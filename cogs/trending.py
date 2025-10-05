# cogs/trending.py
from __future__ import annotations

import os
import re
import io
import json
import time
import math
import logging
from typing import Dict, Optional, List, Tuple

import discord
from discord.ext import commands, tasks
from discord import app_commands

import aiohttp
import asyncpg
from bs4 import BeautifulSoup

# ---------- optional sprite support ----------
try:
    from PIL import Image
    PIL_OK = True
except Exception:
    PIL_OK = False

# ---------------- config ----------------
CONFIG_FILE = "autotrend_config.json"
PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL")

MOMENTUM_BASE = "https://www.fut.gg/players/momentum"
FUTGG_PRICE_URL = "https://www.fut.gg/api/fut/player-prices/26/{card_id}"
REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fut.gg/",
}

FOOTER = "Data & Prices: FUT.GG • Created by www.futhub.co.uk"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fut.trending")

# --------- caching (simple in-memory) ---------
_PAGE_CACHE: Dict[Tuple[str,int], Tuple[float,str]] = {}
PAGE_CACHE_TTL = 120  # seconds

_PRICE_CACHE: Dict[int, Tuple[float, Optional[int], bool]] = {}  # card_id -> (ts, price, extinct)
PRICE_CACHE_TTL = 120  # seconds

# --------- regex helpers (ported from your API) ---------
_26_SEGMENT_RE = re.compile(r"/players/[^?#]*/26-(\d+)(?:[/?#]|$)", re.IGNORECASE)
_LAST_NUM_AFTER_PLAYERS_RE = re.compile(r"/players/[^?#]*?(\d+)(?:[/?#]|$)", re.IGNORECASE)
PCT_RE = re.compile(r"([+\-]?\s?\d+(?:\.\d+)?)\s*%")

def _cid_from_href(href: str) -> Optional[int]:
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

def _name_hint_from_href(href: str) -> Optional[str]:
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

def _name_from_context(anchor) -> Optional[str]:
    try:
        cur = anchor
        for _ in range(6):
            if not cur:
                break
            img = getattr(cur, "find", lambda *a, **k: None)("img", alt=True)
            if img and isinstance(img.get("alt"), str):
                alt = img["alt"].strip()
                name = alt.split(" - ", 1)[0].strip()
                if name and name.lower() != "momentum":
                    return name
            cur = getattr(cur, "parent", None)
    except Exception:
        pass
    return None

_NAME_SUFFIX_CLEAN_RE = re.compile(r"\s+(?:rare|non[- ]?rare|common)(?:\s+\d+\s*ovr)?$", re.IGNORECASE)
_TRAILING_OVR_RE = re.compile(r"\s+\d+\s*ovr\b.*$", re.IGNORECASE)
def _normalize_name(n: Optional[str]) -> Optional[str]:
    if not n: return n
    s = _NAME_SUFFIX_CLEAN_RE.sub("", n.strip())
    s = _TRAILING_OVR_RE.sub("", s)
    return re.sub(r"\s{2,}", " ", s).strip()

def _norm_tf(tf: str) -> str:
    if not tf: return "24"
    tf = tf.lower().strip()
    if tf in {"today","day","daily","24hours","24hr"}: return "24"
    if tf.endswith("h"): tf = tf[:-1]
    return tf if tf in {"6","12","24"} else "24"

