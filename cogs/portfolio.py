
import discord
from discord.ext import commands
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt

PORTFOLIO_DATA_PATH = "portfolio_data"
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

class Portfolio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setcoins")
    async def set_coins(self, ctx, amount: int):
        user_id = str(ctx.author.id)
        data = load_user_data(user_id)
        data["starting_balance"] = amount
        save_user_data(user_id, data)
        await ctx.send(f"💰 **Starting balance set to `{amount:,}` coins.**")

    @commands.command(name="logtrade")
    async def log_trade(self, ctx, player, version, buy: int, sell: int, quantity: int, platform, tag=None, *, notes=None):
        user_id = str(ctx.author.id)
        data = load_user_data(user_id)

        ea_tax = round(sell * 0.05 * quantity)
        profit = round((sell - buy) * quantity - ea_tax)

        trade = {
            "player": player,
            "version": version,
            "buy": buy,
            "sell": sell,
            "quantity": quantity,
            "platform": platform.upper(),
            "ea_tax": ea_tax,
            "profit": profit,
            "tag": tag,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat()
        }

        data["trades"].append(trade)
        save_user_data(user_id, data)

        await ctx.send(
            f"✅ **Logged:** `{player}` x{quantity} | 🟢 Profit: `{profit:,}` coins | 💸 Tax: `{ea_tax:,}`")

    @commands.command(name="checkprofit")
    async def check_profit(self, ctx):
        user_id = str(ctx.author.id)
        data = load_user_data(user_id)

        total_profit = sum(t["profit"] for t in data["trades"])
        total_tax = sum(t["ea_tax"] for t in data["trades"])
        current_balance = data["starting_balance"] + total_profit
        trade_count = len(data["trades"])

        embed = discord.Embed(
            title="📊 Your Trading Portfolio",
            description=f"Tracked for <@{ctx.author.id}>",
            color=0x2ecc71
        )
        embed.add_field(name="💰 Net Profit", value=f"`{total_profit:,}`", inline=True)
        embed.add_field(name="💸 EA Tax Paid", value=f"`{total_tax:,}`", inline=True)
        embed.add_field(name="📦 Trades Logged", value=f"`{trade_count}`", inline=True)
        embed.add_field(name="🏦 Current Balance", value=f"`{current_balance:,}`", inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="checktradehistory")
    async def check_trade_history(self, ctx, limit: int = 5):
        user_id = str(ctx.author.id)
        data = load_user_data(user_id)
        trades = data["trades"][-limit:]

        if not trades:
            await ctx.send("📭 No trades logged yet.")
            return

        embed = discord.Embed(title="📋 Recent Trades", color=0x3498db)
        for i, trade in enumerate(reversed(trades), 1):
            embed.add_field(
                name=f"{i}. {trade['player']} ({trade['version']}) x{trade['quantity']}",
                value=(
                    f"💰 Buy: `{trade['buy']}` | 💸 Sell: `{trade['sell']}` | 🟢 Profit: `{trade['profit']:,}`\n"
                    f"🎮 Platform: `{trade['platform']}` | 🏷️ Tag: `{trade.get('tag', 'N/A')}`"
                ),
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="traderprofile")
    async def trader_profile(self, ctx):
        user_id = str(ctx.author.id)
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

        most_used_tag = max(tag_usage.items(), key=lambda x: x[1]) if tag_usage else "N/A"

        embed = discord.Embed(title="🧾 Your Trader Profile", color=0x7289da)
        embed.add_field(name="💰 Total Profit", value=f"`{total_profit:,}`", inline=True)
        embed.add_field(name="📦 Trades Logged", value=f"`{len(trades)}`", inline=True)
        embed.add_field(name="📈 Win Rate", value=f"`{win_rate:.1f}%`", inline=True)
        embed.add_field(name="🏷️ Most Used Tag", value=f"`{most_used_tag}`", inline=True)

        if best_trade:
            embed.add_field(
                name="🏆 Best Trade",
                value=f"{best_trade['player']} (+{best_trade['profit']:,})",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="profitgraph")
    async def profit_graph(self, ctx):
        user_id = str(ctx.author.id)
        data = load_user_data(user_id)

        trades = data["trades"]
        if not trades:
            await ctx.send("📭 No trades found to generate graph.")
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
        ax.set_title("📈 Coin Balance Over Time")
        ax.set_ylabel("Coins")
        ax.set_xlabel("Time")
        ax.grid(True)
        fig.autofmt_xdate()

        graph_path = f"{PORTFOLIO_DATA_PATH}/{user_id}_profit_graph.png"
        plt.tight_layout()
        plt.savefig(graph_path)
        plt.close(fig)

        file = discord.File(graph_path, filename="profit_graph.png")
        await ctx.send(file=file)

async def setup(bot):
    await bot.add_cog(Portfolio(bot))
