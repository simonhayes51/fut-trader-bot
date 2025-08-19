import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import asyncio
import json
import os

CONFIG_FILE = "autotrend_config.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}
FUTGG_URL = "https://www.fut.gg/players/momentum/?page={}"  # Pages 1 through ~75


def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.auto_post_trends.start()

    def scrape_trending_players(self):
        risers, fallers = [], []

        for page in range(1, 76):  # First 75 pages
            url = FUTGG_URL.format(page)
            response = requests.get(url, headers=HEADERS)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select("a.group\\/player")

            for card in cards:
                alt_text = card.select_one("img")['alt']  # e.g., "Touré - 87 - UT Heroes"
                trend_tag = card.select_one("div.text-green-500, div.text-red-500")
                if not trend_tag or not alt_text:
                    continue

                trend_str = trend_tag.text.replace('%', '').replace('+', '').strip()
                try:
                    trend = float(trend_str) * (-1 if '-' in trend_tag.text else 1)
                except:
                    continue

                if trend > 0:
                    risers.append((alt_text, trend))
                else:
                    fallers.append((alt_text, trend))

            if len(risers) >= 10 and len(fallers) >= 10:
                break

        # Sort both lists
        risers = sorted(risers, key=lambda x: x[1], reverse=True)[:10]
        fallers = sorted(fallers, key=lambda x: x[1])[:10]
        return risers, fallers

    def build_embed(self, players, trend_type):
        emoji = "📈" if trend_type == "riser" else "📉"
        color = discord.Color.green() if trend_type == "riser" else discord.Color.red()

        title = f"{emoji} Top 10 {'Risers' if trend_type == 'riser' else 'Fallers'} (🎮 Console)"
        embed = discord.Embed(title=title, color=color)

        if not players:
            embed.description = "No trending players found."
            return embed

        for name, trend in players:
            embed.add_field(name=name, value=f"{emoji} `{trend:.2f}%`", inline=False)
        return embed

    @app_commands.command(name="trending", description="📊 Show top 10 risers and fallers from FUT.GG")
    async def trending(self, interaction: discord.Interaction):
        await interaction.response.defer()
        risers, fallers = self.scrape_trending_players()

        await interaction.followup.send(embed=self.build_embed(risers, "riser"))
        await interaction.followup.send(embed=self.build_embed(fallers, "faller"))

    @app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM UTC)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 20:15)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need 'Manage Server' permission to use this.", ephemeral=True)
            return

        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use HH:MM (24-hour)", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-trending set to post daily at **{post_time} UTC** in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue

            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue

            risers, fallers = self.scrape_trending_players()
            try:
                await channel.send(embed=self.build_embed(risers, "riser"))
                await asyncio.sleep(1)
                await channel.send(embed=self.build_embed(fallers, "faller"))
            except Exception as e:
                print(f"Error posting to {channel.id}: {e}")

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Trending(bot))
