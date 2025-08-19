import os
import sys
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def heartbeat():
    while True:
        sys.stdout.write("\U0001F493 Bot is still alive...\n")
        sys.stdout.flush()
        await asyncio.sleep(30)

@bot.event
async def on_ready():
    sys.stdout.write(f"\n\u2705 Logged in as {bot.user.name}\n")
    sys.stdout.flush()

    try:
        await bot.load_extension("cogs.pricecheck")
        sys.stdout.write("\U0001F4E6 Loaded pricecheck cog\n")
    except Exception as e:
        sys.stdout.write(f"\u274C Failed to load pricecheck cog: {e}\n")
    sys.stdout.flush()

    try:
        await bot.load_extension("cogs.pricecheckgg")
        sys.stdout.write("\U0001F4E6 Loaded pricecheckgg cog\n")
    except Exception as e:
        sys.stdout.write(f"\u274C Failed to load pricecheckgg cog: {e}\n")
    sys.stdout.flush()

    try:
        synced = await bot.tree.sync()
        sys.stdout.write(f"\U0001F501 Synced {len(synced)} slash command(s)\n")
    except Exception as e:
        sys.stdout.write(f"\u274C Failed to sync slash commands: {e}\n")
    sys.stdout.flush()

    bot.loop.create_task(heartbeat())

@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    sys.stdout.write("\u2705 Ping command triggered\n")
    sys.stdout.flush()
    await interaction.response.send_message("\U0001F3D3 Pong!")

# Validate and run bot
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    sys.stdout.write("\u274C DISCORD_TOKEN not found in environment!\n")
    sys.stdout.flush()
    exit(1)

bot.run(TOKEN)
