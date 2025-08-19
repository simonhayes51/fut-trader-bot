import discord
from discord import app_commands
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json
import logging

log = logging.getLogger("fut-pricecheck")
log.setLevel(logging.INFO)

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
        log.info(f"🧪 /pricecheck triggered by {interaction.user.name} for {player} on {platform.name}")
        await interaction.response.defer()

        try:
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
            log.info(f"🔗 Scraping URL: {futbin_url}")
            data = self.get_price_details(futbin_url, platform.value)

            if data["price"] == "N/A":
                await interaction.followup.send("❌ Failed to fetch price.")
                return

            embed = discord.Embed(
                title=f"{player_name} ({rating})",
                description=(
                    f"**Platform:** {platform.name}\n"
                    f"**Price:** {data['price']} 🪙\n"
                    f"📉 **Trend:** {data['trend']}\n"
                    f"📊 **Range:** {data['range']}\n"
                    f"⏱ **Updated:** {data['updated']}"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text="Data from FUTBIN")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"[ERROR] pricecheck: {e}")
            await interaction.followup.send("⚠️ An error occurred while fetching the price.")

    def get_price_details(self, url, platform):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            log.info(f"🌐 [GET] {url} returned status {response.status_code}")
            soup = BeautifulSoup(response.text, "html.parser")

            price_box = soup.find("div", class_="price-box")
            trend = soup.select_one(".price-box-trend .semi-bold")
            updated = soup.select_one(".prices-updated")
            pr_range = soup.select_one(".price-pr")
            main_price = soup.find("div", class_="price inline-with-icon lowest-price-1")

            data = {
                "price": main_price.text.strip().replace(",", "") if main_price else "N/A",
                "trend": trend.text.strip() if trend else "N/A",
                "updated": updated.text.strip().replace("Price Updated:", "") if updated else "N/A",
                "range": pr_range.text.replace("PR:", "").strip() if pr_range else "N/A"
            }

            log.info(f"📦 Final scrape: Price={data['price']}, Trend={data['trend']}, Range={data['range']}, Updated={data['updated']}")
            return data

        except Exception as e:
            log.error(f"[SCRAPE ERROR] {e}")
            return {"price": "N/A", "trend": "N/A", "updated": "N/A", "range": "N/A"}

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
