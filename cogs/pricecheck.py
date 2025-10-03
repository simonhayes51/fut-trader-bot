# cogs/pricecheck.py
from __future__ import annotations

import os
import io
import logging
import unicodedata
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone
from statistics import median

import discord
from discord.ext import commands
from discord import app_commands

import asyncpg
import aiohttp

# headless matplotlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

# ------------- Logging -------------
log = logging.getLogger("fut.pricecheck")
log.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s"))
log.addHandler(_handler)

# ------------- ENV / Constants -------------
PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL")

FUTGG_PRICE_API = "https://www.fut.gg/api/fut/player-prices"       # /{card_id}
FUTGG_DEF_API   = "https://www.fut.gg/api/fut/player-definition"   # /{card_id}
FUTGG_ASSET_CDN = "https://game-assets.fut.gg/cdn-cgi/image"

COLOR_MAIN = discord.Color.from_str("#39FF14") if hasattr(discord.Color, "from_str") else discord.Color.green()

def _normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode("ascii").lower().strip()

def _fmt_price(v: Optional[int]) -> str:
    try:
        return f"{int(v):,}"
    except Exception:
        return "N/A"

def _cdn_url(path: Optional[str], width: int) -> Optional[str]:
    if not path:
        return None
    return f"{FUTGG_ASSET_CDN}/quality=100,format=auto,width={width}/{path.lstrip('/')}"

