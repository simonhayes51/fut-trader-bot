# cogs/trending.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import aiohttp
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

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.config = load_config()
        self.auto_post_trends.start()

    async def cog_load(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Mozilla/5.0"}
        )

    async def cog_unload(self):
        if self.session:
            await self.session.close()
        self.auto_post_trends.cancel()

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
                price = await self.get_ps_price(p["url"], p["rating"])
                p["trend_4h"] = map_4h[key]
                p["trend_24h"] = p["trend"]
                p["price"] = price or "N/A"
                smart.append(p)
        players = smart[:10]
        title = f"🧠 Smart Movers – Trend flipped from 4h to 24h"
        embed = discord.Embed(title=title, color=discord.Color.red())
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left = ""
        right = ""
        for i, p in enumerate(players):
            try:
                line = (
                    f"**{number_emojis[i]} {p['name']} ({p['rating']})**\n"
                    f"💰 {p['price']}\n"
                    f"🔁 4h: {p['trend_4h']:+.1f}%\n"
                    f"🔁 24h: {p['trend_24h']:+.1f}%\n\n"
                )
            except KeyError as e:
                logger.warning(f"Missing smart mover data: {p} | Error: {e}")
                continue

            if i < 5:
                left += line
            else:
                right += line
        embed.add_field(name="\u200b", value=left.strip(), inline=True)
        embed.add_field(name="\u200b", value=right.strip(), inline=True)
        return embed

    else:
        raw = await self.fetch_trending_data(timeframe)
        emoji = "📈" if direction == "riser" else "📉"
        tf_emoji = "🗓️" if timeframe == "24h" else "🕓"
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console) – {tf_emoji} {timeframe}"
        trend_icon = "📈" if direction == "riser" else "📉"
        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left = ""
        right = ""
        players = []
        for p in raw:
            if (p["trend"] > 0 if direction == "riser" else p["trend"] < 0):
                price = await self.get_ps_price(p["url"], p["rating"])
                if not price:
                    continue
                p["price"] = price
                players.append(p)
            if len(players) == 10:
                break

        for i, p in enumerate(players):
            try:
                line = (
                    f"**{number_emojis[i]} {p['name']} ({p['rating']})**\n"
                    f"💰 {p['price']}\n"
                    f"{trend_icon} {p['trend']:+.2f}%\n\n"
                )
            except KeyError as e:
                logger.warning(f"Missing data for {p['name']} | Error: {e}")
                continue

            if i < 5:
                left += line
            else:
                right += line

        embed.add_field(name="\u200b", value=left.strip(), inline=True)
        embed.add_field(name="\u200b", value=right.strip(), inline=True)
        return embed

    @app_commands.command(name="trending", description="📊 Show trending players")
    @app_commands.describe(direction="Risers, Fallers, or Smart Movers", timeframe="Timeframe to compare")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller"),
            app_commands.Choice(name="🧠 Smart Movers", value="smart")
        ],
        timeframe=[
            app_commands.Choice(name="🗓️ 24 Hours", value="24h"),
            app_commands.Choice(name="🕓 4 Hours", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value)
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="🔁 Refresh", style=discord.ButtonStyle.primary, custom_id=f"refresh_{direction.value}_{timeframe.value}"))
        await interaction.followup.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id")
            if cid and cid.startswith("refresh_"):
                _, direction, timeframe = cid.split("_")
                await interaction.response.defer()
                embed = await self.generate_trend_embed(direction, timeframe)
                if embed:
                    await interaction.edit_original_response(embed=embed)

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for guild_id, conf in self.config.items():
            if now != conf.get("start_time", "00:00"):
                continue
            if not conf.get("enabled", False):
                continue
            channel_id = conf.get("channel_id")
            frequency = int(conf.get("frequency", 24))
            last = conf.get("last_post")
            if last and last == now:
                continue  # Already posted this hour
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    fallers = await self.generate_trend_embed("faller", "24h")
                    risers = await self.generate_trend_embed("riser", "24h")
                    ping = f"<@&{conf['ping_role']}>" if "ping_role" in conf else ""
                    await channel.send(content=ping or None, embed=fallers)
                    await channel.send(embed=risers)
                    self.config[guild_id]["last_post"] = now
                    save_config(self.config)
            except Exception as e:
                logger.error(f"[AutoPost] Error in guild {guild_id}: {e}")

    @app_commands.command(name="setupautotrending", description="⚙️ Configure auto-posting of trends")
    @app_commands.describe(channel="Where to post", frequency="How often (hours)", start_time="When to start (HH:MM UTC)", ping_role="Optional ping role")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, frequency: int, start_time: str, ping_role: discord.Role = None):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
        self.config[str(interaction.guild.id)] = {
            "channel_id": channel.id,
            "frequency": frequency,
            "start_time": start_time,
            "enabled": True,
            "ping_role": ping_role.id if ping_role else None
        }
        save_config(self.config)
        await interaction.response.send_message("✅ Auto trending setup complete.")

async def setup(bot):
    await bot.add_cog(Trending(bot))