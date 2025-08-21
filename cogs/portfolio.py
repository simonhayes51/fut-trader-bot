import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import os

DB_FILE = "portfolio.db"

# Set up database
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS portfolio (
    user_id TEXT,
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

class Portfolio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        quantity="How many you bought",
        platform="Console platform",
        tag="Tag or type (e.g. fodder)",
        notes="Optional notes"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="PlayStation", value="PS"),
        app_commands.Choice(name="Xbox", value="XBOX"),
        app_commands.Choice(name="PC", value="PC")
    ])
    async def logtrade(self, interaction: discord.Interaction, player: str, version: str, buy: int, sell: int, quantity: int, platform: app_commands.Choice[str], tag: str = None, notes: str = None):
        user_id = str(interaction.user.id)
        ea_tax = round(sell * 0.05 * quantity)
        profit = round((sell - buy) * quantity - ea_tax)
        timestamp = datetime.utcnow().isoformat()

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT INTO trades (user_id, player, version, buy, sell, quantity, platform, tag, notes, ea_tax, profit, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, player, version, buy, sell, quantity, platform.value, tag, notes, ea_tax, profit, timestamp))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"✅ Logged: `{player}` x{quantity} | 🟢 Profit: `{profit:,}` coins | 💸 Tax: `{ea_tax:,}`", ephemeral=True)

    @app_commands.command(name="checkprofit", description="📊 View your profit summary")
    async def check_profit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT starting_balance FROM portfolio WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        starting_balance = row[0] if row else 0
        c.execute("SELECT SUM(profit), SUM(ea_tax), COUNT(*) FROM trades WHERE user_id = ?", (user_id,))
        profit, tax, count = c.fetchone()
        conn.close()

        profit = profit or 0
        tax = tax or 0
        count = count or 0
        current_balance = starting_balance + profit

        embed = discord.Embed(title="📊 Your Trading Portfolio", description=f"Tracked for <@{interaction.user.id}>", color=0x2ecc71)
        embed.add_field(name="💰 Net Profit", value=f"`{profit:,}`", inline=True)
        embed.add_field(name="💸 EA Tax Paid", value=f"`{tax:,}`", inline=True)
        embed.add_field(name="🛆 Trades Logged", value=f"`{count}`", inline=True)
        embed.add_field(name="🏦 Current Balance", value=f"`{current_balance:,}`", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tradehistory", description="📄 View your latest trades")
    async def trade_history(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT player, sell, quantity, profit, timestamp FROM trades WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10", (user_id,))
        trades = c.fetchall()
        conn.close()

        if not trades:
            await interaction.response.send_message("📭 No trades found.", ephemeral=True)
            return

        embed = discord.Embed(title="📄 Recent Sales History", color=0x00b0f4)
        for i, t in enumerate(trades, 1):
            date = datetime.fromisoformat(t[4]).strftime("%d %b @ %H:%M")
            embed.add_field(
                name=f"{i}. {t[0]} x{t[2]}",
                value=f"💸 Sold for: `{t[1] * t[2]:,}`\n🟢 Profit: `{t[3]:,}`\n🕒 {date}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profitgraph", description="📈 Visualise your profit over time")
    async def profit_graph(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT starting_balance FROM portfolio WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        starting_balance = row[0] if row else 0

        c.execute("SELECT timestamp, profit FROM trades WHERE user_id = ? ORDER BY timestamp", (user_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            await interaction.response.send_message("📅 No trades to plot.", ephemeral=True)
            return

        timestamps = []
        balances = []
        balance = starting_balance

        for t, p in rows:
            balance += p
            timestamps.append(datetime.fromisoformat(t))
            balances.append(balance)

        graph_path = f"{user_id}_profit_graph.png"
        fig, ax = plt.subplots()
        ax.plot(timestamps, balances, marker='o', color='lime')
        ax.set_title("Coin Balance Over Time")
        ax.set_ylabel("Coins")
        ax.set_xlabel("Time")
        ax.grid(True)
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(graph_path)
        plt.close(fig)

        file = discord.File(graph_path)
        await interaction.response.send_message(file=file)

async def setup(bot):
    await bot.add_cog(Portfolio(bot))
