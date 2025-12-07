import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncpg
import os
import logging
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("fut.playercompare")

PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL")
FUTGG_PRICE_API = "https://www.fut.gg/api/fut/player-prices"
FUTGG_DEF_API = "https://www.fut.gg/api/fut/player-definition"

def _normalize(s: str) -> str:
    """Normalize string for searching"""
    import unicodedata
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode("ascii").lower().strip()

class PlayerCompare(commands.Cog):
    """Compare two players side-by-side with stats and prices"""

    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.db: Optional[asyncpg.Pool] = None
        self.players: List[Dict] = []

    async def cog_load(self):
        """Initialize resources"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Referer": "https://www.fut.gg/",
                },
            )

        if not self.db and PLAYER_DATABASE_URL:
            self.db = await asyncpg.create_pool(dsn=PLAYER_DATABASE_URL, min_size=1, max_size=4)
            await self._load_players()

    async def cog_unload(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()

    async def _load_players(self):
        """Load players from database"""
        sql = """
        SELECT id, name, rating, position, club, nation, league, version, rarity,
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
        log.info(f"[PlayerCompare] Loaded {len(self.players)} players")

    def _resolve_player(self, user_value: str) -> Optional[Dict]:
        """Find player by name and rating"""
        uv = _normalize(user_value)
        for p in self.players:
            if _normalize(p["_value"]) == uv:
                return p
        hits = [p for p in self.players if uv in p["_search"]]
        if not hits:
            return None
        hits.sort(key=lambda x: (x.get("rating") or 0), reverse=True)
        return hits[0]

    async def _get_console_price(self, card_id: Optional[str]) -> Optional[int]:
        """Get console price from FUT.GG"""
        if not card_id:
            return None

        url = f"{FUTGG_PRICE_API}/{card_id}"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json(content_type=None)
        except Exception as e:
            log.error(f"[PlayerCompare] Price fetch error: {e}")
            return None

        root = payload.get("data") or payload
        cur = root.get("currentPrice") or {}
        price = cur.get("price")

        if price is None:
            plat = root.get("platforms") or root.get("prices") or {}
            ps = plat.get("playstation") or plat.get("ps") or {}
            price = ps.get("lowest") or ps.get("price")

        try:
            return int(str(price).replace(",", "").strip())
        except:
            return None

    async def _get_player_stats(self, card_id: Optional[str]) -> Dict:
        """Get player stats from FUT.GG definition"""
        stats = {
            "pace": None, "shooting": None, "passing": None,
            "dribbling": None, "defending": None, "physical": None
        }

        if not card_id:
            return stats

        url = f"{FUTGG_DEF_API}/{card_id}"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return stats
                payload = await resp.json(content_type=None)
        except:
            return stats

        d = (payload.get("data") or payload) or {}
        attributes = d.get("attributes") or {}

        # Map common attribute names
        stats["pace"] = attributes.get("pace") or attributes.get("PAC")
        stats["shooting"] = attributes.get("shooting") or attributes.get("SHO")
        stats["passing"] = attributes.get("passing") or attributes.get("PAS")
        stats["dribbling"] = attributes.get("dribbling") or attributes.get("DRI")
        stats["defending"] = attributes.get("defending") or attributes.get("DEF")
        stats["physical"] = attributes.get("physical") or attributes.get("PHY")

        return stats

    @app_commands.command(name="compare", description="⚖️ Compare two FC26 players side-by-side")
    @app_commands.describe(
        player1="First player (name + rating)",
        player2="Second player (name + rating)"
    )
    async def compare(self, interaction: discord.Interaction, player1: str, player2: str):
        """Compare two players"""
        await interaction.response.defer()

        p1 = self._resolve_player(player1)
        p2 = self._resolve_player(player2)

        if not p1:
            await interaction.followup.send(f"❌ Player 1 '{player1}' not found in database.")
            return
        if not p2:
            await interaction.followup.send(f"❌ Player 2 '{player2}' not found in database.")
            return

        # Fetch prices and stats
        price1 = await self._get_console_price(p1.get("card_id"))
        price2 = await self._get_console_price(p2.get("card_id"))
        stats1 = await self._get_player_stats(p1.get("card_id"))
        stats2 = await self._get_player_stats(p2.get("card_id"))

        # Create comparison embed
        embed = discord.Embed(
            title="⚖️ Player Comparison",
            description=f"**{p1['name']}** vs **{p2['name']}**",
            color=discord.Color.blue()
        )

        # Ratings
        rating_text = f"**{p1.get('rating', '?')}** OVR"
        embed.add_field(name=f"📊 {p1['name']}", value=rating_text, inline=True)
        embed.add_field(name="VS", value="⚔️", inline=True)
        rating_text2 = f"**{p2.get('rating', '?')}** OVR"
        embed.add_field(name=f"📊 {p2['name']}", value=rating_text2, inline=True)

        # Positions
        embed.add_field(name="Position", value=p1.get("position", "N/A"), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Position", value=p2.get("position", "N/A"), inline=True)

        # Prices
        price_text1 = f"{price1:,} 🪙" if price1 else "N/A"
        price_text2 = f"{price2:,} 🪙" if price2 else "N/A"

        embed.add_field(name="💰 Price", value=price_text1, inline=True)

        # Price comparison
        if price1 and price2:
            diff = price1 - price2
            if abs(diff) < 1000:
                comp = "≈"
            elif diff > 0:
                comp = f"📈 +{diff:,}"
            else:
                comp = f"📉 {diff:,}"
            embed.add_field(name="Difference", value=comp, inline=True)
        else:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="💰 Price", value=price_text2, inline=True)

        # Stats comparison
        stat_names = {
            "pace": "⚡ Pace",
            "shooting": "🎯 Shooting",
            "passing": "🎯 Passing",
            "dribbling": "⚽ Dribbling",
            "defending": "🛡️ Defending",
            "physical": "💪 Physical"
        }

        for stat_key, stat_label in stat_names.items():
            s1 = stats1.get(stat_key)
            s2 = stats2.get(stat_key)

            val1 = f"{s1}" if s1 is not None else "?"
            val2 = f"{s2}" if s2 is not None else "?"

            # Add winner indicator
            if s1 is not None and s2 is not None:
                if s1 > s2:
                    val1 = f"**{s1}** ✅"
                elif s2 > s1:
                    val2 = f"**{s2}** ✅"
                else:
                    val1 = f"{s1} ➖"
                    val2 = f"{s2} ➖"

            embed.add_field(name=stat_label, value=val1, inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name=stat_label, value=val2, inline=True)

        # League & Nation
        embed.add_field(name="🏆 League", value=p1.get("league", "Unknown"), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="🏆 League", value=p2.get("league", "Unknown"), inline=True)

        embed.add_field(name="🌍 Nation", value=p1.get("nation", "Unknown"), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="🌍 Nation", value=p2.get("nation", "Unknown"), inline=True)

        # Value for money
        if price1 and price2 and p1.get("rating") and p2.get("rating"):
            coins_per_rating1 = price1 / p1["rating"]
            coins_per_rating2 = price2 / p2["rating"]

            vfm_text = f"**{int(coins_per_rating1):,}** 🪙/rating"
            if coins_per_rating1 < coins_per_rating2:
                vfm_text += " ✅"

            vfm_text2 = f"**{int(coins_per_rating2):,}** 🪙/rating"
            if coins_per_rating2 < coins_per_rating1:
                vfm_text2 += " ✅"

            embed.add_field(name="💎 Value", value=vfm_text, inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name="💎 Value", value=vfm_text2, inline=True)

        embed.set_footer(text="FC26 • Player Comparison Tool • Data from FUT.GG")

        await interaction.followup.send(embed=embed)

    @compare.autocomplete("player1")
    @compare.autocomplete("player2")
    async def _ac_player(self, interaction: discord.Interaction, current: str):
        """Autocomplete for player search"""
        q = _normalize(current)
        pool = self.players if not q else [p for p in self.players if q in p["_search"]]
        return [app_commands.Choice(name=p["_label"], value=p["_value"]) for p in pool[:25]]

async def setup(bot):
    await bot.add_cog(PlayerCompare(bot))
