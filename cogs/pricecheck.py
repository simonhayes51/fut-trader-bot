import discord
from discord import app_commands
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json
import logging

log = logging.getLogger("fut-pricecheck")

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()

    def load_players(self):
        try:
            with open("players_temp.json", "r", encoding="utf-8") as f:
                players = json.load(f)
                log.info("[LOAD] players_temp.json loaded successfully.")
                return players
        except Exception as e:
            log.error(f"[ERROR] Couldn't load players: {e}")
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
            log.info(f"[PRICECHECK] URL: {futbin_url}")

            price = self.get_price(futbin_url, platform.value)

            embed = discord.Embed(
                title=f"{player_name} ({rating})",
                description=f"**Platform:** {platform.name}\n**Price:** {price} 🪙",
                color=discord.Color.green()
            )
            embed.set_footer(text="Data from FUTBIN")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"[ERROR] pricecheck: {e}")
            await interaction.followup.send("⚠️ An error occurred while fetching the price.")

    def get_price(self, url, platform):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")

            prices_wrapper = soup.find("div", class_="lowest-prices-wrapper")
            if not prices_wrapper:
                log.error("[SCRAPE ERROR] Could not find prices wrapper")
                return "N/A"

            # DEBUG: Print out what we found
            log.info("[DEBUG] Found prices wrapper block")
            log.debug(prices_wrapper.prettify()[:1000])  # Only log the first 1000 characters

            price_elements = prices_wrapper.find_all("div", class_="lowest-price")

            def get_price_text(index):
                if len(price_elements) > index:
                    return price_elements[index].text.strip().replace(",", "").replace("\n", "")
                return "0"

            if platform == "console":
                ps_price = get_price_text(0)
                xbox_price = get_price_text(1)
                price = ps_price if ps_price != "0" else xbox_price
            elif platform == "pc":
                price = get_price_text(2)
            else:
                return "N/A"

            if price == "0" or price == "":
                return "N/A"

            log.info(f"[SCRAPE SUCCESS] Platform: {platform}, Price: {price}")
            return f"{int(price):,}"  # Adds commas

        except Exception as e:
            log.error(f"[SCRAPE ERROR] {e}")
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
            log.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
