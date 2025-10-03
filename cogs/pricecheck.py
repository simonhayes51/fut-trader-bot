import os
import discord
import logging
import asyncpg
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from datetime import datetime

log = logging.getLogger("fut-pricecheck")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL")
FUTGG_SEASON = "26"
FUTGG_PRICE_URL = f"https://www.fut.gg/api/fut/player-prices/{FUTGG_SEASON}"

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_pool: asyncpg.Pool | None = None
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        if not self.db_pool:
            if not PLAYER_DATABASE_URL:
                raise RuntimeError("PLAYER_DATABASE_URL is not set")
            self.db_pool = await asyncpg.create_pool(dsn=PLAYER_DATABASE_URL, min_size=1, max_size=6)
        if not self.session:
            self.session = aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"})

    async def cog_unload(self):
        if self.db_pool:
            await self.db_pool.close()
        if self.session:
            await self.session.close()

    # --- DB lookup ---
    async def lookup_player(self, query: str):
        sql = """
            SELECT id, name, rating, club, nation, league, version, rarity,
                   card_id, image_url, player_slug
            FROM fut_players
            WHERE LOWER(name || ' ' || rating::text) = LOWER($1)
            LIMIT 1
        """
        try:
            row = await self.db_pool.fetchrow(sql, query.strip())
            return dict(row) if row else None
        except Exception as e:
            log.error(f"[DB ERROR] {e}")
            return None

    # --- FUT.GG prices ---
    async def fetch_prices(self, card_id: str):
        try:
            url = f"{FUTGG_PRICE_URL}/{card_id}"
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()
            return data.get("prices") or {}
        except Exception as e:
            log.error(f"[FUT.GG ERROR] {e}")
            return {}

    # --- FUT.GG price history (auctions) ---
    async def fetch_price_history(self, card_id: str):
        try:
            url = f"{FUTGG_PRICE_URL}/{card_id}"
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
            auctions = data.get("completedAuctions") or []
            points = [(datetime.fromisoformat(a["soldDate"].replace("Z", "+00:00")), a["soldPrice"])
                      for a in auctions if a.get("soldPrice")]
            return points[-24:]  # last 24 sales
        except Exception as e:
            log.error(f"[HISTORY ERROR] {e}")
            return []

    def generate_price_graph(self, price_data, player_name):
        if len(price_data) < 2:
            return None
        ts, prices = zip(*price_data)
        fig, ax = plt.subplots(figsize=(6,3))
        fig.patch.set_facecolor("#0D0D0D")
        ax.set_facecolor("#0D0D0D")
        ax.plot(ts, prices, marker="o", linestyle="-", color="#39FF14",
                markersize=3, linewidth=2)
        ax.set_title(f"{player_name} Price Trend", color="white", fontsize=11, fontweight="bold")
        ax.set_xlabel("Time", color="white", fontsize=9)
        ax.set_ylabel("Coins", color="white", fontsize=9)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")
        for spine in ax.spines.values():
            spine.set_color("#555555")
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

    @app_commands.command(name="pricecheck", description="Check a player's live FUT.GG price")
    @app_commands.describe(player="Enter the player name and rating")
    async def pricecheck(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()

        match = await self.lookup_player(player)
        if not match:
            await interaction.followup.send("❌ Player not found in database.")
            return

        prices = await self.fetch_prices(match["card_id"])
        ps_price = prices.get("playstation", {}).get("lowest")
        xb_price = prices.get("xbox", {}).get("lowest")

        price_data = await self.fetch_price_history(match["card_id"])
        graph = self.generate_price_graph(price_data, match["name"])

        embed = discord.Embed(
            title=f"{match['name']} ({match['rating']})",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=match["image_url"])
        embed.add_field(name="PS Price", value=f"{ps_price:,} 🪙" if ps_price else "N/A", inline=True)
        embed.add_field(name="Xbox Price", value=f"{xb_price:,} 🪙" if xb_price else "N/A", inline=True)
        embed.add_field(name="Club", value=match["club"] or "Unknown", inline=True)
        embed.add_field(name="Nation", value=match["nation"] or "Unknown", inline=True)
        embed.add_field(name="League", value=match["league"] or "Unknown", inline=True)

        if graph:
            file = discord.File(graph, filename="graph.png")
            embed.set_image(url="attachment://graph.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            sql = """
                SELECT name, rating
                FROM fut_players
                WHERE LOWER(name) LIKE LOWER($1)
                ORDER BY rating DESC
                LIMIT 25
            """
        except Exception as e:
            log.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []
        rows = await self.db_pool.fetch(sql, f"%{current}%")
        return [app_commands.Choice(name=f"{r['name']} ({r['rating']})", value=f"{r['name']} {r['rating']}") for r in rows]

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))