import discord
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup
import requests

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="trending", description="📊 Show top trending players (Risers/Fallers)")
    @app_commands.describe(direction="Risers or Fallers")
    @app_commands.choices(direction=[
        app_commands.Choice(name="📈 Risers", value="riser"),
        app_commands.Choice(name="📉 Fallers", value="faller")
    ])
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str]):
        await interaction.response.defer()

        # Check latest page dynamically if needed
        max_page = 76
        pages = range(max_page, 0, -1) if direction.value == "riser" else range(1, max_page + 1)
        all_players = []

        for page in pages:
            url = f"https://www.fut.gg/players/momentum/?page={page}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")

            player_blocks = soup.select("a[href^='/players/'][class*='group/player']")
            for block in player_blocks:
                name_tag = block.find("img", alt=True)
                if not name_tag:
                    continue
                alt = name_tag["alt"].strip()
                split_alt = alt.split(" - ")
                if len(split_alt) != 3:
                    continue
                name, rating, card_type = split_alt

                trend_tag = block.select_one("div.text-green-500, div.text-red-500")
                if not trend_tag:
                    continue
                trend_text = trend_tag.text.strip().replace('%', '').replace('+', '').replace('−', '-')
                try:
                    trend = float(trend_text)
                except ValueError:
                    continue

                price = "?"
                coin_tag = block.find("img", alt="Coin")
                if coin_tag and coin_tag.parent:
                    parent_text = coin_tag.parent.get_text(strip=True).replace("Coin", "").strip()
                    price = parent_text

                all_players.append({
                    "name": name,
                    "rating": rating,
                    "card_type": card_type,
                    "price": price,
                    "trend": trend
                })

        if direction.value == "riser":
            all_players = sorted(all_players, key=lambda x: x["trend"], reverse=True)
        top10 = all_players[:10]

        emoji = "📈" if direction.value == "riser" else "📉"
        title = f"{emoji} Top 10 {direction.name} (🎮 Console)"
        embed = discord.Embed(title=title, color=discord.Color.green() if direction.value == "riser" else discord.Color.red())

        if not top10:
            embed.description = "No trending players found."
        else:
            for p in top10:
                embed.add_field(
                    name=f"{p['name']} ({p['rating']})",
                    value=(
                        f"{p['card_type']}\n"
                        f"💰 {p['price']}\n"
                        f"{emoji} {p['trend']}%"
                    ),
                    inline=False
                )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Trending(bot))
