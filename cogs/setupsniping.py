import discord
from discord.ext import commands
from discord import app_commands
import json
import os

FILE_PATH = "sniping_channels.json"
ALLOWED_ROLE_NAMES = ["Admin", "Owner"]  # 👈 You can add more role names here if needed

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

    def is_owner_or_admin(self, user: discord.Member):
        # Always allow server owner
        if user.guild and user.id == user.guild.owner_id:
            return True
        # Check for role match
        user_roles = [role.name.lower() for role in user.roles]
        for allowed in ALLOWED_ROLE_NAMES:
            if allowed.lower() in user_roles:
                return True
        return False

    @app_commands.command(name="setupsniping", description="📍 Set the channel for sniping filter posts.")
    @app_commands.describe(channel="The channel where filters should be posted")
    async def setupsniping(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Check for admin or owner permission
        if not self.is_owner_or_admin(interaction.user):
            await interaction.response.send_message("❌ You must be the server owner or have an Admin/Owner role to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        self.sniping_channels[guild_id] = channel.id
        self.save_channels()
        await interaction.response.send_message(f"✅ Sniping filters will now be posted in {channel.mention}.", ephemeral=True)

    def get_channel_for_guild(self, guild_id):
        return self.sniping_channels.get(str(guild_id), None)

async def setup(bot):
    await bot.add_cog(SetupSniping(bot))
