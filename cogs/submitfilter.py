import discord
from discord.ext import commands
from discord import app_commands
import json
import os

SNIPING_FILE = "sniping_channels.json"
FILTER_ALERT_ROLE_ID = 123456789012345678  # 🔁 Replace with your actual Filter Alerts role ID

class SubmitFilter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="submitfilter", description="📬 Share a sniping filter with the server!")
    @app_commands.describe(
        filter_name="Short title e.g. 83 PL Gold Rares",
        rating="Card rating or range (e.g. 82–83)",
        rarity="Card type (Gold Rare, TOTW, etc.)",
        league="Optional – e.g. Premier League",
        nation="Optional – e.g. Brazil",
        position="Optional – e.g. ST, CB, CAM",
        max_bin="Max Buy Now price (e.g. 2000)",
        target_buy="Sniping price (e.g. 1700)",
        target_sell="Sell price (e.g. 2400)",
        platform="Platform used",
        tip="Optional advice or reason this filter works"
    )
    @app_commands.choices(
        platform=[
            app_commands.Choice(name="🎮 Console", value="Console"),
            app_commands.Choice(name="💻 PC", value="PC")
        ]
    )
    async def submitfilter(
        self,
        interaction: discord.Interaction,
        filter_name: str,
        rating: str,
        rarity: str,
        league: str = None,
        nation: str = None,
        position: str = None,
        max_bin: str = None,
        target_buy: str = None,
        target_sell: str = None,
        platform: app_commands.Choice[str] = None,
        tip: str = None
    ):
        await interaction.response.defer()

        # Load channel ID
        guild_id = str(interaction.guild_id)
        if os.path.exists(SNIPING_FILE):
            with open(SNIPING_FILE, "r") as f:
                sniping_data = json.load(f)
                target_channel_id = sniping_data.get(guild_id)
        else:
            target_channel_id = None

        if not target_channel_id:
            await interaction.followup.send(
                "⚠️ No sniping channel has been set yet. Use `/setupsniping` to configure it.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📢 New Sniping Filter by {interaction.user.display_name}",
            description=f"🔍 **{filter_name}**",
            colour=discord.Colour.gold()
        )

        embed.add_field(name="🎮 Platform", value=platform.name if platform else "Not specified", inline=True)
        embed.add_field(name="⭐ Rating", value=rating, inline=True)
        embed.add_field(name="✨ Rarity", value=rarity, inline=True)

        if league:
            embed.add_field(name="🏆 League", value=league, inline=True)
        if nation:
            embed.add_field(name="🇺🇳 Nation", value=nation, inline=True)
        if position:
            embed.add_field(name="📌 Position", value=position, inline=True)
        if max_bin:
            embed.add_field(name="📉 Max BIN", value=f"{max_bin} coins", inline=True)
        if target_buy:
            embed.add_field(name="🟢 Buy at", value=f"{target_buy} coins", inline=True)
        if target_sell:
            embed.add_field(name="🔴 Sell at", value=f"{target_sell} coins", inline=True)
        if tip:
            embed.add_field(name="💡 Tip", value=tip, inline=False)

        embed.set_footer(text="Use this to find quick snipes before prices change.")

        channel = self.bot.get_channel(int(target_channel_id))
        if channel:
            await channel.send(content=f"<@&{FILTER_ALERT_ROLE_ID}>", embed=embed)
            await interaction.followup.send("✅ Your sniping filter has been submitted!", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Could not find the sniping channel.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SubmitFilter(bot))
