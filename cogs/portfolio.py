import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncpg
from datetime import datetime
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
PLAYERS_FILE = "players_temp.json"

class PortfolioSlash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()

    def load_players(self):
        try:
            with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    async def cog_load(self):
        self.pool = await asyncpg.create_pool(DB_URL)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id TEXT PRIMARY KEY,
                    starting_balance INTEGER DEFAULT 0
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    user_id TEXT,
                    player TEXT,
                    version TEXT,
                    buy INTEGER,
                    sell INTEGER,
                    quantity INTEGER,
                    platform TEXT,
                    tag TEXT,
                    notes TEXT,
                    ea_tax INTEGER,
                    profit INTEGER,
                    timestamp TEXT
                )
            """)

    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        results = [
            app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=p["name"])
            for p in self.players if current.lower() in p["name"].lower()
        ]
        return results[:25]

    @app_commands.command(name="setcoins", description="💰 Set your starting coin balance")
    async def setcoins(self, interaction: discord.Interaction, amount: int):
        user_id = str(interaction.user.id)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO portfolio (user_id, starting_balance)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET starting_balance = $2
            """, user_id, amount)
        await interaction.response.send_message(f"✅ Starting balance set to **{amount:,} coins**", ephemeral=True)

    @app_commands.command(name="logtrade", description="💼 Log a new trade")
    @app_commands.describe(
        player="Player name",
        version="Card version (e.g. Gold Rare, TOTW)",
        buy="Buy price",
        sell="Sell price",
        quantity="Quantity bought",
        platform="Platform used",
        tag="Optional tag/category",
        notes="Optional notes"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="PlayStation", value="PS"),
        app_commands.Choice(name="Xbox", value="XBOX"),
        app_commands.Choice(name="PC", value="PC")
    ])
    @app_commands.autocomplete(player=player_autocomplete)
    async def logtrade(self, interaction: discord.Interaction, player: str, version: str, buy: int, sell: int, quantity: int, platform: app_commands.Choice[str], tag: str = None, notes: str = None):
        user_id = str(interaction.user.id)
        ea_tax = round(sell * 0.05 * quantity)
        profit = round((sell - buy) * quantity - ea_tax)
        timestamp = datetime.utcnow().isoformat()

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO trades (user_id, player, version, buy, sell, quantity, platform, tag, notes, ea_tax, profit, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """, user_id, player, version, buy, sell, quantity, platform.value, tag, notes, ea_tax, profit, timestamp)

        await interaction.response.send_message(f"✅ Logged: `{player}` x{quantity} | 🟢 Profit: `{profit:,}` coins | 💸 Tax: `{ea_tax:,}`", ephemeral=True)

    @app_commands.command(name="checkprofit", description="📊 View your profit summary")
    async def check_profit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT starting_balance FROM portfolio WHERE user_id=$1", user_id)
            starting_balance = row["starting_balance"] if row else 0
            stats = await conn.fetchrow("SELECT SUM(profit) AS total_profit, SUM(ea_tax) AS total_tax, COUNT(*) AS count FROM trades WHERE user_id=$1", user_id)

        total_profit = stats["total_profit"] or 0
        total_tax = stats["total_tax"] or 0
        count = stats["count"]
        current_balance = starting_balance + total_profit

        embed = discord.Embed(title="📊 Your Trading Portfolio", color=0x2ecc71)
        embed.add_field(name="💰 Net Profit", value=f"`{total_profit:,}`", inline=True)
        embed.add_field(name="💸 EA Tax Paid", value=f"`{total_tax:,}`", inline=True)
        embed.add_field(name="🖖️ Trades Logged", value=f"`{count}`", inline=True)
        embed.add_field(name="🏦 Current Balance", value=f"`{current_balance:,}`", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="saleshistory", description="📄 View a log of your recent sales")
    async def sales_history(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT player, quantity, sell, profit, timestamp
                FROM trades WHERE user_id=$1
                ORDER BY timestamp DESC LIMIT 10
            """, user_id)

        if not rows:
            await interaction.response.send_message("👭 You haven’t logged any trades yet.", ephemeral=True)
            return

        embed = discord.Embed(title="📄 Recent Sales History", color=0x00b0f4)
        for i, row in enumerate(rows, 1):
            date = datetime.fromisoformat(row["timestamp"]).strftime("%d %b @ %H:%M")
            embed.add_field(
                name=f"{i}. {row['player']} x{row['quantity']}",
                value=(
                    f"💸 Sold for: `{row['sell'] * row['quantity']:,}`\n"
                    f"🟢 Profit: `{row['profit']:,}`\n"
                    f"🕒 {date}"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="traderprofile", description="🧳️ View your trader stats")
    async def trader_profile(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        async with self.pool.acquire() as conn:
            trades = await conn.fetch("SELECT * FROM trades WHERE user_id=$1", user_id)

        total_profit = sum(t["profit"] for t in trades)
        win_count = len([t for t in trades if t["profit"] > 0])
        win_rate = (win_count / len(trades) * 100) if trades else 0

        tag_count = {}
        for t in trades:
            tag = t["tag"] or "N/A"
            tag_count[tag] = tag_count.get(tag, 0) + 1
        most_used_tag = max(tag_count.items(), key=lambda x: x[1])[0] if tag_count else "N/A"

        best_trade = max(trades, key=lambda t: t["profit"], default=None)
        embed = discord.Embed(title="🧳️ Your Trader Profile", color=0x7289da)
        embed.add_field(name="💰 Total Profit", value=f"`{total_profit:,}`", inline=True)
        embed.add_field(name="🖖️ Trades Logged", value=f"`{len(trades)}`", inline=True)
        embed.add_field(name="📈 Win Rate", value=f"`{win_rate:.1f}%`", inline=True)
        embed.add_field(name="🏮 Most Used Tag", value=f"`{most_used_tag}`", inline=True)

        if best_trade:
            embed.add_field(name="🏆 Best Trade", value=f"{best_trade['player']} (+{best_trade['profit']:,})", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profitgraph", description="📈 Visualise your profit over time")
    async def profit_graph(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT starting_balance FROM portfolio WHERE user_id=$1", user_id)
            start = row["starting_balance"] if row else 0
            rows = await conn.fetch("SELECT profit, timestamp FROM trades WHERE user_id=$1 ORDER BY timestamp", user_id)

        if not rows:
            await interaction.response.send_message("📅 No trades found to generate graph.", ephemeral=True)
            return

        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in rows]
        profits = []
        running = start
        for r in rows:
            running += r["profit"]
            profits.append(running)

        fig, ax = plt.subplots()
        ax.plot(timestamps, profits, marker='o', color='lime')
        ax.set_title("Coin Balance Over Time")
        ax.set_ylabel("Coins")
        ax.set_xlabel("Time")
        ax.grid(True)
        fig.autofmt_xdate()
        plt.tight_layout()
        path = f"{user_id}_graph.png"
        plt.savefig(path)
        plt.close(fig)

        file = discord.File(path, filename="profit_graph.png")
        await interaction.response.send_message(file=file)

async def setup(bot):
    await bot.add_cog(PortfolioSlash(bot))
