import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import requests
import json
import os
from datetime import datetime
import asyncio

CONFIG_FILE = "autotrend_config.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}
MOMENTUM_URL = "https://www.fut.gg/players/momentum/"

RARITY_ORDER = ["Bronze", "Silver", "Gold"]  # fallback order


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

    def scrape_momentum(self):
        response = requests.get(MOMENTUM_URL, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("a.group\\/player")
        risers, fallers = [], []

        for card in cards:
            try:
                name_rating = card.find("img")["alt"]  # e.g., "Touré - 87 - UT Heroes"
                name, rating, *_ = name_rating.split(" - ")
                rating = int(rating.strip())

                position = card.select_one(".text-black").text.strip()
                price = card.select_one(".text-numbers-bold").find_next("div").text.strip()
                trend_text = card.select_one(".text-green-500, .text-red-500").text.strip().replace("%", "")
                trend = float(trend_text)

                club = card.select_one(".text-gray-100").text.strip()

                data = {
                    "name": name,
                    "rating": rating,
                    "position": position,
                    "price": price,
                    "trend": trend,
                    "club": club,
                }
                if trend >= 0:
                    risers.append(data)
                else:
                    fallers.append(data)

            except Exception:
                continue

        return risers[:10], fallers[:10]

    def build_embed(self, players, trend_type):
        emoji = "📈" if trend_type == "riser" else "📉"
        title = f"{emoji} Daily Top 10 {'Risers' if trend_type == 'riser' else 'Fallers'} (🎮 Console)"
        color = discord.Color.green() if trend_type == "riser" else discord.Color.red()

        embed = discord.Embed(title=title, color=color, timestamp=datetime.utcnow())

        if not players:
            embed.description = "No trending players found."
            return embed

        for player in players:
            embed.add_field(
                name=f"{player['name']} ({player['rating']})",
                value=(
                    f"{emoji} `{player['trend']}%`\n"
                    f"💰 `{player['price']}`\n"
                    f"🧭 {player['position']} – {player['club']}"
                ),
                inline=False
            )
        return embed

    @app_commands.command(name="trending", description="📊 Show today's top trending FUT players")
    async def trending(self, interaction: discord.Interaction):
        await interaction.response.defer()
        risers, fallers = self.scrape_momentum()

        await interaction.followup.send(embed=self.build_embed(risers, "riser"))
        await interaction.followup.send(embed=self.build_embed(fallers, "faller"))

    @app_commands.command(name="setupautotrending", description="🛠️ Set auto-post channel & time for trending data")
    @app_commands.describe(channel="Channel to post in", post_time="Time in 24h format (e.g. 21:00)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need Manage Server permission.", ephemeral=True)
            return

        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use HH:MM.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-posting set for **{post_time}** in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue

            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue

            risers, fallers = self.scrape_momentum()

            try:
                await channel.send(embed=self.build_embed(risers, "riser"))
                await asyncio.sleep(2)
                await channel.send(embed=self.build_embed(fallers, "faller"))
            except Exception as e:
                print(f"Error posting in guild {guild_id}: {e}")

    @auto_post_trends.before_loop
    async def before_posting(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Trending(bot))
