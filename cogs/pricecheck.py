import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pricecheck", description="Check the price of a FUT player")
    @app_commands.describe(player_name="The name of the player")
    async def pricecheck(self, interaction: discord.Interaction, player_name: str):
        await interaction.response.defer(thinking=True)

        try:
            # Search Futbin for the player
            search_url = f"https://www.futbin.com/search?year=24&term={player_name}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest"
            }

            search_response = requests.get(search_url, headers=headers)
            if search_response.status_code != 200:
                await interaction.followup.send("❌ Failed to fetch data from Futbin.")
                return

            results = search_response.json()
            if not results:
                await interaction.followup.send("❌ No results found for that player.")
                return

            player = results[0]
            player_id = player["id"]
            player_name = player["name"]
            player_image = f"https://cdn.futbin.com/content/fifa24/img/players/{player_id}.png"
            player_url = f"https://www.futbin.com/24/player/{player_id}"

            # Get player page
            player_response = requests.get(player_url, headers=headers)
            if player_response.status_code != 200:
                await interaction.followup.send("❌ Failed to fetch player details.")
                return

            soup = BeautifulSoup(player_response.text, "html.parser")
            price_data = soup.find("div", class_="price-graph-tab price-graph-tab-0")

            if price_data is None:
                await interaction.followup.send("❌ Couldn't find price data.")
                return

            # Extract price data
            ps_data = json.loads(price_data.get("data-ps-data", "[]"))
            pc_data = json.loads(price_data.get("data-pc-data", "[]"))

            latest_ps_price = ps_data[-1][1] if ps_data else "N/A"
            latest_pc_price = pc_data[-1][1] if pc_data else "N/A"

            # Format and send the embed
            embed = discord.Embed(
                title=f"{player_name} Price Check",
                url=player_url,
                description=f"[View on Futbin]({player_url})",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=player_image)
            embed.add_field(name="🎮 Console Price", value=f"{int(latest_ps_price):,} coins" if isinstance(latest_ps_price, int) else latest_ps_price, inline=True)
            embed.add_field(name="🖥️ PC Price", value=f"{int(latest_pc_price):,} coins" if isinstance(latest_pc_price, int) else latest_pc_price, inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: `{str(e)}`")

    @pricecheck.autocomplete("player_name")
    async def autocomplete_player(self, interaction: discord.Interaction, current: str):
        try:
            search_url = f"https://www.futbin.com/search?year=24&term={current}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest"
            }

            search_response = requests.get(search_url, headers=headers)
            if search_response.status_code != 200:
                return []

            results = search_response.json()
            choices = [
                app_commands.Choice(name=player["name"], value=player["name"])
                for player in results[:25]
            ]
            return choices

        except Exception as e:
            print(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
