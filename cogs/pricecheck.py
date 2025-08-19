import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json
import logging

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

    @app_commands.command(name="pricecheck", description="Check a player's current FUTBIN price.")
    @app_commands.describe(player="Enter the name of the player", platform="Choose your platform")
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: str = "console"):
        log.info(f"🧪 /pricecheck by {interaction.user.name} for {player} on {platform}")
        match = next((p for p in self.players if f"{p['name']} {p['rating']}".lower() == player.lower()), None)

        if not match:
            await interaction.response.send_message("❌ Player not found.", ephemeral=True)
            return

        url = match["url"]
        log.info(f"🔗 Scraping URL: {url}")

        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            log.info(f"🌐 [GET] {url} returned {response.status_code}")
        except Exception as e:
            log.error(f"[SCRAPE ERROR] {e}")
            await interaction.response.send_message("❌ Failed to fetch player data.", ephemeral=True)
            return

        soup = BeautifulSoup(response.text, "html.parser")
        try:
            price_box = soup.find("div", class_="price-box-original-player")
            price_tag = price_box.find("div", class_="price inline-with-icon lowest-price-1")
            price = price_tag.text.strip() if price_tag else "N/A"

            trend_div = price_box.find("div", class_="price-box-trend")
            trend_text = trend_div.text.replace("Trend:", "").strip() if trend_div else "-"
            trend_emoji = "📈" if "+" in trend_text else "📉" if "-" in trend_text else "➖"
            trend = f"{trend_emoji} {trend_text}"

            range_div = price_box.find("div", class_="price-pr")
            price_range = range_div.text.replace("PR:", "").strip() if range_div else "-"

            update_div = price_box.find("div", class_="prices-updated")
            updated = update_div.text.replace("Price Updated:", "").strip() if update_div else "-"

        except Exception as e:
            log.warning(f"[WARN] Could not parse price data: {e}")
            await interaction.response.send_message("❌ Could not extract price data.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{match['name']} ({match['rating']})",
            description=f"Platform: {platform.capitalize()}",
            color=discord.Color.gold()
        )

        embed.add_field(name="Price", value=f"{price} 🪙", inline=True)
        embed.add_field(name="Trend", value=trend, inline=True)
        embed.add_field(name="Price Range", value=price_range, inline=True)
        embed.add_field(name="Club", value=match.get("club", "-"), inline=True)
        embed.add_field(name="Nation", value=match.get("nation", "-"), inline=True)
        embed.add_field(name="Position", value=match.get("position", "-"), inline=True)
        embed.set_footer(text=f"Updated: {updated} • Data from FUTBIN")
        embed.set_thumbnail(url=f"https://cdn.futbin.com/content/fifa25/img/players/{match['id']}.png")

        await interaction.response.send_message(embed=embed)

    @pricecheck.autocomplete("player")
    async def price_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            matches = [
                app_commands.Choice(name=f"{p['name']} {p['rating']}", value=f"{p['name']} {p['rating']}")
                for p in self.players
                if current.lower() in f"{p['name']} {p['rating']}".lower()
            ][:25]
            return matches
        except Exception as e:
            log.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))