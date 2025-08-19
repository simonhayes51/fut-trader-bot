import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import requests
import asyncio
import json
from datetime import datetime
import os

CONFIG_FILE = "autotrend_config.json"

# Load/save config

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

    def scrape_players(self, trend_type):
        base_url = "https://www.fut.gg/players/momentum/?page={page}"
        pages = range(71, 76) if trend_type == "riser" else range(1, 6)
        players = []

        for page in pages:
            response = requests.get(base_url.format(page=page), headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select("a.group\\/player")

            for card in cards:
                alt = card.find("img")['alt']
                try:
                    name, rating, version = alt.split(" - ")
                    trend_text = card.select_one(".text-green-500, .text-red-500")
                    trend = trend_text.text.strip() if trend_text else "?"
                    players.append({
                        "name": name,
                        "rating": rating,
                        "version": version,
                        "trend": trend
                    })
                    if len(players) >= 10:
                        return players
                except:
                    continue

        return players

    def build_embed(self, title, emoji, players, color):
        embed = discord.Embed(title=title, color=color, timestamp=datetime.utcnow())

        if not players:
            embed.description = "No trending players found."
        else:
            for player in players:
                embed.add_field(
                    name=f"{player['name']} ({player['rating']})",
                    value=f"{emoji} {player['trend']}\n🃏 {player['version']}",
                    inline=False
                )

        return embed

    @app_commands.command(name="trending", description="📊 Show top trending players on console")
    async def trending(self, interaction: discord.Interaction):
        await interaction.response.defer()
        fallers = self.scrape_players("faller")
        risers = self.scrape_players("riser")

        fallers_embed = self.build_embed("📉 Top 10 Fallers (🎮 Console)", "📉", fallers, discord.Color.red())
        risers_embed = self.build_embed("📈 Top 10 Risers (🎮 Console)", "📈", risers, discord.Color.green())

        await interaction.followup.send(embed=risers_embed)
        await interaction.followup.send(embed=fallers_embed)

    @app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 21:00)")
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
        self.config[guild_id] = {"channel_id": channel.id, "time": post_time}
        save_config(self.config)

        await interaction.response.send_message(f"✅ Auto-trending set to post daily at **{post_time}** in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue

            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue

            risers = self.scrape_players("riser")
            fallers = self.scrape_players("faller")

            risers_embed = self.build_embed("📈 Daily Top 10 Risers (🎮 Console)", "📈", risers, discord.Color.green())
            fallers_embed = self.build_embed("📉 Daily Top 10 Fallers (🎮 Console)", "📉", fallers, discord.Color.red())

            try:
                await channel.send(embed=risers_embed)
                await asyncio.sleep(2)
                await channel.send(embed=fallers_embed)
            except Exception as e:
                print(f"Error posting to {channel.id}: {e}")

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Trending(bot))
