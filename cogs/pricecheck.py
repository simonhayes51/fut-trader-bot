import discord
from discord import app_commands
from discord.ext import commands
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
                players = json.load(f)
                logging.info("[LOAD] players_temp.json loaded successfully.")
                return players
        except Exception as e:
            logging.error(f"[ERROR] Couldn't load players: {e}")
            return []

    @app_commands.command(name="pricecheck", description="Check the current FUTBIN price of a player")
    @app_commands.describe(player="Enter player name and rating (e.g. Lamine Yamal 97)", platform="Choose platform")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Console", value="console"),
        app_commands.Choice(name="PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        await interaction.response.defer()

        try:
            logging.info(f"🧪 /pricecheck triggered by {interaction.user.name} for {player} on {platform.name}")

            # Match player from local list
            matched_player = next(
                (p for p in self.players if f"{p['name'].lower()} {p['rating']}" == player.lower()), None
            )

            if not matched_player:
                await interaction.followup.send("❌ Player not found in local data.")
                return

            player_id = matched_player["id"]
            player_name = matched_player["name"]
            rating = matched_player["rating"]
            slug = player_name.replace(" ", "-").lower()

            futbin_url = f"https://www.futbin.com/25/player/{player_id}/{slug}"
            logging.info(f"[PRICECHECK] URL: {futbin_url}")

            price = self.get_price(futbin_url)

            embed = discord.Embed(
                title=f"{player_name} ({rating})",
                description=f"**Platform:** {platform.name}\n**Price:** {price} 🪙",
                color=discord.Color.green()
            )
            embed.set_footer(text="Data from FUTBIN")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"[ERROR] pricecheck: {e}")
            await interaction.followup.send("⚠️ An error occurred while fetching the price.")

    def get_price(self, url):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            logging.info(f"🌐 [GET] {url} returned status {response.status_code}")
            soup = BeautifulSoup(response.text, "html.parser")

            price_div = soup.find("div", class_="price inline-with-icon lowest-price-1")
            if not price_div:
                logging.error("❌ Could not find the main price block")
                return "N/A"

            price_text = price_div.get_text(strip=True).replace(",", "")
            logging.info(f"💰 Found visible price: {price_text}")

            return f"{int(price_text):,}"  # format with commas

        except Exception as e:
            logging.error(f"[SCRAPE ERROR] {e}")
            return "N/A"

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            current = current.lower()
            suggestions = [
                app_commands.Choice(name=f"{p['name']} {p['rating']}", value=f"{p['name']} {p['rating']}")
                for p in self.players if current in f"{p['name']} {p['rating']}".lower()
            ][:25]
            return suggestions
        except Exception as e:
            logging.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
