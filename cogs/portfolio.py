import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt

PORTFOLIO_DATA_PATH = "portfolio_data"
PLAYERS_FILE = "players_temp.json"

# Ensure the data folder exists
if not os.path.exists(PORTFOLIO_DATA_PATH):
    os.makedirs(PORTFOLIO_DATA_PATH)

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
    @app_commands.describe(amount="Your starting coin balance")
    async def setcoins(self, interaction: discord.Interaction, amount: int):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)
        data["starting_balance"] = amount
        save_user_data(user_id, data)
        await interaction.response.send_message(
            f"💰 Starting coin balance set to **{amount:,} coins**.",
            ephemeral=True
        )

    @app_commands.command(name="addtrade", description="📝 Add a completed trade to your portfolio")
    @app_commands.describe(
        player="Player name",
        version="Card version (e.g. Gold Rare, TOTS)",
        buy_price="Buy price in coins",
        sell_price="Sell price in coins",
        notes="Optional notes about the trade"
    )
    @app_commands.autocomplete(player=player_autocomplete)
    async def addtrade(
        self,
        interaction: discord.Interaction,
        player: str,
        version: str,
        buy_price: int,
        sell_price: int,
        notes: str = None
    ):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)

        trade = {
            "player": player,
            "version": version,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "profit": sell_price - buy_price,
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes or ""
        }

        data["trades"].append(trade)
        save_user_data(user_id, data)

        await interaction.response.send_message(
            f"✅ Trade logged: **{player}** ({version}) – Profit: **{sell_price - buy_price:,}** coins",
            ephemeral=True
        )

    @app_commands.command(name="viewportfolio", description="📊 View your trading portfolio")
    async def viewportfolio(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = load_user_data(user_id)

        total_profit = sum(t["profit"] for t in data["trades"])
        balance = data["starting_balance"] + total_profit
        trade_count = len(data["trades"])

        timestamps = []
        values = []
        balance_tracker = data["starting_balance"]

        for t in sorted(data["trades"], key=lambda x: x["timestamp"]):
            balance_tracker += t["profit"]
            timestamps.append(datetime.fromisoformat(t["timestamp"]))
            values.append(balance_tracker)

        graph_path = f"portfolio_data/{user_id}_graph.png"
        if timestamps:
            fig, ax = plt.subplots()
            ax.plot(timestamps, values, marker='o', color='lime')
            ax.set_title("Coin Balance Over Time")
            ax.set_ylabel("Coins")
            ax.set_xlabel("Time")
            ax.grid(True)
            fig.autofmt_xdate()
            plt.tight_layout()
            plt.savefig(graph_path)
            plt.close(fig)
        else:
            graph_path = None

        embed = discord.Embed(title=f"📈 {interaction.user.name}'s Portfolio", color=0x00ff00)
        embed.add_field(name="💰 Balance", value=f"{balance:,} coins", inline=True)
        embed.add_field(name="📈 Profit", value=f"{total_profit:,} coins", inline=True)
        embed.add_field(name="📄 Trades", value=str(trade_count), inline=True)

        if graph_path and os.path.exists(graph_path):
            file = discord.File(graph_path, filename="graph.png")
            embed.set_image(url="attachment://graph.png")
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(PortfolioSlash(bot))
