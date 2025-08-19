import discord
from discord.ext import commands
from discord import app_commands
import json
import os

FILE_PATH = "sniping_channels.json"
ALLOWED_ROLE_NAMES = ["Admin", "Owner"]

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
        if user.guild and user.id == user.guild.owner_id:
            return True
        user_roles = [role.name.lower() for role in user.roles]
        for allowed in ALLOWED_ROLE_NAMES:
            if allowed.lower() in user_roles:
                return True
        return False

    @app_commands.command(name="setupsniping", description="📍 Set the sniping filter channel and ping role.")
    @app_commands.describe(
        channel="The channel where filters should be posted",
        role="The role to ping when a new filter is submitted"
    )
    async def setupsniping(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
        if not self.is_owner_or_admin(interaction.user):
            await interaction.response.send_message("❌ You must be the server owner or have an Admin/Owner role to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        self.sniping_channels[guild_id] = {
            "channel_id": channel.id,
            "role_id": role.id
        }
        self.save_channels()

        await interaction.response.send_message(
            f"✅ Sniping filters will now be posted in {channel.mention} and will ping {role.mention}.",
            ephemeral=True
        )

    def get_settings(self, guild_id):
        return self.sniping_channels.get(str(guild_id), None)

async def setup(bot):
    await bot.add_cog(SetupSniping(bot))
