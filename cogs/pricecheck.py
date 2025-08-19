import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json
import logging

# Logger setup
log = logging.getLogger("fut-pricecheck")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

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
            log.error(f"[ERROR] Failed to load players: {e}")
            return []

    @app_commands.command(name="pricecheck", description="Check a player's FUTBIN price")
    @app_commands.describe(player="Name and rating (e.g. Lamine Yamal 99)", platform="Platform: console or pc")
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: str = "console"):
        await interaction.response.defer(thinking=True)
        platform = platform.lower()

        match = next((p for p in self.players if f"{p['name']} {p['rating']}".lower() == player.lower()), None)
        if not match:
            await interaction.followup.send("❌ Player not found.", ephemeral=True)
            return

        url = match["url"]
        player_id = match["id"]
        log.info(f"🔗 Scraping URL: {url}")

        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            log.error(f"[SCRAPE ERROR] {e}")
            await interaction.followup.send("❌ Failed to fetch price data.")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        price_box = soup.find("div", class_="price-box-original-player")
        if not price_box:
            await interaction.followup.send("❌ Couldn't find price data on page.")
            return

        try:
            if platform == "pc":
                price_div = price_box.find("div", class_="pc", recursive=True)
            else:
                price_div = price_box.find("div", class_="price inline-with-icon lowest-price-1")

            coin_price = price_div.text.strip().replace(",", "") if price_div else "N/A"
            coin_price = f"{int(coin_price):,}" if coin_price != "N/A" else coin_price

            trend_block = price_box.find("div", class_="price-box-trend")
            trend_text = trend_block.text.replace("Trend:", "").strip() if trend_block else "-"
            trend_emoji = "📈" if "-" not in trend_text else "📉"
            trend = f"{trend_emoji} {trend_text}"

            range_block = price_box.find("div", class_="price-pr")
            price_range = range_block.text.replace("PR:", "").strip() if range_block else "-"

            updated_block = price_box.find("div", class_="prices-updated")
            updated = updated_block.text.replace("Price Updated:", "").strip() if updated_block else "-"

            # Build embed
            embed = discord.Embed(
                title=f"{match['name']} ({match['rating']})",
                description=f"Platform: {platform.capitalize()}",
                color=0xFFD700
            )
            embed.add_field(name="Price", value=f"{coin_price} 🪙", inline=False)
            embed.add_field(name="Trend", value=trend, inline=False)
            embed.add_field(name="Price Range", value=price_range, inline=False)
            embed.add_field(name="Club", value=match['club'], inline=False)
            embed.add_field(name="Nation", value=match['nation'], inline=False)
            embed.add_field(name="Position", value=match['position'], inline=False)

            image_url = f"https://cdn.futbin.com/content/fifa25/img/players/{player_id}.png"
            embed.set_thumbnail(url=image_url)
            embed.set_footer(text=f"Updated: {updated} • Data from FUTBIN")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"[ERROR] Exception during pricecheck: {e}")
            await interaction.followup.send("❌ Error parsing price data.")

    @pricecheck.autocomplete("player")
    async def price_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            suggestions = [
                app_commands.Choice(name=f"{p['name']} {p['rating']}", value=f"{p['name']} {p['rating']}")
                for p in self.players if current.lower() in f"{p['name']} {p['rating']}".lower()
            ][:25]
            return suggestions
        except Exception as e:
            log.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))