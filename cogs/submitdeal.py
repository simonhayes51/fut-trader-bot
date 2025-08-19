import discord
from discord.ext import commands
from discord import app_commands

class SubmitDeal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tree = bot.tree  # Hook into the bot's command tree

    @app_commands.command(name="submitdeal", description="📬 Share a FUT trading tip with the server!")
    @app_commands.describe(
        name="Player name",
        version="Card version (e.g. Gold Rare, TOTW, TOTS)",
        buy_price="Buy price in coins",
        sell_time="When to sell (e.g. in 2 days, post SBC, etc)",
        platform="Platform used",
