import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json

class PriceCheckGG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()

    def load_players(self):
        try:
            with open("futgg_players.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Couldn't load FUT.GG players: {e}")
            return []

    def get_futgg_price(self, url):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            # Correct div target for price
            price_div = soup.find("div", class_="font-bold text-2xl flex flex-row items-center gap-1 justify-self-end")
            if price_div:
                return price_div.text.strip()
            return "N/A"
        except Exception as e:
            print(f"[FUTGG ERROR] {e}")
            return "N/A"

    @app_commands.command(name="pricecheckgg", description="Check a player's coin value from FUT.GG")
    @app_commands.describe(player="Enter player name and rating (e.g. Haaland 92)")
    async def pricecheckgg(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()

        try:
            matched_player = next(
                (p for p in self.players if f"{p['name'].lower()} {p['rating']}" == player.lower()),
                None
            )

            if not matched_player:
                await interaction.followup.send("❌ Player not found in FUT.GG local data.")
                return

            price = self.get_futgg_price(matched_player['url'])

            embed = discord.Embed(
                title=f"{matched_player['name']} ({matched_player['rating']})",
                description=f"💰 **Value:** `{price}`\n🔗 [View on FUT.GG]({matched_player['url']})",
                color=discord.Color.gold()
            )
            embed.set_footer(text="Live market data from FUT.GG")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[ERROR] pricecheckgg: {e}")
            await interaction.followup.send("⚠️ An error occurred while fetching the price.")

    @pricecheckgg.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        return [
            app_commands.Choice(name=f"{p['name']} {p['rating']}", value=f"{p['name']} {p['rating']}")
            for p in self.players if current in f"{p['name']} {p['rating']}".lower()
        ][:25]
            return suggestions
        except Exception as e:
            print(f"[AUTOCOMPLETE ERROR] {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheckGG(bot))
