import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import requests
import json
import os
from datetime import datetime

CONFIG_FILE = "autotrend_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_admin_or_owner(member: discord.Member) -> bool:
    if member.guild and member.id == member.guild.owner_id:
        return True
    allowed_roles = ["Admin", "Owner"]
    role_names = [role.name.lower() for role in member.roles]
    return any(allowed.lower() in role_names for allowed in allowed_roles)

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        # self.auto_post_trends.start()  # Enable if using auto-post

    @app_commands.command(name="trending", description="📊 Show top trending players")
    @app_commands.describe(direction="Choose trend direction", timeframe="Select timeframe")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller"),
            app_commands.Choice(name="📊 Both", value="both")
        ],
        timeframe=[
            app_commands.Choice(name="🗓️ 24 Hour", value="24h"),
            app_commands.Choice(name="🕓 4 Hour", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        if direction.value == "both":
            embed = await self.generate_combined_embed(timeframe.value)
        else:
            embed = await self.generate_trend_embed(direction.value, timeframe.value)

        if embed:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("⚠️ No trend data found.")

    async def generate_combined_embed(self, timeframe: str) -> discord.Embed:
        risers = await self.scrape_futbin_data("riser", timeframe)
        fallers = await self.scrape_futbin_data("faller", timeframe)
        if not risers and not fallers:
            return None

        time_emoji = "🕓" if timeframe == "4h" else "🗓️"
        title = f"📊 Top 5 Risers & Fallers (🎮 Console) – {time_emoji} {timeframe}"
        embed = discord.Embed(title=title, color=discord.Color.gold())
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        def format_entries(players, emoji, trend_prefix):
            lines = []
            for i, p in enumerate(players[:5]):
                booster = " 🚀" if emoji == "📈" and p["trend"] > 100 else ""
                booster = " ❄️" if emoji == "📉" and p["trend"] < -50 else booster
                trend_str = f"{trend_prefix}{abs(p['trend']):.2f}%{booster}"
                lines.append(f"**{p['name']} ({p['rating']})**\n💰 {p['price']}\n{emoji} {trend_str}\n")
            return "\n".join(lines)

        left = format_entries(risers, "📈", "")
        right = format_entries(fallers, "📉", "-")

        embed.add_field(name="📈 Top 5 Risers", value=left or "No data", inline=True)
        embed.add_field(name="📉 Top 5 Fallers", value=right or "No data", inline=True)
        return embed

    async def generate_trend_embed(self, direction: str, timeframe: str) -> discord.Embed:
        players = await self.scrape_futbin_data(direction, timeframe)
        if not players:
            return None

        emoji = "📈" if direction == "riser" else "📉"
        color = discord.Color.green() if direction == "riser" else discord.Color.red()
        time_emoji = "🕓" if timeframe == "4h" else "🗓️"
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console) – {time_emoji} {timeframe}"

        embed = discord.Embed(title=title, color=color)
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        for i, p in enumerate(players[:10]):
            booster = ""
            if direction == "riser" and p["trend"] > 100:
                booster = " 🚀"
            elif direction == "faller" and p["trend"] < -50:
                booster = " ❄️"
            trend_str = f"{p['trend']:.2f}%{booster}" if direction == "riser" else f"-{abs(p['trend']):.2f}%{booster}"
            embed.add_field(
                name=f"{i+1}. {p['name']} ({p['rating']})",
                value=f"💰 {p['price']}\n{emoji} {trend_str}",
                inline=False
            )

        return embed

    async def scrape_futbin_data(self, direction: str, timeframe: str):
        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        wrapper_class = "market-24-hours" if timeframe == "24h" else "market-4-hours"
        container = soup.select_one(f"div.market-players-wrapper.{wrapper_class}.m-row.space-between")
        if not container:
            return []

        players = []
        for card in container.select("a.market-player-card"):
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue

            trend_text = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
            try:
                trend = float(trend_text)
            except:
                continue

            if "day-change-negative" in trend_tag.get("class", []):
                trend = -abs(trend)
            else:
                trend = abs(trend)

            if direction == "riser" and trend <= 0:
                continue
            if direction == "faller" and trend >= 0:
                continue

            name = card.select_one(".playercard-s-25-name")
            rating = card.select_one(".playercard-s-25-rating")
            price_tag = card.select("div.platform-price-wrapper-small span.price")

            price = "?"
            if price_tag and len(price_tag) >= 1:
                price = price_tag[0].text.strip()  # Console is first span

            if not name or not rating:
                continue

            players.append({
                "name": name.text.strip(),
                "rating": rating.text.strip(),
                "trend": trend,
                "price": price
            })

        return sorted(players, key=lambda x: x["trend"], reverse=(direction == "riser"))

async def setup(bot):
    await bot.add_cog(Trending(bot))