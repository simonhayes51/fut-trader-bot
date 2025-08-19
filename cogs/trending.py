import discord
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup
import requests

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def fetch_players(self, trend_type: str):
        # Risers are at the end (pages 70-75), Fallers at start
        pages = range(75, 69, -1) if trend_type == "riser" else range(1, 6)
        players = []

        for page in pages:
            url = f"https://www.fut.gg/players/momentum/?page={page}"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, "html.parser")

            cards = soup.select("a.group\\/player")
            for card in cards:
                alt = card.find("img")['alt']
                try:
                    name, rating, version = alt.split(" - ", 2)
                except ValueError:
                    continue  # Skip malformed

                # Trend %
                trend_tag = card.select_one(".text-green-500, .text-red-500")
                if not trend_tag:
                    continue
                trend = trend_tag.text.strip()

                # Price
                price_tag = card.select_one("img[alt='Coin'] + div")
                price = price_tag.text.strip() if price_tag else "?"

                players.append({
                    "name": name,
                    "rating": rating,
                    "version": version,
                    "price": price,
                    "trend": trend
                })

                if len(players) >= 10:
                    break
            if len(players) >= 10:
                break

        return players

    @app_commands.command(name="trending", description="📊 Show top 10 Risers or Fallers on console")
    @app_commands.choices(
        trend_type=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ]
    )
    async def trending(self, interaction: discord.Interaction, trend_type: app_commands.Choice[str]):
        await interaction.response.defer()

        players = self.fetch_players(trend_type.value)
        emoji = "📈" if trend_type.value == "riser" else "📉"

        embed = discord.Embed(
            title=f"{emoji} Top 10 {trend_type.name} (🎮 Console)",
            color=discord.Color.green() if trend_type.value == "riser" else discord.Color.red()
        )

        if not players:
            embed.description = "No trending players found."
        else:
            for player in players:
                embed.add_field(
                    name=f"{player['name']} ({player['rating']})",
                    value=(
                        f"{player['version']}\n"
                        f"💰 {player['price']}\n"
                        f"{emoji} {player['trend']}"
                    ),
                    inline=False
                )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Trending(bot))
