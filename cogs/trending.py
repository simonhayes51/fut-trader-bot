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
        self.auto_post_trends.start()

    @app_commands.command(name="trending", description="📊 Show top trending players (Risers/Fallers)")
    @app_commands.describe(direction="Risers or Fallers", period="🗓️ 24h or 🕓 4h market data")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ],
        period=[
            app_commands.Choice(name="🗓️ 24h", value="24h"),
            app_commands.Choice(name="🕓 4h", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], period: app_commands.Choice[str] = None):
        await interaction.response.defer()
        period_value = period.value if period else "24h"
        embed = await self.generate_trend_embed(direction.value, period_value)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM 24hr)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 09:00)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only the server owner or users with the 'Admin' or 'Owner' role can use this command.", ephemeral=True)
            return

        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use HH:MM (24-hour)", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-trending set to post daily at **{post_time}** in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue

            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue

            for direction in ["riser", "faller"]:
                embed = await self.generate_trend_embed(direction, "24h")
                await channel.send(embed=embed)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    async def generate_trend_embed(self, direction: str, period: str) -> discord.Embed:
        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        section_class = {
            ("riser", "24h"): "market-gain",
            ("faller", "24h"): "market-losers",
            ("riser", "4h"): "market-gain-4h",
            ("faller", "4h"): "market-losers-4h"
        }.get((direction, period), "market-gain")

        section = soup.find("div", class_=section_class)
        if not section:
            return discord.Embed(title="Error", description="Unable to fetch market data.", color=discord.Color.red())

        cards = section.select("a.market-player-card")
        players = []
        seen = set()

        for card in cards:
            name_tag = card.select_one(".playercard-s-25-name")
            rating_tag = card.select_one(".playercard-s-25-rating")
            trend_tag = card.select_one(".market-player-change")
            price_tag = card.select_one(".platform-price-wrapper-small")

            if not all([name_tag, rating_tag, trend_tag]):
                continue

            name = name_tag.text.strip()
            rating = rating_tag.text.strip()
            full_name = f"{name} ({rating})"

            if full_name in seen:
                continue
            seen.add(full_name)

            trend_text = trend_tag.text.strip().replace("%", "").replace(",", "").replace("+", "")
            try:
                trend = float(trend_text)
            except ValueError:
                continue

            price = price_tag.text.strip() if price_tag else "?"
            players.append({"name": name, "rating": rating, "trend": trend, "price": price})

        sorted_players = sorted(players, key=lambda x: x["trend"], reverse=(direction == "riser"))[:10]

        emoji = "📈" if direction == "riser" else "📉"
        booster_threshold = 100 if direction == "riser" else -50
        booster_emoji = "🚀" if direction == "riser" else "❄️"
        time_emoji = "🗓️" if period == "24h" else "🕓"

        embed = discord.Embed(
            title=f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console)",
            description=f"{time_emoji} Data from FUTBIN | Prices are estimates",
            color=discord.Color.green() if direction == "riser" else discord.Color.red()
        )

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left = ""
        right = ""

        for i, p in enumerate(sorted_players):
            booster = booster_emoji if ((direction == "riser" and p["trend"] > booster_threshold) or (direction == "faller" and p["trend"] < booster_threshold)) else ""
            trend_str = f"{emoji} {'-' if direction == 'faller' else ''}{p['trend']:.2f}% {booster}".strip()
            entry = f"**{number_emojis[i]} {p['name']} ({p['rating']})**\n💰 {p['price']}\n{trend_str}\n\n"
            if i < 5:
                left += entry
            else:
                right += entry

        embed.add_field(name="\u200b", value=left, inline=True)
        embed.add_field(name="\u200b", value=right, inline=True)
        return embed


async def setup(bot):
    await bot.add_cog(Trending(bot))
