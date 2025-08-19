import os
import discord
import logging
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from keep_alive import keep_alive  # 👈 NEW

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configure intents
intents = discord.Intents.default()
intents.message_content = True

# Set up the bot
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user.name}")

    try:
        await bot.load_extension("cogs.pricecheck")
        logging.info("📦 Loaded pricecheck cog")
    except Exception as e:
        logging.error(f"❌ Failed to load pricecheck cog: {e}")

    try:
        await bot.load_extension("cogs.pricecheckgg")
        logging.info("📦 Loaded pricecheckgg cog")
    except Exception as e:
        logging.error(f"❌ Failed to load pricecheckgg cog: {e}")

    try:
        synced = await bot.tree.sync()
        logging.info(f"🔁 Globally synced {len(synced)} slash command(s).")
    except Exception as e:
        logging.error(f"❌ Failed to sync slash commands: {e}")

# Test slash command
@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    logging.info("✅ /ping command used")
    await interaction.response.send_message("🏓 Pong!")

# Start keep-alive server
keep_alive()  # 👈 NEW

# Run bot
token = os.getenv("DISCORD_TOKEN")
if not token:
    logging.error("❌ DISCORD_TOKEN environment variable is missing!")
    exit(1)

bot.run(token)
