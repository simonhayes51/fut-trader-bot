# cogs/trending.py
from __future__ import annotations

import os
import io
import json
import re
import asyncio
import logging
from datetime import datetime
from typing import List, Tuple

import aiohttp
import asyncpg
import discord
from bs4 import BeautifulSoup
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont

# ---------------- Config ----------------
CONFIG_FILE = "autotrend_config.json"
PLAYER_DB_URL = os.getenv("PLAYER_DATABASE_URL") or os.getenv("DATABASE_URL")

MOMENTUM_BASE = "https://www.fut.gg/players/momentum"       # /{tf}/?page=1
FUTGG_PRICE_URL = "https://www.fut.gg/api/fut/player-prices/26/{card_id}"

REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fut.gg/",
    "X-Requested-With": "XMLHttpRequest",
}

# Font path used by the board renderer (change if you ship a custom font)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trending")

# ------------- utils -------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# robust card-id extraction
_26_SEGMENT_RE = re.compile(r"/26-(\d+)(?:[/?#]|$)", re.IGNORECASE)
_LAST_NUM_AFTER_PLAYERS_RE = re.compile(r"/players/[^?#]*?(\d+)(?:[/?#]|$)", re.IGNORECASE)

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

def _pct_from_node(node) -> float | None:
    # scan node and a couple ancestors for a percentage like -12.3%
    for cur in (node, getattr(node, "parent", None), getattr(node.parent, "parent", None)):
        if not cur:
            continue
        txt = cur.get_text(" ", strip=True) or ""
        m = re.search(r"([+\-]?\d+(?:\.\d+)?)\s*%", txt)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
    return None

