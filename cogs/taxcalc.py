import discord
from discord.ext import commands
from discord import app_commands

class TaxCalc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tree = bot.tree

    @app_commands.command(name="taxcalc", description="📊 Calculate EA tax, ROI and break-even for a FUT trade")
    @app_commands.describe(
        buy_price="How much you bought the player for 💰",
        sell_price="How much you're selling or plan to sell for 🏷️"
    )
    async def taxcalc(self, interaction: discord.Interaction, buy_price: int, sell_price: int):
        tax = int(sell_price * 0.05)
        after_tax = sell_price - tax
        profit = after_tax - buy_price

        try:
            roi = (profit / buy_price) * 100
        except ZeroDivisionError:
            roi = 0

        breakeven_price = int(round(buy_price / 0.95))

        if profit > 0:
            result_emoji = "✅ Profit"
        elif profit < 0:
            result_emoji = "❌ Loss"
        else:
            result_emoji = "⚖️ Break-even"

        embed = discord.Embed(
            title="💸 FUT Tax Calculator",
            description="Here's your full trade breakdown:",
            color=discord.Color.green() if profit > 0 else discord.Color.red() if profit < 0 else discord.Color.greyple()
        )

        embed.add_field(name="🛒 Buy Price", value=f"{buy_price:,} coins", inline=True)
        embed.add_field(name="🏷️ Sell Price", value=f"{sell_price:,} coins", inline=True)
        embed.add_field(name="💰 EA Tax (5%)", value=f"{tax:,} coins", inline=True)
        embed.add_field(name="💵 After-Tax Sale", value=f"{after_tax:,} coins", inline=True)
        embed.add_field(name="📈 Profit / Loss", value=f"{profit:,} coins ({result_emoji})", inline=True)
        embed.add_field(name="📊 ROI", value=f"{roi:.2f}%", inline=True)
        embed.add_field(name="🔄 Break-even Sale Price", value=f"{breakeven_price:,} coins", inline=False)
        embed.set_footer(text="EA always takes their cut. Trade smarter. ⚽")
        embed.timestamp = interaction.created_at

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(TaxCalc(bot))
