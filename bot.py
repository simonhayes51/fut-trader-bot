import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure intents
intents = discord.Intents.default()
intents.message_content = True

# Set up the bot
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name}")

    # Try loading pricecheck cog
    try:
        await bot.load_extension("cogs.pricecheck")
        print("📦 Loaded pricecheck cog")
    except Exception as e:
        print(f"❌ Failed to load pricecheck cog: {e}")

    # Try loading pricecheckgg cog
    try:
        await bot.load_extension("cogs.pricecheckgg")
        print("📦 Loaded pricecheckgg cog")
    except Exception as e:
        print(f"❌ Failed to load pricecheckgg cog: {e}")

    # Sync commands globally
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

    print("🟢 on_ready completed successfully")

# Test command
@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    print("✅ /ping command used")
    await interaction.response.send_message("🏓 Pong!")

# Check token and run bot
token = os.getenv("DISCORD_TOKEN")
if not token:
    print("❌ DISCORD_TOKEN environment variable is missing!")
    exit(1)

bot.run(token)
