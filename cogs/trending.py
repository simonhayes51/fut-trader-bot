# cogs/trending.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from bs4 import BeautifulSoup
import asyncio
import json
import os
from datetime import datetime

CONFIG_FILE = "autotrend_config.json"

MOMENTUM_URL = "https://www.fut.gg/players/momentum"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

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
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def fetch_html(self, url):
        async with self.session.get(url, headers=HEADERS) as resp:
            return await resp.text()

    async def get_trending(self, trend_type="fallers", timeframe="24h"):
        html = await self.fetch_html(MOMENTUM_URL)
        soup = BeautifulSoup(html, "html.parser")

        selector = "market-players-wrapper.market-24-hours" if timeframe == "24h" else "market-players-wrapper.market-6-hours"
        section = soup.find("div", class_=selector)
        if not section:
            return []

        players = []
        cards = section.find_all("a", class_="player-item")
        for card in cards:
            name = card.find("div", class_="name")
            if not name or "Momentum" in name.text:
                continue

            player_name = name.text.strip()
            rating_tag = card.find("div", class_="rating")
            rating = rating_tag.text.strip() if rating_tag else ""
            trend_tag = card.find("div", class_="trend")
            trend = trend_tag.text.strip().replace(" ", "").replace("↑", "+").replace("↓", "-") if trend_tag else "N/A"

            price_tag = card.find("div", class_="price-value")
            price = price_tag.text.strip() if price_tag else "N/A"

            if not player_name:
                continue

            players.append({
                "name": f"{player_name} ({rating})" if rating else player_name,
                "price": price,
                "trend": trend,
            })

        players = [p for p in players if p["name"] and p["price"] != "N/A"]
        return players[:10]

    @app_commands.command(name="trending", description="Show top risers or fallers")
    @app_commands.describe(
        trend_type="Choose between risers or fallers",
        timeframe="Select timeframe: 6h or 24h"
    )
    async def trending(
        self, interaction: discord.Interaction,
        trend_type: str = "fallers",
        timeframe: str = "24h"
    ):
        await interaction.response.defer(thinking=True)
        data = await self.get_trending(trend_type, timeframe)

        emoji = "📉" if trend_type == "fallers" else "📈"
        clock = "🕕" if timeframe == "6h" else "📅"

        embed = discord.Embed(
            title=f"{emoji} Top 10 {trend_type.capitalize()} – {clock} {timeframe}",
            colour=discord.Colour.red() if trend_type == "fallers" else discord.Colour.green(),
        )

        if not data:
            embed.description = "No data found."
        else:
            lines = []
            for i, player in enumerate(data, start=1):
                lines.append(
                    f"{i}. **{player['name']}**\n💰 {player['price']} 🪙\n{emoji} {player['trend']}"
                )
            embed.description = "\n\n".join(lines)

        embed.set_footer(
            text=f"Data & Prices: FUT.GG • Created by www.futhub.co.uk • Updated: {datetime.utcnow().isoformat()}Z"
        )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Trending(bot))