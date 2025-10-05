import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncpg
import json
import os
import logging
from datetime import datetime
from bs4 import BeautifulSoup

FUTGG_MOMENTUM_BASE = "https://www.fut.gg/players/momentum"
FUTGG_PRICE_URL = "https://www.fut.gg/api/fut/player-prices/{card_id}"
REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fut.gg/",
}

CONFIG_FILE = "autotrend_config.json"
DB_URL = os.getenv("PLAYER_DATABASE_URL")

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
        self.db = None
        self.config = load_config()
        self.auto_post_trends.start()

    async def cog_load(self):
        self.session = aiohttp.ClientSession(headers=REQ_HEADERS)
        self.db = await asyncpg.create_pool(DB_URL, command_timeout=10)

    async def cog_unload(self):
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        self.auto_post_trends.cancel()

    # ------------------- Core Scraper -------------------
    async def fetch_html(self, url: str) -> str:
        try:
            async with self.session.get(url) as r:
                if r.status == 200:
                    return await r.text()
                logger.warning(f"Bad response {r.status} for {url}")
                return ""
        except Exception as e:
            logger.error(f"Fetch failed {url}: {e}")
            return ""

    async def fetch_momentum(self, kind: str = "risers", timeframe: str = "24") -> list:
        """
        Scrape FUT.GG Momentum (risers/fallers)
        """
        url = f"{FUTGG_MOMENTUM_BASE}/{timeframe}/?page=1"
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        items = []
        for a in soup.select("a[href*='/players/']"):
            href = a.get("href", "")
            if "/players/" not in href:
                continue
            cid = self._extract_card_id(href)
            if not cid:
                continue

            pct = self._extract_percent(a)
            if pct is None:
                continue

            if kind == "risers" and pct <= 0:
                continue
            if kind == "fallers" and pct >= 0:
                continue

            items.append({"card_id": cid, "percent": pct})

        # De-duplicate by card_id
        seen = set()
        final = []
        for it in items:
            if it["card_id"] not in seen:
                final.append(it)
                seen.add(it["card_id"])
        return final[:20]

    def _extract_card_id(self, href: str):
        import re
        m = re.search(r"/26-(\d+)", href)
        if m:
            return int(m.group(1))
        m2 = re.search(r"/players/\d+-[a-z0-9-]+/(\d+)", href)
        if m2:
            return int(m2.group(1))
        return None

    def _extract_percent(self, node):
        import re
        txt = node.get_text(" ", strip=True)
        m = re.search(r"([+-]?\d+(?:\.\d+)?)%", txt)
        if not m:
            parent = node.find_parent()
            if parent:
                txt = parent.get_text(" ", strip=True)
                m = re.search(r"([+-]?\d+(?:\.\d+)?)%", txt)
        if m:
            try:
                return float(m.group(1))
            except:
                return None
        return None

    async def get_console_price(self, card_id: int):
        url = FUTGG_PRICE_URL.format(card_id=card_id)
        try:
            async with self.session.get(url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
            prices = data.get("data", {}).get("prices", {}).get("ps", {})
            price = prices.get("price") or prices.get("lowestBin") or prices.get("LCPrice")
            return int(price) if price and isinstance(price, (int, float)) else None
        except Exception:
            return None

    async def enrich_with_metadata(self, items: list):
        if not self.db or not items:
            return items
        ids = [int(i["card_id"]) for i in items]
        try:
            rows = await self.db.fetch(
                """
                SELECT card_id, name, rating, position, club, nation, league, image_url
                FROM fut_players
                WHERE card_id = ANY($1::bigint[])
                """,
                ids,
            )
            meta = {r["card_id"]: dict(r) for r in rows}
            for i in items:
                m = meta.get(i["card_id"], {})
                i.update(m)
                i["price"] = await self.get_console_price(i["card_id"])
        except Exception as e:
            logger.error(f"DB enrich failed: {e}")
        return items

    # ------------------- Embed Generator -------------------
    async def generate_trend_embed(self, direction: str, timeframe: str):
        """
        direction: risers | fallers
        timeframe: 6 | 24
        """
        data = await self.fetch_momentum(direction, timeframe)
        enriched = await self.enrich_with_metadata(data)

        emoji = "📈" if direction == "risers" else "📉"
        tf_emoji = "🗓️" if timeframe == "24" else "🕓"
        color = discord.Color.green() if direction == "risers" else discord.Color.red()
        title = f"{emoji} Top 10 {'Risers' if direction == 'risers' else 'Fallers'} – {tf_emoji} {timeframe}h"

        embed = discord.Embed(title=title, color=color)
        embed.set_footer(text="Data & Prices: FUT.GG • Created by www.futhub.co.uk")

        number_emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        left, right = "", ""

        players = enriched[:10]
        for i, p in enumerate(players):
            name = p.get("name", f"Card {p['card_id']}")
            rating = f" ({p['rating']})" if p.get("rating") else ""
            price = f"{p['price']:,} 🪙" if p.get("price") else "N/A"
            trend = f"{p['percent']:+.2f}%"
            line = f"**{number_emojis[i]} {name}{rating}**\n💰 {price}\n{emoji} {trend}\n\n"
            if i < 5:
                left += line
            else:
                right += line

        embed.add_field(name="\u200b", value=left or "–", inline=True)
        embed.add_field(name="\u200b", value=right or "–", inline=True)

        # add card images (as one combined strip at bottom)
        files = []
        for p in players[:5]:
            if p.get("image_url"):
                embed.set_image(url=p["image_url"])
                break  # Discord allows only one image per embed

        return embed

    # ------------------- Commands -------------------
    @app_commands.command(name="trending", description="📊 Show top risers or fallers from FUT.GG")
    @app_commands.describe(
        direction="Select Risers or Fallers",
        timeframe="Select timeframe (6h or 24h)"
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="risers"),
            app_commands.Choice(name="📉 Fallers", value="fallers")
        ],
        timeframe=[
            app_commands.Choice(name="🕓 6 Hours", value="6"),
            app_commands.Choice(name="🗓️ 24 Hours", value="24")
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

    # ------------------- Auto Post -------------------
    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for guild_id, conf in self.config.items():
            if now != conf.get("start_time", "00:00"):
                continue
            if not conf.get("enabled", False):
                continue
            channel_id = conf.get("channel_id")
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    fallers = await self.generate_trend_embed("fallers", "24")
                    risers = await self.generate_trend_embed("risers", "24")
                    ping = f"<@&{conf['ping_role']}>" if "ping_role" in conf else ""
                    await channel.send(content=ping or None, embed=fallers)
                    await channel.send(embed=risers)
            except Exception as e:
                logger.error(f"[AutoPost] Error in guild {guild_id}: {e}")

    @app_commands.command(name="setupautotrending", description="⚙️ Configure auto-posting of trends")
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