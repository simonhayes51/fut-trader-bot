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
        await bot.load_extension("cogs.taxcalc")
        logging.info("📦 Loaded taxcalc cog")
    except Exception as e:
        logging.error(f"❌ Failed to load taxcalc cog: {e}")

    try:
        await bot.load_extension("cogs.leaktweets")
        logging.info("📦 Loaded leaktweets cog")
    except Exception as e:
        logging.error(f"❌ Failed to load leaktweets cog: {e}")
    
    try:
        await bot.load_extension("cogs.setupsniping")
        logging.info("📦 Loaded setupsniping cog")
    except Exception as e:
        logging.error(f"❌ Failed to load setupsniping cog: {e}")

    try:
        await bot.load_extension("cogs.submitfilter")
        logging.info("📦 Loaded submitfilter cog")
    except Exception as e:
        logging.error(f"❌ Failed to load submitfilter cog: {e}")
    
    try:
        await bot.load_extension("cogs.trending")
        logging.info("📦 Loaded trending cog")
    except Exception as e:
        logging.error(f"❌ Failed to load trending cog: {e}")
        
    try:
        await bot.load_extension("cogs.submitdeal")
        logging.info("📦 Loaded submitdeal cog")
    except Exception as e:
        logging.error(f"❌ Failed to load submitdeal cog: {e}")

    try:
        synced = await bot.tree.sync()
        logging.info(f"🔁 Globally synced {len(synced)} slash command(s).")
    except Exception as e:
        logging.error(f"❌ Failed to sync slash commands: {e}")

# Test command
@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    logging.info("✅ /ping command used")
    await interaction.response.send_message("🏓 Pong!")

# Keep alive server (used in free hosting platforms like Replit or Railway)
keep_alive()  # Only works if keep_alive.py exists

# Run the bot
token = os.getenv("DISCORD_TOKEN")
if not token:
    logging.error("❌ DISCORD_TOKEN environment variable is missing!")
    exit(1)

bot.run(token)
