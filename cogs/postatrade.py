import discord
from discord.ext import commands
from discord import app_commands

class PostATrade(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tree = bot.tree  # Hook into the bot's command tree

    @app_commands.command(name="postatrade", description="📬 Post a trade tip to the server!")
    @app_commands.describe(
        name="Player name",
        version="Card version (e.g. Gold Rare, TOTW, TOTS)",
        buy_price="Buy price in coins",
        sell_time="When to sell (e.g. in 2 days, post SBC, etc)",
        platform="Platform used",
        reason="Optional tip or reasoning behind the trade",
        image="Optional image of the deal (e.g. screenshot)"
    )
    @app_commands.choices(
        platform=[
            app_commands.Choice(name="🎮 Console", value="Console"),
            app_commands.Choice(name="💻 PC", value="PC")
        ]
    )
    async def postatrade(
        self,
        interaction: discord.Interaction,
        name: str,
        version: str,
        buy_price: int,
        sell_time: str,
        platform: app_commands.Choice[str],
        reason: str = None,
        image: discord.Attachment = None
    ):
        embed = discord.Embed(
            title="📢 New Trade Tip Submitted!",
            description=f"Submitted by {interaction.user.mention}",
            color=discord.Color.blue()
        )

        embed.add_field(name="👤 Name", value=name, inline=True)
        embed.add_field(name="✨ Version", value=version, inline=True)
        embed.add_field(name="💰 Buy Price", value=f"{buy_price:,} coins", inline=True)
        embed.add_field(name="⏳ Sell Time", value=sell_time, inline=True)
        embed.add_field(name="🕹️ Platform", value=platform.name, inline=True)

        if reason:
            embed.add_field(name="🧠 Tip / Reason", value=reason, inline=False)

        if image:
            embed.set_image(url=image.url)

        embed.set_footer(text="Use this format when sharing tips in #trade-room or similar channels 📈")
        embed.timestamp = interaction.created_at

        await interaction.response.send_message("✅ Trade posted!", ephemeral=True)
        await interaction.channel.send(embed=embed)

# ✅ Correct class reference here
async def setup(bot):
    await bot.add_cog(PostATrade(bot))
