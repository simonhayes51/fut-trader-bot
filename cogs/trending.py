# cogs/trending.py
from __future__ import annotations

import os
import re
import io
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Tuple

import aiohttp
import asyncpg
import discord
from discord import app_commands
from discord.ext import commands, tasks
from bs4 import BeautifulSoup

# --------------- Config ---------------
CONFIG_FILE = "autotrend_config.json"
PLAYER_DB_URL = os.getenv("PLAYER_DATABASE_URL") or os.getenv("DATABASE_URL")

MOMENTUM_BASE = "https://www.fut.gg/players/momentum"      # /{tf}/?page=1
FUTGG_PRICE_URL = "https://www.fut.gg/api/fut/player-prices/26/{card_id}"

REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fut.gg/",
    "X-Requested-With": "XMLHttpRequest",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trending")

# --------------- helpers ---------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# FUT.GG id & % extractors
_26_SEGMENT_RE = re.compile(r"/26-(\d+)(?:[/?#]|$)", re.IGNORECASE)
_LAST_NUM_AFTER_PLAYERS_RE = re.compile(r"/players/[^?#]*?(\d+)(?:[/?#]|$)", re.IGNORECASE)
PCT_RE = re.compile(r"([+\-]?\d+(?:\.\d+)?)\s*%")

def _cid_from_href(href: str) -> int | None:
    if "/players/" not in href:
        return None
    m = _26_SEGMENT_RE.search(href)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    m = _LAST_NUM_AFTER_PLAYERS_RE.search(href)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return None

def _name_hint_from_href(href: str) -> str | None:
    """
    /players/256853-malik-tillman/26-50588501/ -> 'Malik Tillman'
    """
    try:
        if "/players/" not in href:
            return None
        path = href.split("/players/", 1)[1].strip("/")
        first_seg = path.split("/", 1)[0]
        slug = first_seg.split("-", 1)[1] if "-" in first_seg and first_seg.split("-", 1)[0].isdigit() else first_seg
        words = [w for w in slug.replace("-", " ").split() if w]
        return " ".join(w.capitalize() for w in words) if words else None
    except Exception:
        return None

def _pct_from_node(node) -> float | None:
    # search node and a couple ancestors/siblings for a percent like "-12.3%"
    try:
        cur = node
        for _ in range(5):
            if not cur:
                break
            txt = cur.get_text(" ", strip=True) if hasattr(cur, "get_text") else ""
            m = PCT_RE.search(txt or "")
            if m:
                return float(m.group(1))
            cur = getattr(cur, "parent", None)
        par = getattr(node, "parent", None)
        if par:
            for sib in getattr(par, "children", []):
                try:
                    txt = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else ""
                    m = PCT_RE.search(txt or "")
                    if m:
                        return float(m.group(1))
                except Exception:
                    continue
    except Exception:
        pass
    return None

