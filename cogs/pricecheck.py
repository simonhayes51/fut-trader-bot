import discord
from discord.ext import commands
from discord import app_commands
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

    async def get_futbin_data(self, url, platform):
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        logger.info(f"🌐 [GET] {url} returned status {response.status_code}")
        soup = BeautifulSoup(response.text, 'html.parser')

        # Main price block (console/pc distinction happens here)
        price_block = soup.find("div", class_="price-box-original-player")
        if not price_block:
            logger.warning("❌ Couldn't find price block")
            return None

        # Get main price
        price_div = price_block.find("div", class_="price")
        price = price_div.text.strip().replace(",", "") if price_div else None

        # Get trend
        trend_block = price_block.find("div", class_="price-box-trend")
        trend = trend_block.text.replace("Trend:", "").strip() if trend_block else "N/A"

        # Get price range
        pr_block = price_block.find("div", class_="price-pr")
        price_range = pr_block.text.replace("PR:", "").strip() if pr_block else "N/A"

        # Get update time
        updated_div = price_block.find("div", class_="prices-updated")
        updated = updated_div.text.replace("Price Updated:", "").strip() if updated_div else "N/A"

        # Get player image
        img_tag = soup.find("img", class_="player_img")
        image_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else None

        return {
            "price": price,
            "trend": trend,
            "price_range": price_range,
            "updated": updated,
            "image_url": image_url
        }

    @app_commands.command(name="pricecheck", description="Check the current price of a FUT player")
    @app_commands.describe(player="Select a player", platform="Choose Console or PC")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Console (PS/Xbox)", value="console"),
        app_commands.Choice(name="PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        logger.info(f"🧪 /pricecheck triggered by {interaction.user.name} for {player} on {platform.name}")
        
        platform_value = platform.value

        matched = next((p for p in self.players if player.lower() in f"{p['name']} {p['rating']}").lower()), None)
        if not matched:
            await interaction.response.send_message("❌ Player not found.", ephemeral=True)
            return

        player_url = matched['url']
        player_name = matched['name']
        rating = matched['rating']

        logger.info(f"🔗 Scraping URL: {player_url}")
        futbin_data = await self.get_futbin_data(player_url, platform_value)

        if not futbin_data:
            await interaction.response.send_message("❌ Failed to fetch data from FUTBIN.", ephemeral=True)
            return

        price = int(futbin_data['price'].replace(",", "")) if futbin_data['price'] else 0
        trend = futbin_data['trend']
        price_range = futbin_data['price_range']
        updated = futbin_data['updated']
        image_url = futbin_data['image_url']

        embed = discord.Embed(
            title=f"{player_name} ({rating})",
            description=f"**Platform:** {platform.name}\n"
                        f"**Price:** {price:,} 🪙\n"
                        f"**Trend:** {trend}\n"
                        f"**Price Range:** {price_range}\n"
                        f"**Updated:** {updated}\n\n"
                        f"[View on FUTBIN]({player_url})",
            colour=discord.Colour.gold()
        )

        if image_url:
            embed.set_thumbnail(url=image_url)

        await interaction.response.send_message(embed=embed)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            suggestions = [
                app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=f"{p['name']} ({p['rating']})")
                for p in self.players if current.lower() in f"{p['name']} {p['rating']}").lower()
            ][:25]
            return suggestions
        except Exception as e:
            logger.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
