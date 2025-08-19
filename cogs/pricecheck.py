import discord
from discord import app_commands
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json
import logging

logger = logging.getLogger("fut-pricecheck")

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()

    def load_players(self):
        try:
            with open("players_temp.json", "r", encoding="utf-8") as f:
                players = json.load(f)
                logger.info("[LOAD] players_temp.json loaded successfully.")
                return players
        except Exception as e:
            logger.error(f"[ERROR] Couldn't load players: {e}")
            return []

    @app_commands.command(name="pricecheck", description="Check the current FUTBIN price of a player")
    @app_commands.describe(player="Enter player name and rating (e.g. Lamine Yamal 99)", platform="Choose platform")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Console", value="console"),
        app_commands.Choice(name="PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        await interaction.response.defer()
        logger.info(f"\U0001F9EA /pricecheck triggered by {interaction.user.name} for {player} on {platform.name}")

        try:
            matched_player = next(
                (p for p in self.players if f"{p['name'].lower()} {p['rating']}" == player.lower()), None
            )

            if not matched_player:
                await interaction.followup.send("❌ Player not found in local data.")
                return

            futbin_url = matched_player.get("url")
            if not futbin_url:
                await interaction.followup.send("❌ No URL found for this player.")
                return

            logger.info(f"\U0001F517 Scraping URL: {futbin_url}")
            price = self.get_price(futbin_url)

            embed = discord.Embed(
                title=f"{matched_player['name']} ({matched_player['rating']})",
                description=f"**Platform:** {platform.name}\n**Price:** {price} \U0001FA99",
                color=discord.Color.green()
            )
            embed.set_footer(text="Data from FUTBIN")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"[ERROR] pricecheck: {e}")
            await interaction.followup.send("⚠️ An error occurred while fetching the price.")

    def get_price(self, url):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            logger.info(f"🌐 [GET] {url} returned status {response.status_code}")
            soup = BeautifulSoup(response.text, "html.parser")

            price_element = soup.find("div", class_="price inline-with-icon lowest-price-1")
            if price_element:
                logger.info("[DEBUG] Found correct price block")
                raw_price = price_element.text.strip().replace(",", "").replace("\n", "")
                if raw_price.isdigit():
                    return f"{int(raw_price):,}"
                return raw_price
            else:
                logger.warning("[WARN] Could not find main price element")
                return "N/A"
        except Exception as e:
            logger.error(f"[SCRAPE ERROR] {e}")
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
            logger.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
