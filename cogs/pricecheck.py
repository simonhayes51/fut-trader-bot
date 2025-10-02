# cogs/pricecheck.py
from __future__ import annotations

import os
import json
import logging
import re
import unicodedata
from typing import Optional, Dict, List, Tuple

import discord
from discord.ext import commands
from discord import app_commands

import asyncpg
import aiohttp
import requests
from bs4 import BeautifulSoup

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import io
from datetime import datetime

# ================= Logging =================
log = logging.getLogger("futhub.pricecheck")
log.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s"))
log.addHandler(_handler)

# ================= Config =================
DATABASE_URL = os.getenv("DATABASE_URL")

PLAYERS_TABLE = "public.fut_players"
# your columns: id, name, rating, position, club, nation, league, version, rarity,
# card_id, added_at, updated_at, player_url, card_ids, image_url, player_slug,
# created_at, price, price_num, price_updated_at, first_name, last_name, nickname, altposition

# FUT.GG season: "26" (FC26), "25" (FC25)
FUTGG_SEASON = os.getenv("FUTGG_SEASON", "26")
FUTGG_PRICE_API = f"https://www.fut.gg/api/fut/player-prices/{FUTGG_SEASON}"          # /{card_id}
FUTGG_DEF_API   = f"https://www.fut.gg/api/fut/player-definition/{FUTGG_SEASON}"      # /{card_id}
FUTGG_ASSET_CDN = "https://game-assets.fut.gg/cdn-cgi/image"

# Branding (optional)
BRAND_ICON_URL   = os.getenv("FUTHUB_BRAND_ICON_URL")   # author icon
BRAND_BANNER_URL = os.getenv("FUTHUB_BRAND_BANNER_URL") # big banner (occupies embed.image slot)

# Theme
COLOR_MAIN = discord.Color.from_str("#39FF14") if hasattr(discord.Color, "from_str") else discord.Color.green()

# Emojis/labels
EMOJI_PS = "🟦 PS"
EMOJI_XB = "🟩 XB"
EMOJI_PC = "💻 PC"
EMOJI_COIN = "🪙"

# ================= Helpers =================
def _normalize(s: str) -> str:
    """Accent-insensitive lowercase."""
    if not s:
        return ""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower().strip()

def _fmt_price(v: Optional[int]) -> str:
    if v is None:
        return "N/A"
    try: return f"{int(v):,}"
    except Exception: return str(v)

def _coin_row(ps: Optional[int], xb: Optional[int], pc: Optional[int], platform: str) -> Tuple[str, str]:
    if platform == "pc":
        return "PC", f"{_fmt_price(pc)} {EMOJI_COIN}"
    return "Console", f"{EMOJI_PS} {_fmt_price(ps)}  •  {EMOJI_XB} {_fmt_price(xb)}  {EMOJI_COIN}"

def _cdn_url(path: Optional[str], width: int) -> Optional[str]:
    # FUT.GG returns relative paths like /fut/players/images/....
    # Build resized auto-format URLs via their CDN.
    if not path: return None
    p = path.lstrip("/")
    return f"{FUTGG_ASSET_CDN}/quality=100,format=auto,width={width}/{p}"

def _parse_futbin_id_from_url(url: Optional[str]) -> Optional[str]:
    if not url or "futbin.com" not in url:
        return None
    m = re.search(r"/players/(\d+)", url)
    return m.group(1) if m else None

