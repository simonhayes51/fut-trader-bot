import os
import discord
import logging
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from keep_alive import keep_alive  # Optional: for uptime pings (e.g. Railway or Replit)

# Load environment variables

load_dotenv()

# Set up logging

logging.basicConfig(
level=logging.INFO,
format=’[%(asctime)s] %(levelname)s:%(name)s: %(message)s’,
handlers=[logging.StreamHandler()]
)

# Configure intents

intents = discord.Intents.default()
intents.message_content = True

# Set up the bot

bot = commands.Bot(command_prefix=”!”, intents=intents)

# List of cogs to load

COGS = [
“cogs.pricecheck”,
“cogs.taxcalc”,
“cogs.setupsniping”,
“cogs.submitfilter”,
“cogs.trending”,
“cogs.postatrade”
]

async def load_cogs():
“”“Load all cogs with better error handling”””
for cog in COGS:
try:
await bot.load_extension(cog)
logging.info(f”📦 Loaded {cog}”)
except Exception as e:
logging.error(f”❌ Failed to load {cog}: {e}”)

@bot.event
async def on_ready():
logging.info(f”✅ Logged in as {bot.user.name} (ID: {bot.user.id})”)
logging.info(f”🌐 Connected to {len(bot.guilds)} guilds”)

```
# Load all cogs
await load_cogs()

# Sync slash commands
try:
    synced = await bot.tree.sync()
    logging.info(f"🔁 Globally synced {len(synced)} slash command(s).")
except Exception as e:
    logging.error(f"❌ Failed to sync slash commands: {e}")
```

# Global error handler for slash commands

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
if isinstance(error, app_commands.CommandOnCooldown):
await interaction.response.send_message(f”⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds.”, ephemeral=True)
elif isinstance(error, app_commands.MissingPermissions):
await interaction.response.send_message(“❌ You don’t have permission to use this command.”, ephemeral=True)
else:
logging.error(f”Slash command error: {error}”)
if not interaction.response.is_done():
await interaction.response.send_message(“❌ An error occurred while processing your command.”, ephemeral=True)

# Global error handler for regular commands

@bot.event
async def on_command_error(ctx, error):
if isinstance(error, commands.CommandNotFound):
return  # Ignore unknown commands
elif isinstance(error, commands.MissingPermissions):
await ctx.send(“❌ You don’t have permission to use this command.”)
else:
logging.error(f”Command error: {error}”)
await ctx.send(“❌ An error occurred while processing your command.”)

# Test command

@bot.tree.command(name=“ping”, description=“Replies with pong!”)
async def ping(interaction: discord.Interaction):
logging.info(f”✅ /ping command used by {interaction.user} in {interaction.guild}”)
latency = round(bot.latency * 1000)  # Convert to milliseconds
await interaction.response.send_message(f”🏓 Pong! Latency: {latency}ms”)

# Admin command to reload cogs (useful for development)

@bot.tree.command(name=“reload”, description=“🔄 Reload a specific cog (Admin only)”)
@app_commands.describe(cog=“Name of the cog to reload (e.g., trending)”)
async def reload_cog(interaction: discord.Interaction, cog: str):
# Check if user is bot owner or has admin permissions
if interaction.user.id != interaction.guild.owner_id and not any(role.permissions.administrator for role in interaction.user.roles):
await interaction.response.send_message(“❌ Only admins can use this command.”, ephemeral=True)
return

```
try:
    await bot.reload_extension(f"cogs.{cog}")
    await interaction.response.send_message(f"✅ Reloaded `{cog}` cog successfully!")
    logging.info(f"🔄 Reloaded {cog} cog by {interaction.user}")
except Exception as e:
    await interaction.response.send_message(f"❌ Failed to reload `{cog}`: {str(e)}")
    logging.error(f"❌ Failed to reload {cog}: {e}")
```

# Graceful shutdown handler

@bot.event
async def on_disconnect():
logging.info(“🔌 Bot disconnected”)

@bot.event
async def on_connect():
logging.info(“🔗 Bot connected to Discord”)

# Keep alive server (used in free hosting platforms like Replit or Railway)

keep_alive()  # Only works if keep_alive.py exists

# Run the bot

def main():
token = os.getenv(“DISCORD_TOKEN”)
if not token:
logging.error(“❌ DISCORD_TOKEN environment variable is missing!”)
return

```
try:
    bot.run(token)
except discord.LoginFailure:
    logging.error("❌ Invalid bot token!")
except Exception as e:
    logging.error(f"❌ Bot failed to start: {e}")
```

if **name** == “**main**”:
main()