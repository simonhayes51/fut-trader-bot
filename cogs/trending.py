import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import json
import os
import logging
from datetime import datetime

CONFIG_FILE = "autotrend_config.json"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_admin_or_owner(member: discord.Member) -> bool:
    if member.guild and member.id == member.guild.owner_id:
        return True
    allowed_roles = ["Admin", "Owner"]
    role_names = [role.name.lower() for role in member.roles]
    return any(allowed.lower() in role_names for allowed in allowed_roles)

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        logger.info(f"Loaded config: {self.config}")
        self.session = None
        self.cached_data = {}

    async def cog_load(self):
        if not self.auto_post_trends.is_running():
            self.auto_post_trends.start()
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Mozilla/5.0"}
        )

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def fetch_url(self, url: str) -> str:
        if not self.session:
            await self.cog_load()
        try:
            async with self.session.get(url) as response:
                return await response.text() if response.status == 200 else None
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return None

    async def get_ps_price(self, url: str, expected_rating: str) -> str:
        html = await self.fetch_url(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        blocks = soup.select("div.player-page-price-versions > div")
        for b in blocks:
            rating = b.select_one(".player-rating")
            price = b.select_one("div.price.inline-with-icon.lowest-price-1")
            if rating and price and rating.text.strip() == expected_rating:
                return price.text.strip()
        fallback = soup.select_one("div.price.inline-with-icon.lowest-price-1")
        return fallback.text.strip() if fallback else None

    async def fetch_trending_data(self, timeframe):
        tf_map = {
            "24h": "div.market-players-wrapper.market-24-hours.m-row.space-between",
            "4h": "div.market-players-wrapper.market-4-hours.m-row.space-between"
        }
        url = "https://www.futbin.com/market"
        html = await self.fetch_url(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(tf_map[timeframe])
        cards = container.select("a.market-player-card") if container else []
        players = []
        for card in cards:
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue
            trend_text = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
            try:
                trend = float(trend_text)
                if "day-change-negative" in trend_tag.get("class", []):
                    trend = -abs(trend)
            except:
                continue
            name = card.select_one(".playercard-s-25-name")
            rating = card.select_one(".playercard-s-25-rating")
            link = card.get("href")
            if not name or not rating or not link:
                continue
            players.append({
                "name": name.text.strip(),
                "rating": rating.text.strip(),
                "trend": trend,
                "url": f"https://www.futbin.com{link}?platform=ps"
            })
        return players

    async def generate_trend_embed(self, direction, timeframe):
        if direction == "smart":
            short = await self.fetch_trending_data("4h")
            long = await self.fetch_trending_data("24h")
            map_4h = {(p["name"], p["rating"]): p["trend"] for p in short}
            smart = []
            for p in long:
                key = (p["name"], p["rating"])
                if key in map_4h and ((map_4h[key] > 0 > p["trend"]) or (map_4h[key] < 0 < p["trend"])):
                    p["trend"] = f"ð 4h: {map_4h[key]:.1f}%, 24h: {p['trend']:.1f}%"
                    smart.append(p)
            players = smart[:10]
            emoji = "ð§ "
            title = f"{emoji} Smart Movers â Trend flipped from 4h to 24h"
        else:
            raw = await self.fetch_trending_data(timeframe)
            players = [p for p in raw if (p["trend"] > 0 if direction == "riser" else p["trend"] < 0)][:10]
            emoji = "ð" if direction == "riser" else "ð"
            tf_emoji = "ðï¸" if timeframe == "24h" else "ð"
            title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (ð® Console) â {tf_emoji} {timeframe}"

        if not players:
            return None

        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())
        embed.set_footer(text="Data from FUTBIN")
        number_emojis = ["1ï¸â£", "2ï¸â£", "3ï¸â£", "4ï¸â£", "5ï¸â£", "6ï¸â£", "7ï¸â£", "8ï¸â£", "9ï¸â£", "ð"]

        for idx, p in enumerate(players):
            price = await self.get_ps_price(p["url"], p["rating"]) if direction != "smart" else "N/A"
            trend = p["trend"] if isinstance(p["trend"], str) else f"{p['trend']:+.1f}%"
            embed.add_field(
                name=f"{number_emojis[idx]} {p['name']} ({p['rating']})",
                value=f"💰 {price}\n{emoji} {trend}",
                inline=True
            )
        return embed

    @app_commands.command(name="trending", description="ð Show trending players")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="ð Risers", value="riser"),
            app_commands.Choice(name="ð Fallers", value="faller"),
            app_commands.Choice(name="ð§  Smart Movers", value="smart")
        ],
        timeframe=[
            app_commands.Choice(name="ðï¸ 24 Hours", value="24h"),
            app_commands.Choice(name="ð 4 Hours", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str] = None):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value if timeframe else "24h")
        if embed:
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="ð Refresh", style=discord.ButtonStyle.primary, custom_id=f"refresh_{direction.value}_{timeframe.value if timeframe else '24h'}"))
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send("â ï¸ Could not generate embed.")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id")
            if cid and cid.startswith("refresh_"):
                parts = cid.split("_")
                if len(parts) == 3:
                    _, direction, timeframe = parts
                    await interaction.response.defer()
                    embed = await self.generate_trend_embed(direction, timeframe)
                    if embed:
                        await interaction.edit_original_response(embed=embed)
                    else:
                        await interaction.followup.send("â ï¸ Refresh failed.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Trending(bot))