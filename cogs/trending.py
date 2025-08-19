import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import requests
import asyncio
import json
import os
from bs4 import BeautifulSoup

CONFIG_FILE = "autotrend_config.json"

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

    def scrape_trending_html(self, trend_type: str):
        """
        Scrapes the FUT.GG Trending Players HTML page.
        trend_type: 'riser' or 'faller' (assumed same listing separated?)
        """
        url = "https://www.fut.gg/players/trending/"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                print(f"[ERROR] HTTP {res.status_code} from FUT.GG trends")
                return []
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"[ERROR] Failed scraping FUT.GG: {e}")
            return []

        # Parse player rows — this will vary depending on page structure
        players = []
        rows = soup.select("div.trending-card")  # update selector as needed
        for row in rows[:10]:
            try:
                name = row.select_one(".player-name").text.strip()
                rating = row.select_one(".player-rating").text.strip()
                price = row.select_one(".player-price").text.strip()
                trend = row.select_one(".player-trend").text.strip()
                position = row.select_one(".player-position").text.strip()
                club = row.select_one(".player-club").text.strip()
            except Exception:
                continue

            players.append({
                "name": name,
                "rating": rating,
                "price": price,
                "trend": trend,
                "position": position,
                "club": club
            })

        return players

    @app_commands.command(name="trending", description="Show top trending players (scraped from FUT.GG)")
    async def trending(self, interaction: discord.Interaction):
        await interaction.response.defer()
        players = self.scrape_trending_html(trend_type="riser")

        embed = discord.Embed(
            title="Trending Players (from FUT.GG)",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        if not players:
            embed.description = "No trending data found or page payload has changed."
        else:
            for p in players:
                embed.add_field(
                    name=f"{p['name']} ({p['rating']})",
                    value=f" {p['trend']} | {p['price']} | {p['position']} – {p['club']}",
                    inline=False
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setupautotrending", description="Set auto-trending daily (HH:MM UTC)")
    @app_commands.describe(
        channel="Channel to post in",
        post_time="Time in HH:MM (UTC)"
    )
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
            return
        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("Use HH:MM 24-hour format.", ephemeral=True)
            return

        gid = str(interaction.guild.id)
        self.config[gid] = {"channel_id": channel.id, "time": post_time}
        save_config(self.config)
        await interaction.response.send_message(f"Auto-trending set at **{post_time} UTC** in {channel.mention}", ephemeral=True)

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for gid, settings in self.config.items():
            if settings["time"] != now:
                continue
            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue
            players = self.scrape_trending_html("riser")
            embed = discord.Embed(
                title="Daily Trending Players",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            if not players:
                embed.description = "No trending data available."
            else:
                for p in players:
                    embed.add_field(
                        name=f"{p['name']} ({p['rating']})",
                        value=f" {p['trend']} | {p['price']} | {p['position']} – {p['club']}",
                        inline=False
                    )
            await channel.send(embed=embed)
            await asyncio.sleep(2)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Trending(bot))