# ================= Cog =================
class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.http: Optional[aiohttp.ClientSession] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        self.players: List[Dict] = []  # cache for autocomplete/lookup

    # ---------- lifecycle ----------
    async def cog_load(self):
        if not self.http:
            self.http = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Referer": "https://www.fut.gg/",
                },
            )
        if not self.db_pool:
            if not DATABASE_URL:
                raise RuntimeError("DATABASE_URL is not set")
            self.db_pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=6)
        await self._load_players()

    async def cog_unload(self):
        if self.http:
            await self.http.close()
        if self.db_pool:
            await self.db_pool.close()

    # ---------- DB ----------
    async def _load_players(self):
        query = f"""
            SELECT
                id, name, rating, position, club, nation, league, version, rarity,
                card_id, player_url, image_url, player_slug, price, price_num,
                price_updated_at, first_name, last_name, nickname, altposition, card_ids, updated_at
            FROM {PLAYERS_TABLE};
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        self.players = []
        for r in rows:
            name = r["name"] or ""
            rating = r["rating"]
            self.players.append({
                "id": r["id"],
                "name": name,
                "name_norm": _normalize(name),
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
                "price": r["price"],
                "price_num": r["price_num"],
                "price_updated_at": r["price_updated_at"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "nickname": r["nickname"],
                "altposition": r["altposition"],
                "card_ids": r["card_ids"],
                "updated_at": r["updated_at"],
                "_label": f"{name} ({rating})" if rating is not None else name,
                "_value": f"{name} {rating}" if rating is not None else name,
                "_search": " ".join(filter(None, [
                    _normalize(name),
                    _normalize(str(rating or "")),
                    _normalize(r["nickname"] or ""),
                    _normalize(f"{r['first_name'] or ''} {r['last_name'] or ''}"),
                    _normalize(r["player_slug"] or ""),
                ])),
            })
        log.info(f"[LOAD] Cached {len(self.players)} players for /pricecheck")

    def _resolve_player(self, user_value: str) -> Optional[Dict]:
        uv = _normalize(user_value)
        # exact
        for p in self.players:
            if _normalize(p["_value"]) == uv:
                return p
        # contains
        hits = [p for p in self.players if uv in p["_search"]]
        if not hits: return None
        hits.sort(key=lambda x: (x.get("rating") or 0), reverse=True)
        return hits[0]

    # ---------- FUT.GG ----------
    async def _futgg_prices(self, card_id: Optional[str]) -> Dict[str, Optional[int]]:
        if not card_id:
            return {"ps": None, "xb": None, "pc": None}
        url = f"{FUTGG_PRICE_API}/{card_id}"

        def to_int(v):
            try: return int(str(v).replace(",", "").strip())
            except Exception: return None

        try:
            async with self.http.get(url) as resp:
                if resp.status != 200:
                    log.warning(f"[FUTGG] prices {card_id} -> HTTP {resp.status}")
                    return {"ps": None, "xb": None, "pc": None}
                data = await resp.json(content_type=None)
        except Exception as e:
            log.error(f"[FUTGG] prices error {card_id}: {e}")
            return {"ps": None, "xb": None, "pc": None}

        ps = xb = pc = None
        try:
            prices = data.get("prices") or data.get("platforms") or {}
            ps_node = prices.get("playstation") or prices.get("ps") or prices.get("ps5") or prices.get("ps4")
            xb_node = prices.get("xbox") or prices.get("xb") or prices.get("seriesx") or prices.get("xboxone")
            pc_node = prices.get("pc") or prices.get("origin") or prices.get("steam")

            def extract(n):
                if not isinstance(n, dict): return None
                for k in ("lowest", "lowestPrice", "lowest_price", "current", "price", "l"):
                    if k in n:
                        return to_int(n[k])
                for v in n.values():
                    cand = to_int(v)
                    if cand: return cand
                return None

            ps = extract(ps_node)
            xb = extract(xb_node)
            pc = extract(pc_node)
        except Exception as e:
            log.error(f"[FUTGG] prices parse {card_id}: {e}")

        return {"ps": ps, "xb": xb, "pc": pc}

    async def _futgg_definition(self, card_id: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Resolve logos & card image via FUT.GG definition.
        Returns: {
            'card_image', 'club_logo', 'nation_logo', 'league_logo',
            'club_name', 'nation_name', 'league_name'
        }
        """
        out = {
            "card_image": None, "club_logo": None, "nation_logo": None, "league_logo": None,
            "club_name": None, "nation_name": None, "league_name": None
        }
        if not card_id:
            return out
        url = f"{FUTGG_DEF_API}/{card_id}"
        try:
            async with self.http.get(url) as resp:
                if resp.status != 200:
                    log.info(f"[FUTGG] def {card_id} -> HTTP {resp.status}")
                    return out
                payload = await resp.json(content_type=None)
        except Exception as e:
            log.info(f"[FUTGG] def error {card_id}: {e}")
            return out

        data = payload.get("data") or payload

        try:
            out["club_name"]   = (data.get("club") or {}).get("name")
            out["nation_name"] = (data.get("nation") or {}).get("name")
            out["league_name"] = (data.get("league") or {}).get("name")

            out["club_logo"]   = _cdn_url((data.get("club") or {}).get("imagePath"),   48)
            out["nation_logo"] = _cdn_url((data.get("nation") or {}).get("imagePath"), 48)
            out["league_logo"] = _cdn_url((data.get("league") or {}).get("imagePath"), 48)
            out["card_image"]  = _cdn_url(data.get("futggCardImagePath"), 500)
        except Exception:
            pass
        return out

    # ---------- FUTBIN hourly graph (from your script) ----------
    def _fetch_hourly_price_data(self, futbin_url: Optional[str]) -> List[Tuple[datetime, int]]:
        """Scrape FUTBIN hourly PS graph from player page."""
        try:
            if not futbin_url or "futbin.com" not in futbin_url:
                return []
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(futbin_url, headers=headers, timeout=12)
            soup = BeautifulSoup(res.text, "html.parser")

            graph_divs = soup.find_all("div", class_="highcharts-graph-wrapper")
            price_data = []

            if len(graph_divs) >= 2:
                hourly_graph = graph_divs[1]
                data_ps_raw = hourly_graph.get("data-ps-data", "[]")
                try:
                    price_data = json.loads(data_ps_raw)
                except json.JSONDecodeError:
                    pass

            if not price_data:
                for script in soup.find_all("script"):
                    if script.string and "highcharts" in script.string.lower():
                        m = re.search(r'data-ps-data="(\[.*?\])"', script.string)
                        if m:
                            try:
                                price_data = json.loads(m.group(1))
                                break
                            except json.JSONDecodeError:
                                continue

            if not price_data:
                return []

            filtered = [
                (datetime.fromtimestamp(ts / 1000), price)
                for ts, price in price_data if price and price > 0
            ]
            return filtered[-24:]
        except Exception as e:
            log.warning(f"[FUTBIN hourly] {e}")
            return []

    def _make_graph_png(self, price_data: List[Tuple[datetime, int]], player_name: str) -> Optional[io.BytesIO]:
        if len(price_data) < 2:
            return None
        try:
            timestamps, prices = zip(*price_data)
            fig, ax = plt.subplots(figsize=(6, 3))
            fig.patch.set_facecolor("#0D0D0D")
            ax.set_facecolor("#0D0D0D")

            ax.plot(timestamps, prices, marker="o", linestyle="-", color="#39FF14", markersize=3, linewidth=2)
            ax.set_title(f"{player_name} Price Trend (Today)", color="white", fontsize=11, fontweight="bold")
            ax.set_xlabel("Time", color="white", fontsize=9)
            ax.set_ylabel("Coins", color="white", fontsize=9)
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")
            for spine in ax.spines.values():
                spine.set_color("#555555")
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.xticks(rotation=45, color="white", fontsize=8)
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K"))
            plt.yticks(color="white", fontsize=8)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=220, facecolor=fig.get_facecolor())
            buf.seek(0)
            plt.close(fig)
            return buf
        except Exception as e:
            log.warning(f"[Graph] {e}")
            return None

    # ---------- Embed builder ----------
    async def _build_embed(
        self,
        player: Dict,
        platform: str,
        include_graph: bool = True
    ) -> Tuple[discord.Embed, Optional[discord.File], Optional[discord.Embed]]:
        """
        Returns: (main_embed, graph_file_or_None, logos_embed_or_None)
        main_embed uses player card image as thumbnail.
        A small second embed carries the league logo as thumbnail so we show all three logos.
        """
        prices = await self._futgg_prices(player.get("card_id"))
        defs = await self._futgg_definition(player.get("card_id"))

        # Decide images
        card_img = player.get("image_url") or defs.get("card_image")
        club_logo = defs.get("club_logo")
        nation_logo = defs.get("nation_logo")
        league_logo = defs.get("league_logo")

        # Title
        title = f"{player['name']} ({player['rating']})" if player.get("rating") else player['name']

        embed = discord.Embed(title=title, color=COLOR_MAIN)
        # Author: brand first, with club logo as icon if set; else brand icon
        if BRAND_ICON_URL:
            embed.set_author(name="FUTHub • Price Check", icon_url=BRAND_ICON_URL)
        elif club_logo:
            embed.set_author(name="FUTHub • Price Check", icon_url=club_logo)
        else:
            embed.set_author(name="FUTHub • Price Check")

        # Thumbnail: player card
        if card_img:
            embed.set_thumbnail(url=card_img)

        # Optional banner
        if BRAND_BANNER_URL:
            embed.set_image(url=BRAND_BANNER_URL)

        # Price fields
        plat_name, value = _coin_row(prices["ps"], prices["xb"], prices["pc"], platform)
        embed.add_field(name="Platform", value=plat_name, inline=True)
        embed.add_field(name="Price", value=value, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Meta fields — with tiny icon hints in names
        if player.get("position"):
            embed.add_field(name="🧩 Position", value=f"`{player['position']}`", inline=True)
        if player.get("club"):
            embed.add_field(name="🏟️ Club", value=player["club"], inline=True)
        elif defs.get("club_name"):
            embed.add_field(name="🏟️ Club", value=defs["club_name"], inline=True)
        if player.get("nation") or defs.get("nation_name"):
            embed.add_field(name="🌍 Nation", value=player.get("nation") or defs.get("nation_name"), inline=True)
        if player.get("league") or defs.get("league_name"):
            embed.add_field(name="🏆 League", value=player.get("league") or defs.get("league_name"), inline=True)
        if player.get("version") or player.get("rarity"):
            ver = player.get("version") or ""
            rar = player.get("rarity") or ""
            embed.add_field(name="Card", value=(ver if ver else "") + (f" • {rar}" if rar else ""), inline=True)

        # Footer with nation logo if present
        if nation_logo:
            embed.set_footer(text=f"Card ID: {player.get('card_id') or 'N/A'} • Source: FUT.GG", icon_url=nation_logo)
        else:
            embed.set_footer(text=f"Card ID: {player.get('card_id') or 'N/A'} • Source: FUT.GG")

        # Logos embed (league as thumbnail so we show all 3 logos across both embeds)
        logos_embed = None
        if league_logo or club_logo or nation_logo:
            logos_embed = discord.Embed(color=COLOR_MAIN)
            if league_logo:
                logos_embed.set_thumbnail(url=league_logo)
            # show Club / Nation again but with icons in field values as links (Discord won’t inline images in fields)
            c_name = player.get("club") or defs.get("club_name") or "Unknown"
            n_name = player.get("nation") or defs.get("nation_name") or "Unknown"
            l_name = player.get("league") or defs.get("league_name") or "Unknown"
            logos_embed.add_field(name="🏟️ Club", value=c_name, inline=True)
            logos_embed.add_field(name="🌍 Nation", value=n_name, inline=True)
            logos_embed.add_field(name="🏆 League", value=l_name, inline=True)

        # Hourly graph from FUTBIN if available and no banner occupying embed.image
        graph_file = None
        if include_graph and not BRAND_BANNER_URL:
            futbin_url = player.get("player_url")
            hourly = self._fetch_hourly_price_data(futbin_url)
            if hourly:
                buf = self._make_graph_png(hourly, player["name"])
                if buf:
                    graph_file = discord.File(buf, filename="graph.png")
                    embed.set_image(url="attachment://graph.png")

        return embed, graph_file, logos_embed

    # ---------- Buttons ----------
    def _build_view(self, card_id: str, platform: str, futbin_url: Optional[str]) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="PS",   style=discord.ButtonStyle.secondary,
                                        custom_id=f"pc_ps_{card_id}", emoji="🟦"))
        view.add_item(discord.ui.Button(label="Xbox", style=discord.ButtonStyle.secondary,
                                        custom_id=f"pc_xb_{card_id}", emoji="🟩"))
        view.add_item(discord.ui.Button(label="PC",   style=discord.ButtonStyle.secondary,
                                        custom_id=f"pc_pc_{card_id}", emoji="💻"))
        view.add_item(discord.ui.Button(label="Refresh", style=discord.ButtonStyle.primary,
                                        custom_id=f"pc_rf_{card_id}", emoji="🔁"))
        if futbin_url and "futbin.com" in futbin_url:
            view.add_item(discord.ui.Button(label="FUTBIN", style=discord.ButtonStyle.link, url=futbin_url))
        return view

    # ---------- Slash command ----------
    @app_commands.command(name="pricecheck", description="FUTHub Price Check (FUT.GG live prices + club/nation/league logos + optional FUTBIN graph)")
    @app_commands.describe(player="Type player name", platform="Show Console (PS+XB) or PC")
    @app_commands.choices(platform=[
        app_commands.Choice(name="🎮 Console", value="console"),
        app_commands.Choice(name="💻 PC", value="pc"),
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        await interaction.response.defer()
        p = self._resolve_player(player)
        if not p:
            await interaction.followup.send("❌ Player not found.")
            return

        plat = platform.value  # "console" or "pc"
        embed, graph_file, logos_embed = await self._build_embed(p, plat)
        view = self._build_view(p.get("card_id") or "0", plat, p.get("player_url"))

        files = [graph_file] if graph_file else None
        if logos_embed:
            if files:
                await interaction.followup.send(embeds=[embed, logos_embed], files=files, view=view)
            else:
                await interaction.followup.send(embeds=[embed, logos_embed], view=view)
        else:
            if files:
                await interaction.followup.send(embed=embed, file=graph_file, view=view)
            else:
                await interaction.followup.send(embed=embed, view=view)

    # ---------- Autocomplete ----------
    @pricecheck.autocomplete("player")
    async def _ac_player(self, interaction: discord.Interaction, current: str):
        try:
            q = _normalize(current)
            pool = self.players if not q else [p for p in self.players if q in p["_search"]]
            pool = pool[:25]
            return [app_commands.Choice(name=p["_label"], value=p["_value"]) for p in pool]
        except Exception as e:
            log.error(f"[AC] {e}")
            return []

    # ---------- Button interactions ----------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        cid = (interaction.data or {}).get("custom_id") or ""
        if not cid.startswith("pc_"):
            return

        try:
            _, action, card_id = cid.split("_", 2)
        except ValueError:
            return

        # Find player by card_id in cache
        player = next((p for p in self.players if (p.get("card_id") or "") == card_id), None)
        if not player:
            return

        await interaction.response.defer()
        if action in ("ps", "xb"):
            embed, graph_file, logos_embed = await self._build_embed(player, "console", include_graph=False)
        elif action == "pc":
            embed, graph_file, logos_embed = await self._build_embed(player, "pc", include_graph=False)
        elif action == "rf":
            # keep current platform from existing embed’s field
            try:
                msg = await interaction.channel.fetch_message(interaction.message.id)
                plat_field = next((f for f in msg.embeds[0].fields if f.name == "Platform"), None)
                plat = "pc" if (plat_field and "PC" in (plat_field.value or "")) else "console"
            except Exception:
                plat = "console"
            embed, graph_file, logos_embed = await self._build_embed(player, plat, include_graph=False)
        else:
            return

        view = self._build_view(card_id, "pc" if action == "pc" else "console", player.get("player_url"))

        # Edit original with possibly two embeds
        if logos_embed:
            await interaction.edit_original_response(embeds=[embed, logos_embed], view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)

# ========= setup =========
async def setup(bot):
    await bot.add_cog(PriceCheck(bot))