# --------------- Cog ---------------
class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self.db: asyncpg.pool.Pool | None = None
        self.config = load_config()
        self.auto_post_trends.start()

    async def cog_load(self):
        timeout = aiohttp.ClientTimeout(total=12)
        self.session = aiohttp.ClientSession(headers=REQ_HEADERS, timeout=timeout)
        if PLAYER_DB_URL:
            self.db = await asyncpg.create_pool(PLAYER_DB_URL, min_size=1, max_size=3, command_timeout=10)

    async def cog_unload(self):
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        self.auto_post_trends.cancel()

    # ------------ network ------------
    async def _html(self, url: str) -> str:
        try:
            async with self.session.get(url) as r:
                if r.status != 200:
                    logger.debug(f"[fetch] {r.status} {url}")
                    return ""
                return await r.text()
        except Exception as e:
            logger.debug(f"[fetch] {url} failed: {e}")
            return ""

    async def _console_price(self, card_id: int) -> tuple[int | None, bool | None, str | None]:
        """
        Returns (price, is_extinct, updated_at_iso).
        Supports both FUT.GG JSON shapes and retries on 429/5xx.
        """
        url = FUTGG_PRICE_URL.format(card_id=card_id)
        for attempt in range(3):
            try:
                async with self.session.get(url) as r:
                    s = r.status
                    if s == 429 or 500 <= s < 600:
                        await asyncio.sleep(0.8 * (attempt + 1))
                        continue
                    if s != 200:
                        return (None, None, None)
                    try:
                        data = await r.json(content_type=None)
                    except Exception:
                        txt = await r.text()
                        try:
                            data = json.loads(txt)
                        except Exception:
                            logger.debug(f"[price] non-json {card_id}: {txt[:200]}")
                            return (None, None, None)

                    # shape A
                    ps = (data or {}).get("prices", {}).get("ps") or (data or {}).get("prices", {}).get("playstation")
                    if isinstance(ps, dict):
                        raw = ps.get("price") or ps.get("lowestBin") or ps.get("LCPrice")
                        if isinstance(raw, str):
                            raw = int("".join(ch for ch in raw if ch.isdigit()))
                        price = int(raw) if isinstance(raw, (int, float)) and raw > 0 else None
                        extinct = bool(ps.get("isExtinct")) if "isExtinct" in ps else None
                        updated = ps.get("updatedAt") or ps.get("priceUpdatedAt")
                        return (price, extinct, updated)

                    # shape B
                    cur = (data or {}).get("data", {}).get("currentPrice", {})
                    if isinstance(cur, dict) and cur:
                        raw = cur.get("price")
                        if isinstance(raw, str):
                            raw = int("".join(ch for ch in raw if ch.isdigit()))
                        price = int(raw) if isinstance(raw, (int, float)) and raw > 0 else None
                        extinct = bool(cur.get("isExtinct")) if "isExtinct" in cur else None
                        updated = cur.get("priceUpdatedAt") or cur.get("updatedAt")
                        return (price, extinct, updated)

                    logger.debug(f"[price] unknown json {card_id}: {str(data)[:300]}")
                    return (None, None, None)
            except Exception:
                await asyncio.sleep(0.6 * (attempt + 1))
        return (None, None, None)

    # ------------ scraping ------------
    async def _parse_last_page(self, tf: str) -> int:
        html = await self._html(f"{MOMENTUM_BASE}/{tf}/?page=1")
        if not html:
            return 1
        soup = BeautifulSoup(html, "html.parser")
        last = 1
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "page=" in href:
                try:
                    n = int(href.split("page=", 1)[1].split("&", 1)[0])
                    last = max(last, n)
                except Exception:
                    pass
            else:
                t = (a.text or "").strip()
                if t.isdigit():
                    last = max(last, int(t))
        return last

    async def _page_items(self, tf: str, page: int) -> List[dict]:
        html = await self._html(f"{MOMENTUM_BASE}/{tf}/?page={page}")
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        items: List[dict] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            cid = _cid_from_href(href)
            if not cid:
                continue
            pct = _pct_from_node(a)
            if pct is None:
                continue
            items.append({"card_id": int(cid), "percent": float(pct), "name_hint": _name_hint_from_href(href)})
        # de-dupe by card_id (keep first occurrence)
        seen = set()
        out = []
        for it in items:
            if it["card_id"] not in seen:
                out.append(it); seen.add(it["card_id"])
        return out

    async def _fetch_trending(self, kind: str, tf: str, limit: int = 10) -> List[dict]:
        # Fallers -> page 1 (most negative first). Risers -> last page (most positive first).
        last = await self._parse_last_page(tf)
        if kind == "fallers":
            base = await self._page_items(tf, 1)
            base.sort(key=lambda x: x["percent"])  # most negative first
        else:
            base = await self._page_items(tf, last)
            base.sort(key=lambda x: x["percent"], reverse=True)  # most positive first

        # extra guard in case not enough items on that page
        result = base[:limit]
        if len(result) < limit:
            other_page = last if kind == "fallers" else 1
            more = await self._page_items(tf, other_page)
            result = (base + more)[:limit]

        # absolute de-dupe once again
        seen = set(); uniq = []
        for it in result:
            if it["card_id"] not in seen:
                uniq.append(it); seen.add(it["card_id"])
        return uniq[:limit]

    # ------------ enrichment ------------
    async def _enrich(self, rows: List[dict]) -> List[dict]:
        if not rows:
            return []
        ids = [int(r["card_id"]) for r in rows]
        meta: Dict[int, dict] = {}
        if self.db:
            try:
                dbrows = await self.db.fetch(
                    """
                    SELECT card_id, name, rating, position, club, nation, league
                    FROM fut_players
                    WHERE card_id = ANY($1::bigint[])
                    """,
                    ids,
                )
                meta = {int(r["card_id"]): dict(r) for r in dbrows}
            except Exception as e:
                logger.warning(f"[db] enrich failed: {e}")

        out = []
        for r in rows:
            cid = int(r["card_id"])
            m = meta.get(cid, {})
            price, extinct, updated = await self._console_price(cid)
            name = m.get("name") or r.get("name_hint") or f"Card {cid}"
            out.append({
                "card_id": cid,
                "name": name,
                "rating": m.get("rating"),
                "percent": r["percent"],
                "price": price,
                "extinct": extinct,
                "price_updated_at": updated,
                "club": m.get("club"),
                "nation": m.get("nation"),
                "league": m.get("league"),
                "position": m.get("position"),
            })
        return out

    # ------------ embed ------------
    def _build_embed(self, kind: str, tf: str, items: List[dict]) -> discord.Embed:
        emoji = "📈" if kind == "risers" else "📉"
        tf_emoji = {"6": "🕕", "12": "🕛", "24": "📅"}.get(tf, "📅")
        title = f"{emoji} Top 10 {'Risers' if kind=='risers' else 'Fallers'} – {tf_emoji} {tf}h"
        color = discord.Color.green() if kind == "risers" else discord.Color.red()
        embed = discord.Embed(title=title, color=color)

        left = right = ""
        nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, p in enumerate(items[:10]):
            name = p.get("name") or f"Card {p['card_id']}"
            rating = f" ({p['rating']})" if p.get("rating") else ""
            price_txt = "Extinct" if p.get("extinct") else (f"{p['price']:,} 🪙" if p.get("price") else "N/A")
            sign = "📈" if (p.get("percent") or 0) >= 0 else "📉"
            pct = f"{float(p['percent']):+.2f}%"
            line = f"**{nums[i]} {name}{rating}**\n💰 {price_txt}\n{sign} {pct}\n\n"
            (left := left + line) if i < 5 else (right := right + line)

        embed.add_field(name="\u200b", value=left or "–", inline=True)
        embed.add_field(name="\u200b", value=right or "–", inline=True)

        # footer
        ts = next((x.get("price_updated_at") for x in items if x.get("price_updated_at")), None)
        footer = "Data & Prices: FUT.GG • Created by www.futhub.co.uk"
        if ts:
            footer += f" • Updated: {ts}"
        embed.set_footer(text=footer)
        return embed

    async def generate_trend_embed(self, kind: str, tf: str) -> discord.Embed:
        # tf is '6'|'12'|'24'
        raw = await self._fetch_trending(kind, tf, limit=10)
        enriched = await self._enrich(raw)
        # just to be safe: keep unique by card_id, preserve order
        seen = set(); uniq = []
        for it in enriched:
            cid = int(it["card_id"])
            if cid not in seen:
                uniq.append(it); seen.add(cid)
        return self._build_embed(kind, tf, uniq[:10])

    # ------------ commands ------------
    @app_commands.command(name="trending", description="📊 Show top risers/fallers (FUT.GG)")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="risers"),
            app_commands.Choice(name="📉 Fallers", value="fallers"),
        ],
        timeframe=[
            app_commands.Choice(name="🕕 6h", value="6"),
            app_commands.Choice(name="🕛 12h", value="12"),
            app_commands.Choice(name="📅 24h", value="24"),
        ],
    )
    async def trending(
        self,
        interaction: discord.Interaction,
        direction: app_commands.Choice[str],
        timeframe: app_commands.Choice[str],
    ):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value)
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(
            label="🔁 Refresh",
            style=discord.ButtonStyle.primary,
            custom_id=f"refresh_{direction.value}_{timeframe.value}"
        ))
        await interaction.followup.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id")
            if cid and cid.startswith("refresh_"):
                _, direction, timeframe = cid.split("_")
                await interaction.response.defer()
                embed = await self.generate_trend_embed(direction, timeframe)
                await interaction.edit_original_response(embed=embed)

    # ------------ autopost ------------
    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for guild_id, conf in self.config.items():
            if not conf.get("enabled", False):
                continue
            if now != conf.get("start_time", "00:00"):
                continue
            channel = self.bot.get_channel(conf.get("channel_id"))
            if not channel:
                continue
            try:
                fallers = await self.generate_trend_embed("fallers", "24")
                risers  = await self.generate_trend_embed("risers",  "24")
                ping = f"<@&{conf['ping_role']}>" if conf.get("ping_role") else None
                await channel.send(content=ping or None, embed=fallers)
                await channel.send(embed=risers)
                self.config[guild_id]["last_post"] = now
                save_config(self.config)
            except Exception as e:
                logger.error(f"[AutoPost] guild {guild_id}: {e}")

    @app_commands.command(name="setupautotrending", description="⚙️ Configure auto-posting of trends")
    @app_commands.describe(
        channel="Where to post",
        frequency="How often (hours) — stored but not yet used",
        start_time="When to start (HH:MM UTC)",
        ping_role="Optional ping role",
    )
    async def setupautotrending(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        frequency: int,
        start_time: str,
        ping_role: discord.Role | None = None,
    ):
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