# cogs/trending.py
from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional

import discord
from discord.ext import commands, tasks
from discord import app_commands

import aiohttp
import asyncpg
from bs4 import BeautifulSoup
import unicodedata

CONFIG_FILE = "autotrend_config.json"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fut.trending")

PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL")
FUTGG_PRICE_API = "https://www.fut.gg/api/fut/player-prices"  # /{card_id}

# ----------------- helpers -----------------
def _normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode("ascii").lower().strip()

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
        self.session: Optional[aiohttp.ClientSession] = None
        self.db: Optional[asyncpg.Pool] = None
        self.player_index: Dict[tuple, Dict] = {}  # (name_norm, rating) -> row
        self.config = load_config()
        self.auto_post_trends.start()

    async def cog_load(self):
        # HTTP
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Referer": "https://www.futbin.com/",
                },
            )
        # DB
        if not self.db:
            if not PLAYER_DATABASE_URL:
                raise RuntimeError("PLAYER_DATABASE_URL is not set")
            self.db = await asyncpg.create_pool(dsn=PLAYER_DATABASE_URL, min_size=1, max_size=6)
        # Index players once
        await self._build_player_index()

    async def cog_unload(self):
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        self.auto_post_trends.cancel()

    async def _build_player_index(self):
        """
        Build a quick lookup index from fut_players so we can map FUTBIN (name,rating) -> card_id for fut.gg prices.
        """
        sql = """
        SELECT name, rating, card_id, image_url, player_slug, position, club, nation, league
        FROM public.fut_players
        WHERE card_id IS NOT NULL;
        """
        try:
            rows = await self.db.fetch(sql)
            idx: Dict[tuple, Dict] = {}
            for r in rows:
                key = (_normalize(r["name"]), int(r["rating"]) if r["rating"] is not None else None)
                if key[1] is None:
                    continue
                # prefer the first seen entry; FUTBIN trending is per base card typically
                idx.setdefault(key, dict(r))
            self.player_index = idx
            logger.info(f"[Trending] Player index built: {len(self.player_index)} entries")
        except Exception as e:
            logger.error(f"[Trending] Failed building player index: {e}")
            self.player_index = {}

    # ----------------- network utils -----------------
    async def fetch_text(self, url: str) -> Optional[str]:
        if not self.session:
            await self.cog_load()
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                logger.warning(f"HTTP {response.status} for {url}")
        except Exception as e:
            logger.error(f"Fetch error: {e}")
        return None

    async def futgg_console_price(self, card_id: str) -> Optional[int]:
        """
        Robustly extract a Console price from fut.gg JSON. Returns int or None.
        """
        if not card_id:
            return None
        url = f"{FUTGG_PRICE_API}/{card_id}"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json(content_type=None)
        except Exception as e:
            logger.warning(f"[FUTGG] price error for {card_id}: {e}")
            return None

        root = payload.get("data") or payload
        cur = root.get("currentPrice") or {}
        price = cur.get("price")

        def to_int(v):
            try:
                return int(str(v).replace(",", "").strip())
            except Exception:
                return None

        if price is not None:
            return to_int(price)

        # fallback to platform buckets
        plat = root.get("platforms") or root.get("prices") or {}
        def pick(node):
            if not isinstance(node, dict): return None
            for k in ("lowest","lowestPrice","current","price","l"):
                if k in node:
                    return to_int(node[k])
            for v in node.values():
                pv = to_int(v)
                if pv is not None:
                    return pv
            return None
        ps = pick(plat.get("playstation") or plat.get("ps"))
        xb = pick(plat.get("xbox"))
        vals = [v for v in (ps, xb) if v is not None]
        return min(vals) if vals else None

    # ----------------- FUTBIN trending scrape -----------------
    async def fetch_trending_data(self, timeframe: str):
        """
        Scrape FUTBIN market page to get trending players for 4h/24h.
        """
        tf_map = {
            "24h": "div.market-players-wrapper.market-24-hours.m-row.space-between",
            "4h":  "div.market-players-wrapper.market-4-hours.m-row.space-between",
        }
        url = "https://www.futbin.com/market"
        html = await self.fetch_text(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(tf_map.get(timeframe, ""))
        cards = container.select("a.market-player-card") if container else []
        players = []
        for card in cards:
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue
            raw = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
            try:
                trend = float(raw)
                if "day-change-negative" in trend_tag.get("class", []):
                    trend = -abs(trend)
            except Exception:
                continue
            name_el = card.select_one(".playercard-s-25-name")
            rating_el = card.select_one(".playercard-s-25-rating")
            link = card.get("href")
            if not name_el or not rating_el or not link:
                continue
            name = name_el.text.strip()
            rating = rating_el.text.strip()
            players.append({
                "name": name,
                "rating": rating,
                "trend": trend,
                "futbin_url": f"https://www.futbin.com{link}?platform=ps",
            })
        return players

    # ----------------- embed builder -----------------
    async def generate_trend_embed(self, direction: str, timeframe: str):
        """
        direction: "riser" | "faller" | "smart"
        timeframe: "4h" | "24h"
        """
        footer_text = "Data: FUTBIN • Prices: FUT.GG • Created by www.futhub.co.uk"

        if direction == "smart":
            short = await self.fetch_trending_data("4h")
            long = await self.fetch_trending_data("24h")
            map_4h = {(p["name"], p["rating"]): p["trend"] for p in short}
            smart = []
            for p in long:
                key = (p["name"], p["rating"])
                if key in map_4h and ((map_4h[key] > 0 > p["trend"]) or (map_4h[key] < 0 < p["trend"])):
                    # lookup in DB for card_id
                    idx_key = (_normalize(p["name"]), int(p["rating"]))
                    row = self.player_index.get(idx_key)
                    price_txt = "N/A"
                    if row:
                        price_val = await self.futgg_console_price(str(row["card_id"]))
                        if price_val is not None:
                            price_txt = f"{price_val:,} 🪙"
                    p["trend_4h"] = map_4h[key]
                    p["trend_24h"] = p["trend"]
                    p["price_txt"] = price_txt
                    smart.append(p)

            players = smart[:10]
            title = f"🧠 Smart Movers – Trend flipped (4h ↔ 24h)"
            embed = discord.Embed(title=title, color=discord.Color.orange())
            embed.set_footer(text=footer_text)

            number_emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
            left = right = ""
            for i, p in enumerate(players):
                line = (
                    f"**{number_emojis[i]} {p['name']} ({p['rating']})**\n"
                    f"💰 {p['price_txt']}\n"
                    f"↔️ 4h: {p['trend_4h']:+.1f}%\n"
                    f"🗓️ 24h: {p['trend_24h']:+.1f}%\n\n"
                )
                (left if i < 5 else right).__iadd__(line)  # type: ignore
            embed.add_field(name="\u200b", value=left.strip() or "—", inline=True)
            embed.add_field(name="\u200b", value=right.strip() or "—", inline=True)
            return embed

        # regular risers/fallers
        raw = await self.fetch_trending_data(timeframe)
        is_riser = direction == "riser"
        emoji = "📈" if is_riser else "📉"
        tf_emoji = "🕓" if timeframe == "4h" else "🗓️"
        title = f"{emoji} Top 10 {'Risers' if is_riser else 'Fallers'} – {tf_emoji} {timeframe}"
        embed = discord.Embed(
            title=title,
            color=discord.Color.green() if is_riser else discord.Color.red()
        )
        embed.set_footer(text=footer_text)

        number_emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        left = right = ""
        players = []

        for p in raw:
            if (p["trend"] > 0) == is_riser:
                # Use DB to get card_id → price from fut.gg
                idx_key = (_normalize(p["name"]), int(p["rating"]))
                row = self.player_index.get(idx_key)
                price_txt = None
                if row:
                    price_val = await self.futgg_console_price(str(row["card_id"]))
                    if price_val is not None:
                        price_txt = f"{price_val:,} 🪙"
                # Only include if we have at least a price (or allow without? your call)
                players.append({
                    **p,
                    "price_txt": price_txt or "N/A",
                })
            if len(players) == 10:
                break

        trend_icon = "📈" if is_riser else "📉"
        for i, p in enumerate(players):
            line = (
                f"**{number_emojis[i]} {p['name']} ({p['rating']})**\n"
                f"💰 {p['price_txt']}\n"
                f"{trend_icon} {p['trend']:+.2f}%\n\n"
            )
            if i < 5:
                left += line
            else:
                right += line

        embed.add_field(name="\u200b", value=left.strip() or "—", inline=True)
        embed.add_field(name="\u200b", value=right.strip() or "—", inline=True)
        return embed

    # ----------------- slash command -----------------
    @app_commands.command(name="trending", description="📊 Show trending players (FUTBIN) with FUT.GG Console prices")
    @app_commands.describe(direction="Risers, Fallers, or Smart Movers", timeframe="Timeframe to compare")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller"),
            app_commands.Choice(name="🧠 Smart Movers", value="smart"),
        ],
        timeframe=[
            app_commands.Choice(name="🗓️ 24 Hours", value="24h"),
            app_commands.Choice(name="🕓 4 Hours", value="4h"),
        ],
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        # Make sure index exists (handles hot-reloads)
        if not self.player_index:
            await self._build_player_index()
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

    # ----------------- auto post -----------------
    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for guild_id, conf in self.config.items():
            if now != conf.get("start_time", "00:00"):
                continue
            if not conf.get("enabled", False):
                continue
            channel_id = conf.get("channel_id")
            last = conf.get("last_post")
            if last and last == now:
                continue
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    fallers = await self.generate_trend_embed("faller", "24h")
                    risers = await self.generate_trend_embed("riser", "24h")
                    ping = f"<@&{conf['ping_role']}>" if conf.get("ping_role") else ""
                    if ping:
                        await channel.send(content=ping, embed=fallers)
                    else:
                        await channel.send(embed=fallers)
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
            "ping_role": ping_role.id if ping_role else None,
        }
        save_config(self.config)
        await interaction.response.send_message("✅ Auto trending setup complete.")


async def setup(bot):
    await bot.add_cog(Trending(bot))