def _pretty_iso(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso


# ------------- Cog -------------
class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.db: Optional[asyncpg.Pool] = None
        self.players: List[Dict] = []

    async def cog_load(self):
        # HTTP session
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Referer": "https://www.fut.gg/",
                },
            )
        # DB pool
        if not self.db:
            if not PLAYER_DATABASE_URL:
                raise RuntimeError("PLAYER_DATABASE_URL is not set")
            self.db = await asyncpg.create_pool(dsn=PLAYER_DATABASE_URL, min_size=1, max_size=6)
        await self._load_players()

    async def cog_unload(self):
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()

    # -------- DB --------
    async def _load_players(self):
        sql = """
        SELECT
            id, name, rating, position, club, nation, league, version, rarity,
            card_id, player_url, image_url, player_slug,
            nickname, first_name, last_name
        FROM public.fut_players;
        """
        async with self.db.acquire() as conn:
            rows = await conn.fetch(sql)

        self.players = []
        for r in rows:
            name = r["name"] or ""
            rating = r["rating"]
            self.players.append({
                "id": r["id"],
                "name": name,
                "rating": int(r["rating"]) if r["rating"] is not None else None,
                "position": r["position"],
                "club": r["club"],
                "nation": r["nation"],
                "league": r["league"],
                "version": r["version"],
                "rarity": r["rarity"],
                "card_id": str(r["card_id"]) if r["card_id"] is not None else None,
                "player_url": r["player_url"],
                "image_url": r["image_url"],
                "player_slug": r["player_slug"],
                "_label": f"{name} ({rating})" if rating is not None else name,
                "_value": f"{name} {rating}" if rating is not None else name,
                "_search": " ".join([
                    _normalize(name),
                    _normalize(str(rating or "")),
                    _normalize(r["player_slug"] or ""),
                    _normalize(f"{r['first_name'] or ''} {r['last_name'] or ''}"),
                    _normalize(r["nickname"] or ""),
                ]),
            })
        log.info(f"[DB] Loaded {len(self.players)} players")

    def _resolve_player(self, user_value: str) -> Optional[Dict]:
        uv = _normalize(user_value)
        for p in self.players:
            if _normalize(p["_value"]) == uv:
                return p
        hits = [p for p in self.players if uv in p["_search"]]
        if not hits:
            return None
        hits.sort(key=lambda x: (x.get("rating") or 0), reverse=True)
        return hits[0]

    # -------- FUT.GG: console price --------
    async def _futgg_console_price(self, card_id: Optional[str]) -> tuple[Optional[int], Optional[str], bool]:
        """
        Returns (console_price, updated_at_iso, is_extinct) from fut.gg.
        """
        if not card_id:
            return (None, None, False)

        url = f"{FUTGG_PRICE_API}/{card_id}"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    log.warning(f"[FUTGG] HTTP {resp.status} for {card_id}")
                    return (None, None, False)
                payload = await resp.json(content_type=None)
        except Exception as e:
            log.error(f"[FUTGG] fetch error {card_id}: {e}")
            return (None, None, False)

        root = payload.get("data") or payload
        cur = root.get("currentPrice") or {}
        price = cur.get("price")
        updated_at = cur.get("priceUpdatedAt")
        extinct = bool(cur.get("isExtinct", False))

        # fallback to platforms/prices if needed
        plat = root.get("platforms") or root.get("prices") or {}

        def to_int(v):
            try:
                return int(str(v).replace(",", "").strip())
            except Exception:
                return None

        def extract(node: dict | None) -> Optional[int]:
            if not isinstance(node, dict):
                return None
            for k in ("lowest", "lowestPrice", "current", "price", "l"):
                if k in node:
                    return to_int(node[k])
            for v in node.values():
                cand = to_int(v)
                if cand is not None:
                    return cand
            return None

        if price is None:
            ps = extract(plat.get("playstation") or plat.get("ps"))
            xb = extract(plat.get("xbox"))
            price = min([p for p in (ps, xb) if p is not None], default=None)

        return (to_int(price), updated_at, extinct)

    # -------- FUT.GG: hourly console series --------
    async def _futgg_console_series(self, card_id: Optional[str]) -> List[Tuple[datetime, int]]:
        if not card_id:
            return []
        url = f"{FUTGG_PRICE_API}/{card_id}"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return []
                payload = await resp.json(content_type=None)
        except Exception:
            return []

        root = payload.get("data") or payload
        auctions = root.get("completedAuctions") or []
        if not auctions:
            return []

        rows: List[Tuple[datetime, int]] = []
        for a in auctions:
            price = a.get("soldPrice")
            ts = a.get("soldDate")
            if not price or not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                continue
            dt = dt.replace(minute=0, second=0, microsecond=0)
            try:
                rows.append((dt, int(price)))
            except Exception:
                continue

        if not rows:
            return []

        buckets: Dict[datetime, List[int]] = {}
        for dt, p in rows:
            buckets.setdefault(dt, []).append(p)

        series = sorted((dt, int(median(vals))) for dt, vals in buckets.items())
        return series[-24:]

    # -------- Graph --------
    def _make_graph_png(self, points: List[Tuple[datetime, int]], name: str) -> Optional[io.BytesIO]:
        if len(points) < 2:
            return None
        t, y = zip(*points)
        fig, ax = plt.subplots(figsize=(6, 3))
        fig.patch.set_facecolor("#0D0D0D")
        ax.set_facecolor("#0D0D0D")

        ax.plot(t, y, marker="o", linestyle="-", color="#39FF14", markersize=3, linewidth=2)
        ax.set_title(f"{name} Console Price (24h)", color="white", fontsize=11, fontweight="bold")
        ax.set_xlabel("Time", color="white", fontsize=9)
        ax.set_ylabel("Coins", color="white", fontsize=9)

        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")
        for s in ax.spines.values():
            s.set_color("#555555")

        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        plt.xticks(rotation=45, color="white", fontsize=8)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v/1000)}K"))
        plt.yticks(color="white", fontsize=8)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=220, facecolor=fig.get_facecolor())
        buf.seek(0)
        plt.close(fig)
        return buf

    # -------- FUT.GG player definition (logos + card) --------
    async def _futgg_definition(self, card_id: Optional[str]) -> Dict[str, Optional[str]]:
        out = {
            "club": None, "nation": None, "league": None,
            "club_logo": None, "nation_logo": None, "league_logo": None,
            "card_image": None,
        }
        if not card_id:
            return out
        url = f"{FUTGG_DEF_API}/{card_id}"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return out
                payload = await resp.json(content_type=None)
        except Exception:
            return out

        d = (payload.get("data") or payload) or {}
        club = d.get("club") or {}
        nation = d.get("nation") or {}
        league = d.get("league") or {}

        out["club"] = club.get("name")
        out["nation"] = nation.get("name")
        out["league"] = league.get("name")

        out["club_logo"] = _cdn_url(club.get("imagePath"), 48)
        out["nation_logo"] = _cdn_url(nation.get("imagePath"), 48)
        out["league_logo"] = _cdn_url(league.get("imagePath"), 48)
        out["card_image"] = _cdn_url(d.get("futggCardImagePath"), 500)
        return out

    # -------- Slash command --------
    @app_commands.command(
        name="pricecheck",
        description="Console price from FUT.GG + logos + card image + hourly trend"
    )
    @app_commands.describe(player="Name + rating (e.g. 'Claudia Pina 86')")
    async def pricecheck(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()

        p = self._resolve_player(player)
        if not p:
            await interaction.followup.send("❌ Player not found in database.")
            return

        # fut.gg data
        console_price, updated_at, extinct = await self._futgg_console_price(p.get("card_id"))
        defs = await self._futgg_definition(p.get("card_id"))
        series = await self._futgg_console_series(p.get("card_id"))

        # Primary embed
        title = f"{p['name']} ({p.get('rating','?')})"
        embed = discord.Embed(title=title, color=COLOR_MAIN)

        # Card image (DB first, fut.gg fallback)
        thumb = p.get("image_url") or defs.get("card_image")
        if thumb:
            embed.set_thumbnail(url=thumb)

        # Price (Extinct or coins)
        if extinct:
            price_val = "**EXTINCT**"
        else:
            price_val = f"{_fmt_price(console_price)} 🪙"
        embed.add_field(name="🎮 Console Price", value=price_val, inline=True)

        # Position
        if p.get("position"):
            embed.add_field(name="🧩 Position", value=p["position"], inline=True)
        else:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Club / Nation / League (names)
        club = p.get("club") or defs.get("club") or "Unknown"
        nation = p.get("nation") or defs.get("nation") or "Unknown"
        league = p.get("league") or defs.get("league") or "Unknown"
        embed.add_field(name="🏟️ Club", value=club, inline=True)
        embed.add_field(name="🌍 Nation", value=nation, inline=True)
        embed.add_field(name="🏆 League", value=league, inline=True)

        # Logos: author icon (club) + footer icon (nation)
        if defs.get("club_logo"):
            embed.set_author(name="FUT.GG • Price Check", icon_url=defs["club_logo"])
        else:
            embed.set_author(name="FUT.GG • Price Check")

        footer_bits = ["Data: FUT.GG", "Created by www.futhub.co.uk"]
        pretty = _pretty_iso(updated_at)
        if pretty:
            footer_bits.insert(1, f"Updated: {pretty}")
        footer_text = " • ".join(footer_bits)

        if defs.get("nation_logo"):
            embed.set_footer(text=footer_text, icon_url=defs["nation_logo"])
        else:
            embed.set_footer(text=footer_text)

        # Secondary embed to show the league logo thumbnail (so all three logos appear)
        logos_embed = None
        if defs.get("league_logo"):
            logos_embed = discord.Embed(color=COLOR_MAIN)
            logos_embed.set_thumbnail(url=defs["league_logo"])
            logos_embed.add_field(name="🏆 League", value=league, inline=True)

        # Graph
        file = None
        if series:
            buf = self._make_graph_png(series, p["name"])
            if buf:
                file = discord.File(buf, filename="graph.png")
                embed.set_image(url="attachment://graph.png")

        # Send
        if logos_embed and file:
            await interaction.followup.send(embeds=[embed, logos_embed], file=file)
        elif logos_embed:
            await interaction.followup.send(embeds=[embed, logos_embed])
        elif file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    # -------- Autocomplete --------
    @pricecheck.autocomplete("player")
    async def _ac_player(self, interaction: discord.Interaction, current: str):
        q = _normalize(current)
        pool = self.players if not q else [p for p in self.players if q in p["_search"]]
        return [app_commands.Choice(name=p["_label"], value=p["_value"]) for p in pool[:25]]


async def setup(bot):
    await bot.add_cog(PriceCheck(bot))