# ------------- Cog -------------
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
            self.db = await asyncpg.create_pool(PLAYER_DB_URL, command_timeout=10)

    async def cog_unload(self):
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        self.auto_post_trends.cancel()

    # ----------- FUT.GG scraping -----------
    async def _html(self, url: str) -> str:
        try:
            async with self.session.get(url) as r:
                if r.status != 200:
                    logger.debug(f"[fetch] {r.status} for {url}")
                    return ""
                return await r.text()
        except Exception as e:
            logger.warning(f"[fetch] {url} failed: {e}")
            return ""

    async def _momentum_items(self, kind: str, tf: str, page: int = 1) -> list[dict]:
        """
        kind: 'risers' | 'fallers'
        tf: '6' | '12' | '24'
        Returns [{'card_id': int, 'percent': float}, ...] (deduped)
        """
        html = await self._html(f"{MOMENTUM_BASE}/{tf}/?page={page}")
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/players/" not in href:
                continue
            cid = _cid_from_href(href)
            if not cid:
                continue
            pct = _pct_from_node(a)
            if pct is None:
                continue
            if kind == "risers" and pct <= 0:
                continue
            if kind == "fallers" and pct >= 0:
                continue
            items.append({"card_id": int(cid), "percent": float(pct)})
        # de-dupe by card_id
        seen = set()
        out = []
        for it in items:
            if it["card_id"] not in seen:
                out.append(it); seen.add(it["card_id"])
        return out

    # ----------- Price fetch (robust) -----------
    async def _console_price(self, card_id: int) -> Tuple[int | None, bool | None, str | None]:
        """
        Returns (price, is_extinct, updated_at_iso).
        Supports both FUT.GG JSON shapes and retries on 429/5xx.
        """
        url = FUTGG_PRICE_URL.format(card_id=card_id)
        for attempt in range(3):
            try:
                async with self.session.get(url) as r:
                    status = r.status
                    if status == 429 or 500 <= status < 600:
                        await asyncio.sleep(0.8 * (attempt + 1))
                        continue
                    if status != 200:
                        logger.debug(f"[price] {status} for {url}")
                        return (None, None, None)

                    # accept whatever content-type
                    try:
                        data = await r.json(content_type=None)
                    except Exception:
                        txt = await r.text()
                        try:
                            data = json.loads(txt)
                        except Exception:
                            logger.debug(f"[price] non-json for {card_id}: {txt[:200]}")
                            return (None, None, None)

                    # Shape A: root 'prices' -> 'ps'
                    try:
                        ps = (data or {}).get("prices", {}).get("ps") or (data or {}).get("prices", {}).get("playstation")
                        if isinstance(ps, dict):
                            raw = ps.get("price") or ps.get("lowestBin") or ps.get("LCPrice")
                            if isinstance(raw, str):
                                raw = int("".join(ch for ch in raw if ch.isdigit()))
                            price = int(raw) if isinstance(raw, (int, float)) and raw > 0 else None
                            extinct = bool(ps.get("isExtinct")) if "isExtinct" in ps else None
                            updated = ps.get("updatedAt") or ps.get("priceUpdatedAt")
                            return (price, extinct, updated)
                    except Exception:
                        pass

                    # Shape B: 'data' -> 'currentPrice'
                    try:
                        cur = (data or {}).get("data", {}).get("currentPrice", {})
                        if isinstance(cur, dict) and cur:
                            raw = cur.get("price")
                            if isinstance(raw, str):
                                raw = int("".join(ch for ch in raw if ch.isdigit()))
                            price = int(raw) if isinstance(raw, (int, float)) and raw > 0 else None
                            extinct = bool(cur.get("isExtinct")) if "isExtinct" in cur else None
                            updated = cur.get("priceUpdatedAt") or cur.get("updatedAt")
                            return (price, extinct, updated)
                    except Exception:
                        pass

                    # Unknown shape
                    logger.debug(f"[price] unexpected JSON for {card_id}: {str(data)[:300]}")
                    return (None, None, None)

            except Exception as e:
                logger.debug(f"[price] fetch error {card_id}: {e}")
                await asyncio.sleep(0.6 * (attempt + 1))
        return (None, None, None)

    # ----------- DB enrichment -----------
    async def _enrich(self, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        ids = [r["card_id"] for r in rows]
        meta = {}
        if self.db:
            try:
                dbrows = await self.db.fetch(
                    """
                    SELECT card_id, name, rating, position, club, nation, league, image_url
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
            out.append({
                "card_id": cid,
                "percent": r["percent"],
                "name": m.get("name") or f"Card {cid}",
                "rating": m.get("rating"),
                "position": m.get("position"),
                "club": m.get("club"),
                "nation": m.get("nation"),
                "league": m.get("league"),
                "image": m.get("image_url"),
                "price": price,
                "extinct": extinct,
                "price_updated_at": updated,
            })
        return out

    # ----------- Board renderer (icons next to lines) -----------
    async def _build_board(self, items: list[dict]) -> discord.File | None:
        try:
            rows = min(10, len(items))
            if rows == 0:
                return None

            W = 940
            LINE_H = 96
            H = 24 + rows * LINE_H + 24
            PADX = 20
            IMG_W, IMG_H = 76, 92
            GAP = 14

            board = Image.new("RGBA", (W, H), (28, 30, 36, 255))
            draw = ImageDraw.Draw(board)
            try:
                f_title = ImageFont.truetype(FONT_PATH, 28)
                f_sub = ImageFont.truetype(FONT_PATH, 20)
            except Exception:
                f_title = ImageFont.load_default()
                f_sub = ImageFont.load_default()

            async def fetch_img(url: str) -> Image.Image | None:
                if not url:
                    return None
                try:
                    async with self.session.get(url) as r:
                        if r.status != 200:
                            return None
                        b = await r.read()
                    img = Image.open(io.BytesIO(b)).convert("RGBA")
                    w, h = img.size
                    s = min(IMG_W / max(1, w), IMG_H / max(1, h))
                    img = img.resize((int(w*s), int(h*s)), Image.LANCZOS)
                    slot = Image.new("RGBA", (IMG_W, IMG_H), (0,0,0,0))
                    slot.paste(img, ((IMG_W - img.size[0])//2, (IMG_H - img.size[1])//2), img)
                    return slot
                except Exception:
                    return None

            thumbs = [await fetch_img(it.get("image", "")) for it in items[:rows]]
            numbers = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

            for idx, it in enumerate(items[:rows]):
                y = 24 + idx * LINE_H
                if idx > 0:
                    draw.line([(PADX, y-4), (W-PADX, y-4)], fill=(58, 60, 68, 255), width=1)

                draw.text((PADX, y+8), numbers[idx], font=f_title, fill=(190,210,255,255))

                x_img = PADX + 48
                if thumbs[idx]:
                    board.paste(thumbs[idx], (x_img, y+2), thumbs[idx])

                x_text = x_img + IMG_W + GAP
                name = it.get("name") or f"Card {it['card_id']}"
                rating = f" ({it['rating']})" if it.get("rating") else ""
                draw.text((x_text, y+6), f"{name}{rating}", font=f_title, fill=(70,170,255,255))

                price_txt = "Extinct" if it.get("extinct") else (f"{it['price']:,} 🪙" if it.get("price") else "N/A")
                draw.text((x_text, y+44), f"💰 {price_txt}", font=f_sub, fill=(230,230,230,255))

                pct = it.get("percent")
                pct_txt = f"{pct:+.2f}%" if isinstance(pct, (int,float)) else "—"
                pct_col = (88, 214, 141, 255) if (isinstance(pct,(int,float)) and pct >= 0) else (255, 120, 120, 255)
                draw.text((x_text + 280, y+44), "↕", font=f_sub, fill=(210,210,210,255))
                draw.text((x_text + 305, y+44), pct_txt, font=f_sub, fill=pct_col)

            buf = io.BytesIO()
            board.save(buf, format="PNG")
            buf.seek(0)
            return discord.File(buf, filename="trending_board.png")
        except Exception as e:
            logger.warning(f"[board] failed: {e}")
            return None

    # ----------- Embed builders -----------
    async def _build_embed(self, kind: str, tf: str, items: list[dict]) -> tuple[discord.Embed, discord.File | None]:
        emoji = "📈" if kind == "risers" else "📉"
        tf_emoji = {"6": "🕕", "12": "🕛", "24": "📅"}.get(tf, "📅")
        title = f"{emoji} Top 10 {'Risers' if kind=='risers' else 'Fallers'} – {tf_emoji} {tf}h"
        color = discord.Color.green() if kind == "risers" else discord.Color.red()

        embed = discord.Embed(title=title, color=color)

        # text columns (keeps content searchable)
        left = right = ""
        numbers = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, p in enumerate(items[:10]):
            name = p.get("name") or f"Card {p['card_id']}"
            rating = f" ({p['rating']})" if p.get("rating") else ""
            price_txt = "Extinct" if p.get("extinct") else (f"{p['price']:,} 🪙" if p.get("price") else "N/A")
            trend_icon = "📈" if (p.get("percent") or 0) >= 0 else "📉"
            trend_val = f"{float(p['percent']):+.2f}%" if isinstance(p.get("percent"), (int, float)) else "—"
            line = f"**{numbers[i]} {name}{rating}**\n💰 {price_txt}\n{trend_icon} {trend_val}\n\n"
            (left := left + line) if i < 5 else (right := right + line)

        embed.add_field(name="\u200b", value=left or "–", inline=True)
        embed.add_field(name="\u200b", value=right or "–", inline=True)

        # unified board image with thumbnails
        board = await self._build_board(items[:10])
        if board:
            embed.set_image(url="attachment://trending_board.png")

        # footer with optional updated time (if any)
        ts = next((x.get("price_updated_at") for x in items if x.get("price_updated_at")), None)
        footer = "Data & Prices: FUT.GG • Created by www.futhub.co.uk"
        if ts:
            footer += f" • Updated: {ts}"
        embed.set_footer(text=footer)

        return embed, board

    async def generate_trend_embed(self, kind: str, tf: str) -> tuple[discord.Embed, discord.File | None]:
        raw = await self._momentum_items(kind, tf, page=1)
        raw.sort(key=lambda x: x["percent"], reverse=(kind == "risers"))
        raw = raw[:20]
        enriched = await self._enrich(raw)

        # extra dedupe guard
        seen = set(); uniq = []
        for it in enriched:
            cid = int(it["card_id"])
            if cid not in seen:
                uniq.append(it); seen.add(cid)

        return await self._build_embed(kind, tf, uniq[:10])

    # ----------- Commands -----------
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
        embed, file = await self.generate_trend_embed(direction.value, timeframe.value)
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(
            label="🔁 Refresh",
            style=discord.ButtonStyle.primary,
            custom_id=f"refresh_{direction.value}_{timeframe.value}"
        ))
        if file:
            await interaction.followup.send(embed=embed, view=view, file=file)
        else:
            await interaction.followup.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id")
            if cid and cid.startswith("refresh_"):
                _, direction, timeframe = cid.split("_")
                await interaction.response.defer()
                embed, file = await self.generate_trend_embed(direction, timeframe)
                if file:
                    await interaction.edit_original_response(embed=embed, attachments=[file])
                else:
                    await interaction.edit_original_response(embed=embed)

    # ----------- Autopost -----------
    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for guild_id, conf in self.config.items():
            if now != conf.get("start_time", "00:00"):
                continue
            if not conf.get("enabled", False):
                continue
            channel = self.bot.get_channel(conf.get("channel_id"))
            if not channel:
                continue
            try:
                fallers_embed, fallers_file = await self.generate_trend_embed("fallers", "24")
                risers_embed, risers_file = await self.generate_trend_embed("risers", "24")
                ping = f"<@&{conf['ping_role']}>" if conf.get("ping_role") else None
                if fallers_file:
                    await channel.send(content=ping, embed=fallers_embed, file=fallers_file)
                else:
                    await channel.send(content=ping, embed=fallers_embed)
                if risers_file:
                    await channel.send(embed=risers_embed, file=risers_file)
                else:
                    await channel.send(embed=risers_embed)
                self.config[guild_id]["last_post"] = now
                save_config(self.config)
            except Exception as e:
                logger.error(f"[AutoPost] guild {guild_id}: {e}")

    @app_commands.command(name="setupautotrending", description="⚙️ Configure auto-posting of trends")
    @app_commands.describe(channel="Where to post", frequency="How often (hours)", start_time="When to start (HH:MM UTC)", ping_role="Optional ping role")
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