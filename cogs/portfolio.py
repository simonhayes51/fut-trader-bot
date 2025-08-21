import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt

PORTFOLIO_DATA_PATH = "portfolio_data"
PLAYERS_FILE = "players_temp.json"
os.makedirs(PORTFOLIO_DATA_PATH, exist_ok=True)

def get_data_path(user_id):
    return os.path.join(PORTFOLIO_DATA_PATH, f"{user_id}.json")

def load_user_data(user_id):
    path = get_data_path(user_id)
    if not os.path.exists(path):
        return {"user_id": user_id, "starting_balance": 0, "trades": []}
    with open(path, "r") as f:
        return json.load(f)

def save_user_data(user_id, data):
    path = get_data_path(user_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_players():
    try:
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

class PortfolioSlash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = load_players()

    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        results = [
            app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=p["name"])
            for p in self.players if current.lower() in p["name"].lower()
        ]
        return results[:25]

    @app_commands.command(name="setcoins", description="💰 Set your starting coin balance")
    async def setcoins(self, interaction: discord.Interaction, amount: int):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)
        data["starting_balance"] = amount
        save_user_data(user_id, data)
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
    @app_commands.autocomplete(player=player_autocomplete)
    async def logtrade(self, interaction: discord.Interaction, player: str, version: str, buy: int, sell: int, quantity: int, platform: app_commands.Choice[str], tag: str = None, notes: str = None):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)

        ea_tax = round(sell * 0.05 * quantity)
        profit = round((sell - buy) * quantity - ea_tax)

        trade = {
            "player": player,
            "version": version,
            "buy": buy,
            "sell": sell,
            "quantity": quantity,
            "platform": platform.value,
            "ea_tax": ea_tax,
            "profit": profit,
            "tag": tag,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat()
        }

        data["trades"].append(trade)
        save_user_data(user_id, data)

        await interaction.response.send_message(f"✅ Logged: `{player}` x{quantity} | 🟢 Profit: `{profit:,}` coins | 💸 Tax: `{ea_tax:,}`", ephemeral=True)

    @app_commands.command(name="checkprofit", description="📊 View your profit summary")
    async def check_profit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)

        total_profit = sum(t["profit"] for t in data["trades"])
        total_tax = sum(t["ea_tax"] for t in data["trades"])
        current_balance = data["starting_balance"] + total_profit
        trade_count = len(data["trades"])

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

    @app_commands.command(name="traderprofile", description="🧳 View your trader stats")
    async def trader_profile(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)

        trades = data["trades"]
        total_profit = sum(t["profit"] for t in trades)
        win_count = len([t for t in trades if t["profit"] > 0])
        win_rate = (win_count / len(trades) * 100) if trades else 0
        best_trade = max(trades, key=lambda x: x["profit"], default=None)
        tag_usage = {}

        for t in trades:
            tag = t.get("tag", "N/A")
            tag_usage[tag] = tag_usage.get(tag, 0) + 1

        most_used_tag = max(tag_usage.items(), key=lambda x: x[1])[0] if tag_usage else "N/A"

        embed = discord.Embed(title="🧳 Your Trader Profile", color=0x7289da)
        embed.add_field(name="💰 Total Profit", value=f"`{total_profit:,}`", inline=True)
        embed.add_field(name="🛆 Trades Logged", value=f"`{len(trades)}`", inline=True)
        embed.add_field(name="📈 Win Rate", value=f"`{win_rate:.1f}%`", inline=True)
        embed.add_field(name="🏛️ Most Used Tag", value=f"`{most_used_tag}`", inline=True)

        if best_trade:
            embed.add_field(
                name="🏆 Best Trade",
                value=f"{best_trade['player']} (+{best_trade['profit']:,})",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profitgraph", description="📈 Visualise your profit over time")
    async def profit_graph(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)
        trades = data["trades"]

        if not trades:
            await interaction.response.send_message("📅 No trades found to generate graph.", ephemeral=True)
            return

        trades.sort(key=lambda x: x["timestamp"])
        profits = []
        balance = data["starting_balance"]
        timestamps = []

        for t in trades:
            balance += t["profit"]
            profits.append(balance)
            timestamps.append(datetime.fromisoformat(t["timestamp"]))

        fig, ax = plt.subplots()
        ax.plot(timestamps, profits, marker='o', color='lime')
        ax.set_title("\ud83d\udcc8 Coin Balance Over Time")
        ax.set_ylabel("Coins")
        ax.set_xlabel("Time")
        ax.grid(True)
        fig.autofmt_xdate()

        graph_path = f"{PORTFOLIO_DATA_PATH}/{user_id}_profit_graph.png"
        plt.tight_layout()
        plt.savefig(graph_path)
        plt.close(fig)

        file = discord.File(graph_path, filename="profit_graph.png")
        await interaction.response.send_message(file=file)

async def setup(bot):
    await bot.add_cog(PortfolioSlash(bot))
