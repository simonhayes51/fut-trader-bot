import os
import discord
import logging
import asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("futbot")

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    log.info(f"✅ Logged in as {bot.user.name}")

    try:
        await bot.load_extension("cogs.pricecheck")
        log.info("📦 Loaded pricecheck cog")
    except Exception as e:
        log.error(f"❌ Failed to load pricecheck cog: {e}")

    try:
        await bot.load_extension("cogs.pricecheckgg")
        log.info("📦 Loaded pricecheckgg cog")
    except Exception as e:
        log.error(f"❌ Failed to load pricecheckgg cog: {e}")

    try:
        synced = await bot.tree.sync()
        log.info(f"🔁 Globally synced {len(synced)} slash command(s).")
    except Exception as e:
        log.error(f"❌ Failed to sync slash commands: {e}")

    # Heartbeat to keep logs alive
    async def heartbeat():
        while True:
            log.info("💓 Bot is still alive...")
            await asyncio.sleep(30)

    bot.loop.create_task(heartbeat())

# Simple ping command
@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

# Run the bot using the token from environment variables
bot.run(os.getenv("DISCORD_TOKEN"))
