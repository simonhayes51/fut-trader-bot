import discord
from discord import app_commands
from discord.ext import commands
from bs4 import BeautifulSoup
import requests
import json

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("players_temp.json", "r", encoding="utf-8") as f:
            self.players = json.load(f)

    @app_commands.command(name="pricecheck", description="Check the current FUTBIN price of a player")
    @app_commands.describe(player="Enter player name and rating e.g. Georgia Stanway 91")
    async def pricecheck(self, interaction: discord.Interaction, player: str):
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
            player_rating = matched_player["rating"]

            futbin_url = f"https://www.futbin.com/25/player/{player_id}/{player_name.replace(' ', '-').lower()}"
            price = self.get_price_from_futbin(futbin_url)

            embed = discord.Embed(
                title=f"{player_name} ({player_rating})",
                description=f"Platform: **Console**\nPrice: **{price}**",
                color=discord.Color.green()
            )
            embed.set_footer(text="Live price from FUTBIN")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[ERROR] pricecheck: {e}")
            await interaction.followup.send("⚠️ An error occurred while fetching the price.")

    def get_price_from_futbin(self, url):
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, "html.parser")
            price_div = soup.find("div", class_="lowest-price inline-with-icon")
            return price_div.text.strip() if price_div else "N/A"
        except Exception as e:
            print(f"[SCRAPE ERROR] {e}")
            return "N/A"

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        suggestions = []
        for p in self.players:
            full_name = f"{p['name']} {p['rating']}"
            if current.lower() in full_name.lower():
                suggestions.append(app_commands.Choice(name=full_name, value=full_name))
            if len(suggestions) >= 25:
                break
        return suggestions

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
