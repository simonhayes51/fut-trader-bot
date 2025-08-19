import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json
import logging

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()

    def load_players(self):
        try:
            with open("players_temp.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                logging.info("[LOAD] players_temp.json loaded successfully.")
                return data
        except Exception as e:
            logging.error(f"[ERROR] Failed to load players_temp.json: {e}")
            return []

    @app_commands.command(name="pricecheck", description="Check the FUT price of a player.")
    @app_commands.describe(player="Name of the player", platform="Platform: console or pc")
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: str = "console"):
        await interaction.response.defer()

        try:
            player_data = next(
                (p for p in self.players if player.lower() in f"{p['name']} {p['rating']}".lower()),
                None
            )

            if not player_data:
                await interaction.followup.send("❌ Player not found.")
                return

            url = player_data.get("url")
            logging.info(f"[PRICECHECK] Scraping URL: {url}")
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

            if response.status_code != 200:
                await interaction.followup.send("❌ Failed to fetch player data.")
                return

            soup = BeautifulSoup(response.text, "html.parser")

            price_block = soup.find("div", class_="price-box", attrs={"data-id": player_data['id']})
            if not price_block:
                await interaction.followup.send("❌ Price data not found.")
                return

            main_price = price_block.find("div", class_="price inline-with-icon lowest-price-1")
            trend = price_block.find("div", class_="price-box-trend")
            price_range = price_block.find("div", class_="price-pr")
            update_time = price_block.find("div", class_="prices-updated")

            coin_price = main_price.text.strip() if main_price else "Unknown"
            trend_value = trend.text.strip().replace("Trend:", "") if trend else "-"
            price_range_text = price_range.text.strip().replace("PR:", "") if price_range else "-"
            updated = update_time.text.strip().replace("Price Updated:", "") if update_time else "-"

            embed = discord.Embed(
