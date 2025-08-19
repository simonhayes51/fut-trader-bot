import discord
from discord.ext import commands
from discord import app_commands
import json
import os

FILE_PATH = "sniping_channels.json"

class SetupSniping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sniping_channels = self.load_channels()

    def load_channels(self):
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH, "r") as f:
                return json.load(f)
        return {}

    def save_channels(self):
        with open(FILE_PATH, "w") as f:
            json.dump(self.sniping_channels, f, indent=4)

    @app_commands.command(name="setupsniping", description="📍 Set the channel for sniping filter posts.")
    @app_commands.describe(channel="The channel where filters should be posted")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setupsniping(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild_id)
        self.sniping_channels[guild_id] = channel.id
        self.save_channels()
        await interaction.response.send_message(f"✅ Sniping filters will now be posted in {channel.mention}.", ephemeral=True)

    def get_channel_for_guild(self, guild_id):
        return self.sniping_channels.get(str(guild_id), None)

async def setup(bot):
    await bot.add_cog(SetupSniping(bot))
