import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
import os

DB_PATH = "portfolio.db"

# Create DB and table if not exists
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
    c.execute('''CREATE TABLE IF NOT EXISTS balances (
        user_id TEXT PRIMARY KEY,
        starting_balance INTEGER
    )''')
    conn.commit()
    conn.close()

init_db()

class PortfolioSQL(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setcoins", description="💰 Set your starting coin balance")
    async def setcoins(self, interaction: discord.Interaction, amount: int):
        user_id = str(interaction.user.id)
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("REPLACE INTO balances (user_id, starting_balance) VALUES (?, ?)", (user_id, amount))
            conn.commit()
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
        profit = (sell - buy) * quantity - ea_tax

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO trades (user_id, player, version, buy, sell, quantity, platform, tag, notes, ea_tax, profit, timestamp)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (user_id, player, version, buy, sell, quantity, platform.value, tag, notes, ea_tax, profit, datetime.utcnow().isoformat()))
            conn.commit()

        await interaction.response.send_message(f"✅ Logged: `{player}` x{quantity} | 🟢 Profit: `{profit:,}` coins | 💸 Tax: `{ea_tax:,}`", ephemeral=True)

    @app_commands.command(name="checkprofit", description="📊 View your profit summary")
    async def checkprofit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT SUM(profit), SUM(ea_tax), COUNT(*) FROM trades WHERE user_id = ?", (user_id,))
            total_profit, total_tax, trade_count = c.fetchone()

            c.execute("SELECT starting_balance FROM balances WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            starting_balance = row[0] if row else 0

        total_profit = total_profit or 0
        total_tax = total_tax or 0
        trade_count = trade_count or 0
        current_balance = starting_balance + total_profit

        embed = discord.Embed(
            title="📊 Your Trading Portfolio",
            description=f"Tracked for <@{interaction.user.id}>",
            color=0x2ecc71
        )
        embed.add_field(name="💰 Net Profit", value=f"`{total_profit:,}`", inline=True)
        embed.add_field(name="💸 EA Tax Paid", value=f"`{total_tax:,}`", inline=True)
        embed.add_field(name="🛆 Trades Logged", value=f"`{trade_count}`", inline=True)
        embed.add_field(name="🏦 Current Balance", value=f"`{current_balance:,}`", inline=True)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(PortfolioSQL(bot))
