import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import asyncio
import requests
from bs4 import BeautifulSoup

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def scrape_trending(self, trend_type: str):
        players = []
        headers = {"User-Agent": "Mozilla/5.0"}

        if trend_type == "riser":
            pages = range(75, 0, -1)  # Reverse order for risers
        else:
            pages = range(1, 76)      # Normal order for fallers

        for page in pages:
            url = f"https://www.fut.gg/players/momentum/?page={page}"
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select('a[href*="/players/"]')

            for card in cards:
                try:
                    alt = card.find("img").get("alt", "Unknown - ? - ?")
                    name, rating, card_type = alt.split(" - ")

                    # Get trend
                    trend_tag = card.select_one("div.font-bold.text-xs.text-green-500, div.font-bold.text-xs.text-red-500")
                    trend = trend_tag.text.strip() if trend_tag else "?"

                    if trend_type == "riser" and not trend.startswith("+"):
                        continue
                    if trend_type == "faller" and not trend.startswith("-"):
                        continue

                    # Get price
                    price_tag = card.select_one('div.flex.items-center.justify-center.grow.shrink-0.gap-[0.1em]')
                    price = price_tag.get_text(strip=True) if price_tag else "?"

                    players.append({
                        "name": name,
                        "rating": rating,
                        "card_type": card_type,
                        "price": price,
                        "trend": trend
                    })

                    if len(players) == 10:
                        return players
                except Exception as e:
                    continue

        return players

    @app_commands.command(name="trending", description="📊 Show top trending FUT players (console only)")
    @app_commands.choices(trend_type=[
        app_commands.Choice(name="📈 Risers", value="riser"),
        app_commands.Choice(name="📉 Fallers", value="faller")
    ])
    async def trending(self, interaction: discord.Interaction, trend_type: app_commands.Choice[str]):
        await interaction.response.defer()
        players = self.scrape_trending(trend_type.value)

        emoji = "📈" if trend_type.value == "riser" else "📉"
        embed = discord.Embed(
            title=f"{emoji} Top 10 {emoji} {'Risers' if trend_type.value == 'riser' else 'Fallers'} (🎮 Console)",
            color=discord.Color.green() if trend_type.value == "riser" else discord.Color.red(),
            timestamp=datetime.utcnow()
        )

        if not players:
            embed.description = "No trending players found."
        else:
            for player in players:
                embed.add_field(
                    name=f"{player['name']} ({player['rating']})",
                    value=(
                        f"{player['card_type']}\n"
                        f"💰 {player['price']}\n"
                        f"{emoji} {player['trend']}"
                    ),
                    inline=False
                )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Trending(bot))
