# cogs/pricecheck.py
from __future__ import annotations

import os, io, json, re, logging, unicodedata
from typing import Optional, Dict, List, Tuple
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

import asyncpg
import aiohttp
import requests
from bs4 import BeautifulSoup

# headless matplotlib for servers
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

log = logging.getLogger("fut.pricecheck")
log.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s"))
log.addHandler(_handler)

# ---- ENV / constants ----
PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL")  # <<—— use this DB
FUTGG_SEASON = os.getenv("FUTGG_SEASON", "26")

FUTGG_PRICE_API = f"https://www.fut.gg/api/fut/player-prices/{FUTGG_SEASON}"      # /{card_id}
FUTGG_DEF_API   = f"https://www.fut.gg/api/fut/player-definition/{FUTGG_SEASON}"  # /{card_id}
FUTGG_ASSET_CDN = "https://game-assets.fut.gg/cdn-cgi/image"

COLOR_MAIN = discord.Color.from_str("#39FF14") if hasattr(discord.Color, "from_str") else discord.Color.green()

def _normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode("ascii").lower().strip()

def _fmt_price(v: Optional[int]) -> str:
    return f"{int(v):,}" if isinstance(v, (int, float)) else "N/A"

def _cdn_url(path: Optional[str], width: int) -> Optional[str]:
    if not path: return None
    return f"{FUTGG_ASSET_CDN}/quality=100,format=auto,width={width}/{path.lstrip('/')}"

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.db: Optional[asyncpg.Pool] = None
        self.players: List[Dict] = []

    async def cog_load(self):
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-GB,en;q=0.9"}
            )
        if not self.db:
            if not PLAYER_DATABASE_URL:
                raise RuntimeError("PLAYER_DATABASE_URL is not set")
            self.db = await asyncpg.create_pool(dsn=PLAYER_DATABASE_URL, min_size=1, max_size=6)
        await self._load_players()

    async def cog_unload(self):
        if self.session: await self.session.close()
        if self.db: await self.db.close()

    # -------- DB --------
    async def _load_players(self):
        sql = """
        SELECT id, name, rating, position, club, nation, league, version, rarity,
               card_id, player_url, image_url, player_slug, nickname, first_name, last_name
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
                "image_url": r["image_url"],  # your stored card image (if present)
                "player_slug": r["player_slug"],
                "_label": f"{name} ({rating})" if rating is not None else name,
                "_value": f"{name} {rating}" if rating is not None else name,
                "_search": " ".join([
                    _normalize(name),
                    _normalize(str(rating or "")),
                    _normalize(r["player_slug"] or ""),
                    _normalize(f"{r['first_name'] or ''} {r['last_name'] or ''}"),
                    _normalize(r["nickname"] or "")
                ])
            })
        log.info(f"[DB] Loaded {len(self.players)} players")

    def _resolve_player(self, key: str) -> Optional[Dict]:
        uv = _normalize(key)
        for p in self.players:
            if _normalize(p["_value"]) == uv:  # exact "Name Rating"
                return p
        hits = [p for p in self.players if uv in p["_search"]]
        return sorted(hits, key=lambda x: (x.get("rating") or 0), reverse=True)[0] if hits else None

    # -------- FUT.GG: prices + definition (logos, card art) --------
    async def _futgg_prices(self, card_id: Optional[str]) -> Dict[str, Optional[int]]:
        if not card_id: return {"ps": None, "xb": None, "pc": None}
        url = f"{FUTGG_PRICE_API}/{card_id}"
        try:
            async with self.session.get(url) as r:
                if r.status != 200: return {"ps": None, "xb": None, "pc": None}
                data = await r.json(content_type=None)
        except Exception as e:
            log.warning(f"[FUTGG prices] {e}"); return {"ps": None, "xb": None, "pc": None}

        def get(n: Optional[dict]) -> Optional[int]:
            if not isinstance(n, dict): return None
            for k in ("lowest","lowestPrice","current","price","l"):
                if k in n:
                    try: return int(str(n[k]).replace(",",""))
                    except: return None
            for v in n.values():
                try:
                    v2 = int(str(v).replace(",",""))
                    return v2
                except: pass
            return None

        p = data.get("prices") or data.get("platforms") or {}
        return {
            "ps": get(p.get("playstation") or p.get("ps") or p.get("ps5") or p.get("ps4")),
            "xb": get(p.get("xbox") or p.get("xb") or p.get("seriesx") or p.get("xboxone")),
            "pc": get(p.get("pc") or p.get("origin") or p.get("steam")),
        }

    async def _futgg_definition(self, card_id: Optional[str]) -> Dict[str, Optional[str]]:
        out = {"card_image": None, "club_logo": None, "nation_logo": None, "league_logo": None,
               "club": None, "nation": None, "league": None}
        if not card_id: return out
        url = f"{FUTGG_DEF_API}/{card_id}"
        try:
            async with self.session.get(url) as r:
                if r.status != 200: return out
                payload = await r.json(content_type=None)
        except Exception as e:
            log.info(f"[FUTGG def] {e}"); return out

        d = payload.get("data") or payload
        out["club"]   = (d.get("club")   or {}).get("name")
        out["nation"] = (d.get("nation") or {}).get("name")
        out["league"] = (d.get("league") or {}).get("name")
        out["club_logo"]   = _cdn_url((d.get("club")   or {}).get("imagePath"), 48)
        out["nation_logo"] = _cdn_url((d.get("nation") or {}).get("imagePath"), 48)
        out["league_logo"] = _cdn_url((d.get("league") or {}).get("imagePath"), 48)
        out["card_image"]  = _cdn_url(d.get("futggCardImagePath"), 500)
        return out

    # -------- FUTBIN hourly graph (your original logic) --------
    def _fetch_hourly_from_futbin(self, futbin_url: Optional[str]) -> List[Tuple[datetime,int]]:
        try:
            if not futbin_url or "futbin.com" not in futbin_url: return []
            res = requests.get(futbin_url, headers={"User-Agent":"Mozilla/5.0"}, timeout=12)
            soup = BeautifulSoup(res.text, "html.parser")
            price_data = []
            graph_divs = soup.find_all("div", class_="highcharts-graph-wrapper")
            if len(graph_divs) >= 2:
                raw = graph_divs[1].get("data-ps-data", "[]")
                try: price_data = json.loads(raw)
                except: pass
            if not price_data:
                for s in soup.find_all("script"):
                    if s.string and "highcharts" in s.string.lower():
                        m = re.search(r'data-ps-data="(\[.*?\])"', s.string)
                        if m:
                            try:
                                price_data = json.loads(m.group(1))
                                break
                            except: pass
            if not price_data: return []
            filtered = [(datetime.fromtimestamp(ts/1000), p) for ts,p in price_data if p and p>0]
            return filtered[-24:]
        except Exception as e:
            log.warning(f"[FUTBIN hourly] {e}")
            return []

    def _make_graph_png(self, points: List[Tuple[datetime,int]], name: str) -> Optional[io.BytesIO]:
        if len(points) < 2: return None
        t, y = zip(*points)
        fig, ax = plt.subplots(figsize=(6,3))
        fig.patch.set_facecolor("#0D0D0D"); ax.set_facecolor("#0D0D0D")
        ax.plot(t, y, marker="o", linestyle="-", color="#39FF14", markersize=3, linewidth=2)
        ax.set_title(f"{name} Price Trend (Today)", color="white", fontsize=11, fontweight="bold")
        ax.set_xlabel("Time", color="white", fontsize=9); ax.set_ylabel("Coins", color="white", fontsize=9)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")
        for s in ax.spines.values(): s.set_color("#555555")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M")); plt.xticks(rotation=45, color="white", fontsize=8)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v,_: f"{int(v/1000)}K")); plt.yticks(color="white", fontsize=8)
        plt.tight_layout()
        buf = io.BytesIO(); plt.savefig(buf, format="png", dpi=220, facecolor=fig.get_facecolor()); buf.seek(0); plt.close(fig)
        return buf

    # -------- Slash cmd --------
    @app_commands.command(name="pricecheck", description="Live FUT.GG price • logos • card image • FUTBIN hourly graph")
    @app_commands.describe(player="Name + rating (e.g. 'Claudia Pina 86')", platform="Show console (PS+XB) or PC")
    @app_commands.choices(platform=[
        app_commands.Choice(name="🎮 Console (PS+XB)", value="console"),
        app_commands.Choice(name="💻 PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        await interaction.response.defer()
        p = self._resolve_player(player)
        if not p:
            await interaction.followup.send("❌ Player not found in database.")
            return

        prices = await self._futgg_prices(p.get("card_id"))
        defs   = await self._futgg_definition(p.get("card_id"))

        # Title + card image (prefer DB image_url, fallback to FUT.GG card image)
        title = f"{p['name']} ({p.get('rating','?')})"
        card_img = p.get("image_url") or defs.get("card_image")

        # Build embed
        embed = discord.Embed(title=title, color=COLOR_MAIN)
        if card_img: embed.set_thumbnail(url=card_img)

        # Prices
        if platform.value == "pc":
            embed.add_field(name="💻 PC Price", value=f"{_fmt_price(prices['pc'])} 🪙", inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
        else:
            embed.add_field(name="🟦 PS Price", value=f"{_fmt_price(prices['ps'])} 🪙", inline=True)
            embed.add_field(name="🟩 Xbox Price", value=f"{_fmt_price(prices['xb'])} 🪙", inline=True)

        # Club / Nation / League — with logos as field icons (Discord can’t inline imgs in fields, so we show names and place a logo in author/footer)
        club   = p.get("club")   or defs.get("club")   or "Unknown"
        nation = p.get("nation") or defs.get("nation") or "Unknown"
        league = p.get("league") or defs.get("league") or "Unknown"
        embed.add_field(name="🏟️ Club", value=club, inline=True)
        embed.add_field(name="🌍 Nation", value=nation, inline=True)
        embed.add_field(name="🏆 League", value=league, inline=True)
        if defs.get("club_logo"):
            embed.set_author(name="FUT.GG • Price Check", icon_url=defs["club_logo"])
        if defs.get("nation_logo"):
            embed.set_footer(text="Data: FUT.GG • Graph: FUTBIN", icon_url=defs["nation_logo"])

        # FUTBIN hourly graph if you have a futbin URL in DB
        futbin_url = p.get("player_url")
        graph_file = None
        if futbin_url and "futbin.com" in futbin_url:
            pts = self._fetch_hourly_from_futbin(futbin_url)
            if pts:
                graph_buf = self._make_graph_png(pts, p["name"])
                if graph_buf:
                    graph_file = discord.File(graph_buf, filename="graph.png")
                    embed.set_image(url="attachment://graph.png")

        # Link button(s)
        view = discord.ui.View(timeout=None)
        if futbin_url and "futbin.com" in futbin_url:
            view.add_item(discord.ui.Button(label="Open on FUTBIN", style=discord.ButtonStyle.link, url=futbin_url))

        if graph_file:
            await interaction.followup.send(embed=embed, file=graph_file, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

    # -------- Autocomplete --------
    @pricecheck.autocomplete("player")
    async def ac_player(self, interaction: discord.Interaction, current: str):
        q = _normalize(current)
        pool = self.players if not q else [p for p in self.players if q in p["_search"]]
        return [app_commands.Choice(name=p["_label"], value=p["_value"]) for p in pool[:25]]

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))