# ---------- file config helpers ----------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# =========================================================

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.db: Optional[asyncpg.Pool] = None
        self.config = load_config()
        self.auto_post_trends.start()

    async def cog_load(self):
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers=REQ_HEADERS,
            )
        if not self.db:
            if not PLAYER_DATABASE_URL:
                raise RuntimeError("PLAYER_DATABASE_URL is not set")
            self.db = await asyncpg.create_pool(dsn=PLAYER_DATABASE_URL, min_size=1, max_size=6)

    async def cog_unload(self):
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        self.auto_post_trends.cancel()

    # ---------------- networking ----------------
    async def _fetch_html(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url) as r:
                if r.status != 200:
                    logger.warning(f"[HTTP] {r.status} for {url}")
                    return None
                return await r.text()
        except Exception as e:
            logger.error(f"[HTTP] fetch error: {e}")
            return None

    async def _momentum_page(self, tf_num: str, page: int) -> Optional[str]:
        now = time.time()
        key = (tf_num, page)
        hit = _PAGE_CACHE.get(key)
        if hit and (now - hit[0] < PAGE_CACHE_TTL):
            return hit[1]
        url = f"{MOMENTUM_BASE}/{tf_num}/?page={page}"
        html = await self._fetch_html(url)
        if html:
            _PAGE_CACHE[key] = (now, html)
        return html

    def _parse_last_page_num(self, html: str) -> int:
        soup = BeautifulSoup(html, "html.parser")
        last = 1
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if "page=" in href:
                try:
                    n = int(href.split("page=", 1)[1].split("&", 1)[0])
                    last = max(last, n)
                except Exception:
                    continue
            else:
                t = (a.text or "").strip()
                if t.isdigit():
                    last = max(last, int(t))
        return last

    def _nearest_percent_text(self, node) -> Optional[float]:
        cur = node
        for _ in range(5):
            if cur is None:
                break
            try:
                txt = cur.get_text(" ", strip=True)
                m = PCT_RE.search(txt or "")
                if m:
                    return float(m.group(1).replace(" ", ""))
            except Exception:
                pass
            cur = getattr(cur, "parent", None)
        parent = getattr(node, "parent", None)
        if parent:
            for sib in getattr(parent, "children", []):
                try:
                    txt = sib.get_text(" ", strip=True)
                    m = PCT_RE.search(txt or "")
                    if m:
                        return float(m.group(1).replace(" ", ""))
                except Exception:
                    continue
        return None

    def _extract_items(self, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "html.parser")
        items: List[dict] = []
        seen: set[int] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            cid = _cid_from_href(href)
            if not cid or cid in seen:
                continue
            pct = self._nearest_percent_text(a)
            if pct is None:
                continue

            name_hint_img = _normalize_name(_name_from_context(a))
            name_hint_slug = _normalize_name(_name_hint_from_href(href))
            name_hint = name_hint_img or (name_hint_slug if (name_hint_slug and name_hint_slug.lower() != "momentum") else None) or f"Card {cid}"

            items.append({"card_id": cid, "percent": float(pct), "name_hint": name_hint})
            seen.add(cid)
        return items

    async def _page_items(self, tf_num: str, page: int) -> List[dict]:
        html = await self._momentum_page(tf_num, page)
        return self._extract_items(html) if html else []

    # ---------------- prices (with cache) ----------------
    async def _get_console_price(self, card_id: int) -> Tuple[Optional[int], bool]:
        """Return (price, extinct). Cached for PRICE_CACHE_TTL."""
        now = time.time()
        hit = _PRICE_CACHE.get(card_id)
        if hit and now - hit[0] < PRICE_CACHE_TTL:
            return hit[1], hit[2]

        url = FUTGG_PRICE_URL.format(card_id=card_id)
        price: Optional[int] = None
        extinct = False
        try:
            async with self.session.get(url) as r:
                if r.status != 200:
                    _PRICE_CACHE[card_id] = (now, None, False)
                    return None, False
                data = await r.json(content_type=None)
        except Exception:
            _PRICE_CACHE[card_id] = (now, None, False)
            return None, False

        root = (data or {}).get("data") or data or {}
        cur = root.get("currentPrice") or {}
        extinct = bool(cur.get("isExtinct", False))

        def to_int(v):
            try: return int(str(v).replace(",", "").strip())
            except: return None

        price = to_int(cur.get("price"))
        if price is None:
            # fallback to platform buckets
            prices = (data or {}).get("prices", {}) or root.get("prices", {}) or {}
            ps = prices.get("ps") or prices.get("playstation") or {}
            xb = prices.get("xbox") or {}
            for bucket in (ps, xb):
                for k in ("price","lowestBin","LCPrice","lowest","lowestPrice","current"):
                    if k in bucket:
                        price = to_int(bucket[k])
                        if price: break
                if price: break

        _PRICE_CACHE[card_id] = (now, price, extinct)
        return price, extinct

    # ---------------- DB enrichment ----------------
    async def _enrich_meta(self, rows: List[dict]) -> List[dict]:
        if not rows:
            return []
        ids = [int(x["card_id"]) for x in rows]
        try:
            async with self.db.acquire() as conn:
                dbrows = await conn.fetch(
                    """
                    SELECT card_id, name, rating, position, league, nation, club, image_url
                    FROM public.fut_players
                    WHERE card_id = ANY($1::bigint[])
                    """,
                    ids,
                )
        except Exception as e:
            logger.warning(f"[DB] enrich meta failed: {e}")
            dbrows = []
        meta = {int(r["card_id"]): dict(r) for r in dbrows}
        out: List[dict] = []
        for r in rows:
            cid = int(r["card_id"])
            m = meta.get(cid, {})
            name = m.get("name") or r.get("name_hint") or f"Card {cid}"
            out.append({
                "card_id": cid,
                "name": name,
                "rating": m.get("rating"),
                "position": m.get("position"),
                "league": m.get("league"),
                "nation": m.get("nation"),
                "club": m.get("club"),
                "image": m.get("image_url"),
                "percent": float(r["percent"]),
            })
        return out

    # ---------------- combine & de-dupe ----------------
    @staticmethod
    def _unique_by_card(rows: List[dict]) -> List[dict]:
        best: Dict[int, dict] = {}
        for r in rows:
            cid = int(r["card_id"])
            cur = best.get(cid)
            if not cur or abs(float(r["percent"])) > abs(float(cur["percent"])):
                best[cid] = r
        return list(best.values())

    async def _fetch_trending(self, kind: str, tf_num: str, limit: int) -> List[dict]:
        first_html = await self._momentum_page(tf_num, 1)
        if not first_html:
            return []
        last_page = self._parse_last_page_num(first_html)

        head = await self._page_items(tf_num, 1)
        tail = await self._page_items(tf_num, last_page) if last_page > 1 else []
        pool = self._unique_by_card(head + tail)

        if kind == "fallers":
            pool.sort(key=lambda x: float(x["percent"]))  # most negative first
        else:
            pool.sort(key=lambda x: float(x["percent"]), reverse=True)  # most positive first

        return pool[:limit]

    # ---------------- thumbnail sprite ----------------
    async def _build_sprite(self, items: List[dict]) -> Optional[discord.File]:
        if not PIL_OK:
            return None
        # collect up to 10 images (fallback to fut.gg card URL if missing)
        urls = []
        for it in items[:10]:
            if it.get("image"):
                urls.append(it["image"])
            else:
                # fut.gg card image not guaranteed in DB; skip if missing
                urls.append(None)

        # fetch images
        imgs: List[Optional[Image.Image]] = []
        for u in urls:
            if not u:
                imgs.append(None)
                continue
            try:
                async with self.session.get(u, headers=REQ_HEADERS) as r:
                    if r.status != 200:
                        imgs.append(None)
                        continue
                    b = await r.read()
                img = Image.open(io.BytesIO(b)).convert("RGBA")
                # fit to 88x112 (rough card ratio), keep aspect
                w, h = img.size
                scale = min(88 / max(1, w), 112 / max(1, h))
                img = img.resize((max(1,int(w*scale)), max(1,int(h*scale))), Image.LANCZOS)
                canvas = Image.new("RGBA", (88, 112), (0,0,0,0))
                cx = (88 - img.size[0]) // 2
                cy = (112 - img.size[1]) // 2
                canvas.paste(img, (cx, cy), img)
                imgs.append(canvas)
            except Exception:
                imgs.append(None)

        if not any(imgs):
            return None

        # stack vertically with small gaps; two columns if >5
        col = 2 if len(imgs) > 5 else 1
        rows = math.ceil(len(imgs) / col)
        gap = 6
        W = col * 88 + (col - 1) * gap
        H = rows * 112 + (rows - 1) * gap
        strip = Image.new("RGBA", (W, H), (0,0,0,0))

        for idx, im in enumerate(imgs):
            if im is None:
                continue
            c = idx // rows if col == 2 else 0
            r = idx % rows if col == 2 else idx
            x = c * (88 + gap)
            y = r * (112 + gap)
            strip.paste(im, (x, y), im)

        out = io.BytesIO()
        strip.save(out, format="PNG")
        out.seek(0)
        return discord.File(out, filename="trending_sprite.png")

    # ---------------- embed generation ----------------
    async def _embed_risers_fallers(self, kind: str, tf_num: str) -> Tuple[discord.Embed, Optional[discord.File]]:
        data = await self._fetch_trending(kind, tf_num, limit=10)
        enriched = await self._enrich_meta(data)

        # attach prices (Console)
        for e in enriched:
            price, extinct = await self._get_console_price(int(e["card_id"]))
            e["console_price"] = price
            e["extinct"] = bool(extinct)

        emoji = "📈" if kind == "risers" else "📉"
        tf_label = f"{tf_num}h"
        embed = discord.Embed(
            title=f"{emoji} Top 10 {'Risers' if kind=='risers' else 'Fallers'} – 🗓️ {tf_label}",
            color=discord.Color.green() if kind == "risers" else discord.Color.red(),
        )
        embed.set_footer(text=FOOTER)

        nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        left = right = ""
        for i, it in enumerate(enriched[:10]):
            price_txt = "Extinct" if it.get("extinct") else (f"{it['console_price']:,} 🪙" if it.get("console_price") else "N/A")
            rating = f" ({it['rating']})" if it.get("rating") else ""
            line = (
                f"**{nums[i]} [{it['name']}{rating}](https://www.fut.gg/players/26-{it['card_id']}/)**\n"
                f"💰 {price_txt}\n"
                f"{emoji} {it['percent']:+.2f}%\n\n"
            )
            if i < 5: left += line
            else: right += line

        embed.add_field(name="\u200b", value=left.strip() or "—", inline=True)
        embed.add_field(name="\u200b", value=right.strip() or "—", inline=True)

        sprite_file = await self._build_sprite(enriched)
        if sprite_file:
            embed.set_image(url="attachment://trending_sprite.png")
        return embed, sprite_file

    async def _embed_smart(self) -> Tuple[discord.Embed, Optional[discord.File]]:
        # flip between 6h and 24h
        f6  = await self._fetch_trending("fallers", "6", 50)
        r6  = await self._fetch_trending("risers",  "6", 50)
        f24 = await self._fetch_trending("fallers", "24", 50)
        r24 = await self._fetch_trending("risers",  "24", 50)

        f6m  = {int(x["card_id"]): float(x["percent"]) for x in f6}
        r6m  = {int(x["card_id"]): float(x["percent"]) for x in r6}
        f24m = {int(x["card_id"]): float(x["percent"]) for x in f24}
        r24m = {int(x["card_id"]): float(x["percent"]) for x in r24}

        smart_ids: set[int] = set()
        smart_map: Dict[int, Dict[str, float]] = {}
        for cid, p6 in r6m.items():
            if cid in f24m:
                smart_ids.add(cid)
                smart_map[cid] = {"chg6hPct": p6, "chg24hPct": f24m[cid]}
        for cid, p6 in f6m.items():
            if cid in r24m:
                smart_ids.add(cid)
                smart_map[cid] = {"chg6hPct": p6, "chg24hPct": r24m[cid]}

        rows = [{"card_id": cid, "percent": smart_map[cid]["chg6hPct"], "name_hint": None} for cid in smart_ids]
        enriched = await self._enrich_meta(rows)

        # attach prices
        for e in enriched:
            price, extinct = await self._get_console_price(int(e["card_id"]))
            e["console_price"] = price
            e["extinct"] = bool(extinct)
            cid = int(e["card_id"])
            e["trend"] = {"chg6hPct": smart_map[cid]["chg6hPct"], "chg24hPct": smart_map[cid]["chg24hPct"]}

        # order by magnitude of 6h move
        enriched.sort(key=lambda x: abs(x["trend"]["chg6hPct"]), reverse=True)
        enriched = enriched[:10]

        embed = discord.Embed(
            title="🧠 Smart Movers – flip between 6h and 24h",
            color=discord.Color.orange(),
        )
        embed.set_footer(text=FOOTER)

        nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        left = right = ""
        for i, it in enumerate(enriched):
            price_txt = "Extinct" if it.get("extinct") else (f"{it['console_price']:,} 🪙" if it.get("console_price") else "N/A")
            rating = f" ({it['rating']})" if it.get("rating") else ""
            line = (
                f"**{nums[i]} [{it['name']}{rating}](https://www.fut.gg/players/26-{it['card_id']}/)**\n"
                f"💰 {price_txt}\n"
                f"🕕 6h: {it['trend']['chg6hPct']:+.1f}%\n"
                f"🗓️ 24h: {it['trend']['chg24hPct']:+.1f}%\n\n"
            )
            if i < 5: left += line
            else: right += line

        embed.add_field(name="\u200b", value=left.strip() or "—", inline=True)
        embed.add_field(name="\u200b", value=right.strip() or "—", inline=True)

        sprite_file = await self._build_sprite(enriched)
        if sprite_file:
            embed.set_image(url="attachment://trending_sprite.png")
        return embed, sprite_file

    # ---------------- command surface ----------------
    @app_commands.command(
        name="trending",
        description="📊 Trending players from FUT.GG Momentum (Console prices; de-duped)"
    )
    @app_commands.describe(
        kind="Risers, Fallers, or Smart (6h↔24h flip)",
        timeframe="Only used for Risers/Fallers (6h/12h/24h)"
    )
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="📈 Risers", value="risers"),
            app_commands.Choice(name="📉 Fallers", value="fallers"),
            app_commands.Choice(name="🧠 Smart",  value="smart"),
        ],
        timeframe=[
            app_commands.Choice(name="🕕 6 Hours",  value="6h"),
            app_commands.Choice(name="🕛 12 Hours", value="12h"),
            app_commands.Choice(name="🗓️ 24 Hours", value="24h"),
        ]
    )
    async def trending(self, interaction: discord.Interaction,
                       kind: app_commands.Choice[str],
                       timeframe: app_commands.Choice[str] = None):
        await interaction.response.defer()
        tf_num = _norm_tf(timeframe.value if timeframe else "24h")

        if kind.value == "smart":
            embed, sprite = await self._embed_smart()
        else:
            embed, sprite = await self._embed_risers_fallers(kind.value, tf_num)

        view = discord.ui.View(timeout=None)
        tf_show = timeframe.value if timeframe else "24h"
        view.add_item(
            discord.ui.Button(label="🔁 Refresh",
                              style=discord.ButtonStyle.primary,
                              custom_id=f"refresh_{kind.value}_{tf_show}")
        )
        if sprite:
            await interaction.followup.send(embed=embed, file=sprite, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id")
            if cid and cid.startswith("refresh_"):
                _, kind, tf = cid.split("_", 2)
                await interaction.response.defer()
                if kind == "smart":
                    embed, sprite = await self._embed_smart()
                else:
                    embed, sprite = await self._embed_risers_fallers(kind, _norm_tf(tf))
                if sprite:
                    await interaction.edit_original_response(embed=embed, attachments=[sprite])
                else:
                    await interaction.edit_original_response(embed=embed)

    # ---------------- auto post ----------------
    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = time.strftime("%H:%M", time.gmtime())
        for guild_id, conf in load_config().items():
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
                    fallers_embed, fallers_sprite = await self._embed_risers_fallers("fallers", "24")
                    risers_embed,  risers_sprite  = await self._embed_risers_fallers("risers",  "24")
                    ping = f"<@&{conf['ping_role']}>" if conf.get("ping_role") else ""
                    if ping:
                        if fallers_sprite:
                            await channel.send(content=ping, embed=fallers_embed, file=fallers_sprite)
                        else:
                            await channel.send(content=ping, embed=fallers_embed)
                    else:
                        if fallers_sprite:
                            await channel.send(embed=fallers_embed, file=fallers_sprite)
                        else:
                            await channel.send(embed=fallers_embed)
                    if risers_sprite:
                        await channel.send(embed=risers_embed, file=risers_sprite)
                    else:
                        await channel.send(embed=risers_embed)

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