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

    def scrape_momentum(self, duration: str = "24h"):
        url = "https://www.fut.gg/players/momentum/"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[ERROR] FUT.GG Momentum status {resp.status_code}")
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"[ERROR] Momentum scraping failed: {e}")
            return []

        # Note: The actual HTML structure may vary. Below is a placeholder layout.
        rows = soup.select("div.momentum-card")  # Adjust selector to match actual site
        players = []
        for row in rows[:10]:
            try:
                name = row.select_one(".player-name").text.strip()
                rating = row.select_one(".player-rating").text.strip()
                trend = row.select_one(".player-trend").text.strip()
                diff = row.select_one(".player-diff").text.strip()
                position = row.select_one(".player-position").text.strip()
                club = row.select_one(".player-club").text.strip()
            except Exception as e:
                print(f"[DEBUG] Momentum row parse error: {e}")
                continue

            players.append({
                "name": name,
                "rating": rating,
                "trend": trend,
                "diff": diff,
                "position": position,
                "club": club
            })
        return players

    @app_commands.command(name="momentum", description="Show top momentum movers from FUT.GG")
    async def momentum(self, interaction: discord.Interaction):
        await interaction.response.defer()
        players = self.scrape_momentum()

        embed = discord.Embed(
            title="FUT.GG Momentum Trends (24h)",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )

        if not players:
            embed.description = "No data found — structure may have changed."
        else:
            for p in players:
                embed.add_field(
                    name=f"{p['name']} ({p['rating']})",
                    value=f"{p['trend']} | {p['diff']} | {p['position']} – {p['club']}",
                    inline=False
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setupautotrending", description="Set auto momentum post channel & time (UTC HH:MM)")
    @app_commands.describe(
        channel="Where to post",
        post_time="HH:MM 24h UTC"
    )
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You need Manage Server perms.", ephemeral=True)

        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            return await interaction.response.send_message("Use HH:MM (24h UTC).", ephemeral=True)

        self.config[str(interaction.guild.id)] = {"channel_id": channel.id, "time": post_time}
        save_config(self.config)
        await interaction.response.send_message(f"Auto momentum set for **{post_time} UTC** in {channel.mention}", ephemeral=True)

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for gid, cfg in self.config.items():
            if cfg.get("time") != now:
                continue

            channel = self.bot.get_channel(cfg["channel_id"])
            if not channel:
                continue

            players = self.scrape_momentum()
            embed = discord.Embed(
                title="Daily Momentum Movers (24h)",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            if not players:
                embed.description = "No momentum data found."
            else:
                for p in players:
                    embed.add_field(
                        name=f"{p['name']} ({p['rating']})",
                        value=f"{p['trend']} | {p['diff']} | {p['position']} – {p['club']}",
                        inline=False
                    )

            try:
                await channel.send(embed=embed)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[ERROR] Momentum post error: {e}")

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Trending(bot))
