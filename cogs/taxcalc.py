import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Tuple
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

class TaxCalc(commands.Cog):
    """Enhanced tax calculator with multiple scenarios and visualizations"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = bot.tree
        self.ea_tax_rate = 0.05  # FC26 EA tax rate (5%)

    def _calculate_trade(self, buy: int, sell: int, quantity: int = 1) -> dict:
        """Calculate trade metrics"""
        total_buy = buy * quantity
        total_sell = sell * quantity
        tax = int(total_sell * self.ea_tax_rate)
        after_tax = total_sell - tax
        profit = after_tax - total_buy
        roi = (profit / total_buy * 100) if total_buy > 0 else 0
        breakeven = int(round(buy / (1 - self.ea_tax_rate)))

        return {
            "buy": buy,
            "sell": sell,
            "quantity": quantity,
            "total_buy": total_buy,
            "total_sell": total_sell,
            "tax": tax,
            "after_tax": after_tax,
            "profit": profit,
            "roi": roi,
            "breakeven": breakeven
        }

    def _generate_profit_scenarios(self, buy_price: int) -> List[Tuple[int, int, float]]:
        """Generate profit scenarios at different sell prices"""
        scenarios = []
        for increase in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
            sell = int(buy_price * (1 + increase))
            result = self._calculate_trade(buy_price, sell)
            scenarios.append((sell, result["profit"], result["roi"]))
        return scenarios

    def _make_profit_chart(self, buy_price: int) -> io.BytesIO:
        """Create profit visualization chart"""
        scenarios = self._generate_profit_scenarios(buy_price)
        sell_prices = [s[0] for s in scenarios]
        profits = [s[1] for s in scenarios]

        fig, ax = plt.subplots(figsize=(8, 4))
        fig.patch.set_facecolor("#0D0D0D")
        ax.set_facecolor("#0D0D0D")

        colors = ['#ff4444' if p < 0 else '#44ff44' for p in profits]
        bars = ax.bar(range(len(sell_prices)), profits, color=colors, alpha=0.8)

        ax.set_title(f"Profit Scenarios (Buy: {buy_price:,} coins)", color="white", fontsize=12, fontweight="bold")
        ax.set_xlabel("Sell Price", color="white", fontsize=10)
        ax.set_ylabel("Profit (after tax)", color="white", fontsize=10)
        ax.set_xticks(range(len(sell_prices)))
        ax.set_xticklabels([f"{p:,}" for p in sell_prices], rotation=45, color="white", fontsize=8)
        ax.tick_params(colors="white")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")

        for spine in ax.spines.values():
            spine.set_color("#555555")

        # Add value labels on bars
        for bar, profit, (_, _, roi) in zip(bars, profits, scenarios):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{profit:,}\n({roi:.1f}%)',
                   ha='center', va='bottom' if height > 0 else 'top',
                   color='white', fontsize=7)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=200, facecolor=fig.get_facecolor())
        buf.seek(0)
        plt.close(fig)
        return buf

    @app_commands.command(name="taxcalc", description="💸 Calculate EA tax, ROI and break-even for FC26 trades")
    @app_commands.describe(
        buy_price="How much you bought the player for 💰",
        sell_price="How much you're selling or plan to sell for 🏷️",
        quantity="Number of cards (default: 1)"
    )
    async def taxcalc(self, interaction: discord.Interaction, buy_price: int, sell_price: int, quantity: int = 1):
        await interaction.response.defer()

        if quantity < 1 or quantity > 1000:
            await interaction.followup.send("❌ Quantity must be between 1 and 1000", ephemeral=True)
            return

        result = self._calculate_trade(buy_price, sell_price, quantity)

        if result["profit"] > 0:
            result_emoji = "✅ Profit"
            color = discord.Color.green()
        elif result["profit"] < 0:
            result_emoji = "❌ Loss"
            color = discord.Color.red()
        else:
            result_emoji = "⚖️ Break-even"
            color = discord.Color.greyple()

        embed = discord.Embed(
            title="💸 FC26 Tax Calculator",
            description="Complete trade breakdown with EA tax calculations",
            color=color,
            timestamp=interaction.created_at
        )

        # Basic Info
        embed.add_field(name="🛒 Buy Price", value=f"{buy_price:,} 🪙", inline=True)
        embed.add_field(name="🏷️ Sell Price", value=f"{sell_price:,} 🪙", inline=True)
        embed.add_field(name="📦 Quantity", value=f"{quantity}x", inline=True)

        # Calculations
        embed.add_field(name="💰 EA Tax (5%)", value=f"{result['tax']:,} 🪙", inline=True)
        embed.add_field(name="💵 After-Tax Sale", value=f"{result['after_tax']:,} 🪙", inline=True)
        embed.add_field(name="📊 ROI", value=f"{result['roi']:.2f}%", inline=True)

        # Profit/Loss
        profit_text = f"{result['profit']:,} 🪙\n{result_emoji}"
        embed.add_field(name="📈 Total Profit/Loss", value=profit_text, inline=True)
        embed.add_field(name="🔄 Break-even Price", value=f"{result['breakeven']:,} 🪙", inline=True)

        # Per card profit if quantity > 1
        if quantity > 1:
            per_card = result['profit'] // quantity
            embed.add_field(name="💎 Per Card Profit", value=f"{per_card:,} 🪙", inline=True)

        # Investment advice
        if result['roi'] >= 20:
            advice = "🔥 Excellent trade! Very high ROI"
        elif result['roi'] >= 10:
            advice = "✅ Great trade! Good profit margin"
        elif result['roi'] >= 5:
            advice = "👍 Decent trade, safe profit"
        elif result['roi'] > 0:
            advice = "⚠️ Low profit, consider waiting"
        else:
            advice = "❌ Loss! Do not sell at this price"

        embed.add_field(name="💡 Trade Analysis", value=advice, inline=False)

        embed.set_footer(text="FC26 • EA Tax: 5% • Trade smarter with FUTHub")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="bulktax", description="📊 Calculate profit for buying multiple cards")
    @app_commands.describe(
        buy_price="Buy price per card",
        sell_price="Sell price per card",
        quantity="Number of cards to flip"
    )
    async def bulktax(self, interaction: discord.Interaction, buy_price: int, sell_price: int, quantity: int):
        """Calculate bulk trading profits"""
        await interaction.response.defer()

        if quantity < 1 or quantity > 10000:
            await interaction.followup.send("❌ Quantity must be between 1 and 10,000", ephemeral=True)
            return

        result = self._calculate_trade(buy_price, sell_price, quantity)

        embed = discord.Embed(
            title=f"📦 Bulk Trade Calculator ({quantity}x cards)",
            description="Mass trading profit breakdown",
            color=discord.Color.gold()
        )

        embed.add_field(name="💰 Total Investment", value=f"{result['total_buy']:,} 🪙", inline=True)
        embed.add_field(name="💵 Total Sale Value", value=f"{result['total_sell']:,} 🪙", inline=True)
        embed.add_field(name="💸 Total EA Tax", value=f"{result['tax']:,} 🪙", inline=True)

        embed.add_field(name="🟢 Total Profit", value=f"{result['profit']:,} 🪙", inline=True)
        embed.add_field(name="📊 ROI", value=f"{result['roi']:.2f}%", inline=True)
        embed.add_field(name="💎 Per Card Profit", value=f"{result['profit'] // quantity:,} 🪙", inline=True)

        # Time estimates
        if quantity >= 100:
            est_time = quantity * 0.5  # ~30 seconds per card
            embed.add_field(name="⏱️ Est. Trading Time", value=f"~{int(est_time)} minutes", inline=False)

        embed.set_footer(text="FC26 • Bulk Trading Calculator")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="profitscenarios", description="📈 See profit at different sell prices")
    @app_commands.describe(buy_price="Your buy price")
    async def profitscenarios(self, interaction: discord.Interaction, buy_price: int):
        """Show profit scenarios with visualization"""
        await interaction.response.defer()

        scenarios = self._generate_profit_scenarios(buy_price)

        embed = discord.Embed(
            title=f"📈 Profit Scenarios (Buy: {buy_price:,} 🪙)",
            description="Potential profit at different sell prices",
            color=discord.Color.blue()
        )

        for sell, profit, roi in scenarios:
            emoji = "🟢" if profit > 0 else "🔴"
            embed.add_field(
                name=f"{emoji} Sell at {sell:,} 🪙",
                value=f"Profit: **{profit:,}** 🪙\nROI: **{roi:.1f}%**",
                inline=True
            )

        embed.set_footer(text="FC26 • All calculations include 5% EA tax")

        # Generate chart
        chart = self._make_profit_chart(buy_price)
        file = discord.File(chart, filename="scenarios.png")
        embed.set_image(url="attachment://scenarios.png")

        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(name="targetprofit", description="🎯 Calculate required sell price for target profit")
    @app_commands.describe(
        buy_price="Your buy price",
        target_profit="Desired profit amount"
    )
    async def targetprofit(self, interaction: discord.Interaction, buy_price: int, target_profit: int):
        """Calculate required sell price for target profit"""
        # Formula: sell_price = (buy_price + target_profit + (sell_price * 0.05))
        # Solving: sell_price = (buy_price + target_profit) / 0.95
        required_sell = int((buy_price + target_profit) / (1 - self.ea_tax_rate))

        # Verify calculation
        result = self._calculate_trade(buy_price, required_sell)

        embed = discord.Embed(
            title="🎯 Target Profit Calculator",
            description=f"To earn **{target_profit:,}** 🪙 profit",
            color=discord.Color.purple()
        )

        embed.add_field(name="🛒 Buy Price", value=f"{buy_price:,} 🪙", inline=True)
        embed.add_field(name="🎯 Target Profit", value=f"{target_profit:,} 🪙", inline=True)
        embed.add_field(name="🏷️ Required Sell Price", value=f"**{required_sell:,}** 🪙", inline=True)

        embed.add_field(name="💰 EA Tax", value=f"{result['tax']:,} 🪙", inline=True)
        embed.add_field(name="📊 ROI", value=f"{result['roi']:.2f}%", inline=True)
        embed.add_field(name="✅ Actual Profit", value=f"{result['profit']:,} 🪙", inline=True)

        embed.set_footer(text="FC26 • Set this as your listing price!")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(TaxCalc(bot))
