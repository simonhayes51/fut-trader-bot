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
        self.logger = logging.getLogger("fut-pricecheck")

    def load_players(self):
        try:
            with open("players_temp.json", "r", encoding="utf-8") as f:
                players = json.load(f)
                self.logger.info("[LOAD] players_temp.json loaded successfully.")
                return players
        except Exception as e:
            self.logger.error(f"[LOAD ERROR] Failed to load players: {e}")
            return []

    def format_coin_value(self, value):
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return "N/A"

    @app_commands.command(name="pricecheck", description="Check a player's price on FUTBIN")
    @app_commands.describe(player="Name of the player", platform="Choose Console or PC")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Console", value="console"),
        app_commands.Choice(name="PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        self.logger.info(f"🧪 /pricecheck triggered by {interaction.user.name} for {player} on {platform.value}")

        matching_players = [p for p in self.players if player.lower() in f"{p['name']} {p['rating']}"]
        if not matching_players:
            await interaction.response.send_message(f"❌ No player found matching '{player}'")
            return

        selected_player = matching_players[0]
        url = selected_player['url']
        self.logger.info(f"🔗 Scraping URL: {url}")

        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            self.logger.info(f"🌐 [GET] {url} returned status {res.status_code}")
            if res.status_code != 200:
                raise Exception("Page not found")

            soup = BeautifulSoup(res.text, "html.parser")
            price_box = soup.find("div", class_="price-box-original-player")

            if not price_box:
                await interaction.response.send_message("❌ Could not find price information.")
                return

            price_element = price_box.select_one(".price")
            trend_element = price_box.select_one(".price-box-trend .semi-bold")
            update_time = price_box.select_one(".prices-updated")
            pr_range = price_box.select_one(".price-pr")

            price_text = price_element.text.strip().split("\n")[0] if price_element else "N/A"
            trend_text = trend_element.text.strip() if trend_element else "N/A"
            update_text = update_time.text.strip() if update_time else "N/A"
            range_text = pr_range.text.strip().replace("PR: ", "") if pr_range else "N/A"

            coin_value = self.format_coin_value(price_text.replace(",", "").replace("\u202f", ""))

            embed = discord.Embed(
                title=f"{selected_player['name']} ({selected_player['rating']})",
                description=f"**Platform:** {platform.name}\n**Price:** {coin_value} 🪙\n**📉 Trend:** {trend_text}\n**📊 Range:** {range_text}\n**⏱ Updated:** {update_text}",
                color=discord.Color.gold()
            )

            player_image_url = f"https://cdn.futbin.com/content/fifa25/img/players/{selected_player['id']}.png"
            embed.set_thumbnail(url=player_image_url)
            embed.set_footer(text="Data from FUTBIN")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            self.logger.error(f"[ERROR] Failed to scrape or parse data: {e}")
            await interaction.response.send_message("❌ Failed to fetch player data.")

    @pricecheck.autocomplete("player")
    async def autocomplete_player(self, interaction: discord.Interaction, current: str):
        try:
            suggestions = [
                app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=p['name'])
                for p in self.players if current.lower() in f"{p['name']} {p['rating']}".lower()
            ][:25]
            return suggestions
        except Exception as e:
            self.logger.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []

def setup(bot):
    bot.add_cog(PriceCheck(bot))
