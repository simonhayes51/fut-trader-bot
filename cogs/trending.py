import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="trending", description="📊 Show top trending players")
    @app_commands.describe(
        direction="Choose trend direction",
        period="Choose timeframe"
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ],
        period=[
            app_commands.Choice(name="🗓️ 24 Hour", value="24h"),
            app_commands.Choice(name="🕓 4 Hour", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], period: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_embed(direction.value, period.value)
        if embed:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Could not fetch market data.")

    async def generate_embed(self, direction, period) -> discord.Embed:
        data = self.scrape_futbin_data(direction, period)
        if not data:
            return None

        emoji = "📈" if direction == "riser" else "📉"
        color = discord.Color.green() if direction == "riser" else discord.Color.red()
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console) – {period}"

        embed = discord.Embed(title=title, color=color)
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, p in enumerate(data[:10]):
            boost = ""
            if direction == "riser" and p["trend"] > 100:
                boost = " 🚀"
            elif direction == "faller" and p["trend"] < -50:
                boost = " ❄️"

            trend = f"-{p['trend']:.2f}%" if direction == "faller" else f"{p['trend']:.2f}%"
            embed.add_field(
                name=f"{number_emojis[i]} {p['name']} ({p['rating']})",
                value=f"💰 {p['price']}\n{emoji} {trend}{boost}",
                inline=False
            )

        return embed

    def scrape_futbin_data(self, direction, period):
        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        wrapper_class = "market-24-hours" if period == "24h" else "market-4-hours"
        wrapper = soup.select_one(f"div.market-players-wrapper.{wrapper_class}.m-row.space-between")
        if not wrapper:
            return []

        cards = wrapper.select("a.market-player-card")
        players = []

        for card in cards:
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue

            try:
                trend = float(trend_tag.text.replace("%", "").replace("+", "").replace(",", ""))
            except:
                continue

            if direction == "riser" and trend <= 0:
                continue
            if direction == "faller" and trend >= 0:
                continue

            name = card.select_one(".playercard-s-25-name")
            rating = card.select_one(".playercard-s-25-rating")
            price = card.select_one(".platform-price-wrapper-small")

            if not (name and rating and price):
                continue

            players.append({
                "name": name.text.strip(),
                "rating": rating.text.strip(),
                "price": price.text.strip(),
                "trend": trend
            })

        return sorted(players, key=lambda x: x["trend"], reverse=(direction == "riser"))[:10]

async def setup(bot):
    await bot.add_cog(Trending(bot))
