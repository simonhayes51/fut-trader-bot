import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def fetch_trending(self, trend_type):
        # Use correct page depending on trend type
        page = 1 if trend_type == "fallers" else 75
        url = f"https://www.fut.gg/players/momentum/?page={page}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        cards = soup.find_all("a", class_="group/player")
        players = []

        for card in cards:
            alt_text = card.find("img")['alt'] if card.find("img") else None
            if not alt_text:
                continue

            try:
                name_rating, card_type = alt_text.split(" - ", 1)
                if " - " in card_type:
                    card_type = card_type.split(" - ")[0].strip()
            except ValueError:
                continue

            # Pull trend %
            trend_div = card.find("div", class_="text-green-500") or card.find("div", class_="text-red-500")
            trend = trend_div.get_text(strip=True) if trend_div else "?"

            # Pull price
            coin_img = card.find("img", {"alt": "Coin"})
            price = coin_img.next_sibling.strip() if coin_img and coin_img.next_sibling else "?"

            players.append({
                "name": name_rating,
                "type": card_type,
                "price": price,
                "trend": trend
            })

        return players[:10]  # Top 10 only

    @app_commands.command(name="trending", description="📊 Show top trending players on console")
    @app_commands.choices(
        trend_type=[
            app_commands.Choice(name="📈 Risers", value="risers"),
            app_commands.Choice(name="📉 Fallers", value="fallers")
        ]
    )
    async def trending(self, interaction: discord.Interaction, trend_type: app_commands.Choice[str]):
        await interaction.response.defer()
        players = self.fetch_trending(trend_type.value)

        emoji = "📈" if trend_type.value == "risers" else "📉"
        embed = discord.Embed(
            title=f"{emoji} Top 10 {trend_type.name} (\U0001F3AE Console)",
            color=discord.Color.green() if trend_type.value == "risers" else discord.Color.red()
        )

        if not players:
            embed.description = "No trending players found."
        else:
            for player in players:
                embed.add_field(
                    name=f"{player['name']}",
                    value=(
                        f"{player['type']}\n"
                        f"💰 {player['price']}\n"
                        f"{emoji} {player['trend']}"
                    ),
                    inline=False
                )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Trending(bot))
