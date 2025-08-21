import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt

DB_FILE = "portfolio.db"
PLAYERS_FILE = "players_temp.json"

# Ensure DB exists and is structured
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS portfolio (
    user_id TEXT PRIMARY KEY,
    starting_balance INTEGER DEFAULT 0
)''')
c.execute('''CREATE TABLE IF NOT EXISTS trades (
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
)''')
conn.commit()
conn.close()

# Load players
try:
    with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
        PLAYERS = json.load(f)
except:
    PLAYERS = []

class PortfolioSlash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        results = [
            app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=p["name"])
            for p in PLAYERS if current.lower() in p["name"].lower()
        ]
        return results[:25]

    @app_commands.command(name="setcoins", description="💰 Set your starting coin balance")
    async def setcoins(self, interaction: discord.Interaction, amount: int):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("REPLACE INTO portfolio (user_id, starting_balance) VALUES (?, ?)", (user_id, amount))
        conn.commit()
        conn.close()
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

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (user_id, player, version, buy, sell, quantity, platform.value, tag, notes, ea_tax, profit, timestamp))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"✅ Logged: `{player}` x{quantity} | 🟢 Profit: `{profit:,}` coins | 💸 Tax: `{ea_tax:,}`", ephemeral=True)

    @app_commands.command(name="checkprofit", description="📊 View your profit summary")
    async def check_profit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT starting_balance FROM portfolio WHERE user_id=?", (user_id,))
        row = c.fetchone()
        starting_balance = row[0] if row else 0
        c.execute("SELECT SUM(profit), SUM(ea_tax), COUNT(*) FROM trades WHERE user_id=?", (user_id,))
        total_profit, total_tax, count = c.fetchone()
        conn.close()

        current_balance = (starting_balance or 0) + (total_profit or 0)

        embed = discord.Embed(title="📊 Your Trading Portfolio", color=0x2ecc71)
        embed.add_field(name="💰 Net Profit", value=f"`{total_profit or 0:,}`", inline=True)
        embed.add_field(name="💸 EA Tax Paid", value=f"`{total_tax or 0:,}`", inline=True)
        embed.add_field(name="🛆 Trades Logged", value=f"`{count}`", inline=True)
        embed.add_field(name="🏦 Current Balance", value=f"`{current_balance:,}`", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="traderprofile", description="🧳 View your trader stats")
    async def trader_profile(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT * FROM trades WHERE user_id=?", (user_id,))
        trades = c.fetchall()

        total_profit = sum(t[10] for t in trades)
        win_count = len([t for t in trades if t[10] > 0])
        win_rate = (win_count / len(trades) * 100) if trades else 0

        # Most used tag
        tag_count = {}
        for t in trades:
            tag = t[7] or "N/A"
            tag_count[tag] = tag_count.get(tag, 0) + 1
        most_used_tag = max(tag_count.items(), key=lambda x: x[1])[0] if tag_count else "N/A"

        best_trade = max(trades, key=lambda t: t[10], default=None)
        embed = discord.Embed(title="🧳 Your Trader Profile", color=0x7289da)
        embed.add_field(name="💰 Total Profit", value=f"`{total_profit:,}`", inline=True)
        embed.add_field(name="🛆 Trades Logged", value=f"`{len(trades)}`", inline=True)
        embed.add_field(name="📈 Win Rate", value=f"`{win_rate:.1f}%`", inline=True)
        embed.add_field(name="🏛️ Most Used Tag", value=f"`{most_used_tag}`", inline=True)

        if best_trade:
            embed.add_field(name="🏆 Best Trade", value=f"{best_trade[1]} (+{best_trade[10]:,})", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="saleshistory", description="📄 View a log of your recent sales")
    async def sales_history(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT player, quantity, sell, profit, timestamp FROM trades WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (user_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            await interaction.response.send_message("📭 You haven’t logged any trades yet.", ephemeral=True)
            return

        embed = discord.Embed(title="📄 Recent Sales History", color=0x00b0f4)
        for i, row in enumerate(rows, 1):
            date = datetime.fromisoformat(row[4]).strftime("%d %b @ %H:%M")
            embed.add_field(
                name=f"{i}. {row[0]} x{row[1]}",
                value=(
                    f"💸 Sold for: `{row[2] * row[1]:,}`\n"
                    f"🟢 Profit: `{row[3]:,}`\n"
                    f"🕒 {date}"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profitgraph", description="📈 Visualise your profit over time")
    async def profit_graph(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT starting_balance FROM portfolio WHERE user_id=?", (user_id,))
        row = c.fetchone()
        start = row[0] if row else 0
        c.execute("SELECT profit, timestamp FROM trades WHERE user_id=? ORDER BY timestamp", (user_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            await interaction.response.send_message("📅 No trades found to generate graph.", ephemeral=True)
            return

        timestamps = [datetime.fromisoformat(r[1]) for r in rows]
        profits = []
        running = start
        for r in rows:
            running += r[0]
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
