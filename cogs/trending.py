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
    @app_commands.describe(
        direction="Select Risers or Fallers",
        timeframe="Time period to check: 24h or 4h"
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="📈 Risers", value="riser"),
        app_commands.Choice(name="📉 Fallers", value="faller")
    ], timeframe=[
        app_commands.Choice(name="🗓️ 24h", value="24"),
        app_commands.Choice(name="🕓 4h", value="4")
    ])
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM 24hr)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 09:00)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins or Owners can use this command.", ephemeral=True)
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
                embed = await self.generate_trend_embed(direction, "24")
                await channel.send(embed=embed)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    async def generate_trend_embed(self, direction: str, timeframe: str) -> discord.Embed:
        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        container_class = f"market-players-wrapper market-{timeframe}-hours m-row space-between"
        container = soup.find("div", class_=container_class)

        if not container:
            embed = discord.Embed(title="Error", description="No trend data available.", color=discord.Color.red())
            return embed

        cards = container.select("a.market-player-card")
        players = []

        seen = set()
        for card in cards:
            # Name and rating
            name_tag = card.select_one(".playercard-s-25-name")
            rating_tag = card.select_one(".playercard-s-25-rating")
            if not name_tag or not rating_tag:
                continue
            name = name_tag.text.strip()
            rating = rating_tag.text.strip()
            unique_key = f"{name}-{rating}"
            if unique_key in seen:
                continue
            seen.add(unique_key)

            # Price
            price_tag = card.select_one(".platform-price-wrapper-small")
            price = price_tag.text.strip() if price_tag else "?"

            # Trend %
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue
            trend_text = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
            try:
                trend = float(trend_text)
            except ValueError:
                continue

            # Filter based on trend
            if direction == "riser" and trend <= 0:
                continue
            if direction == "faller" and trend >= 0:
                continue

            players.append({
                "name": name,
                "rating": rating,
                "price": price,
                "trend": trend
            })

        if not players:
            embed = discord.Embed(title="Error", description="No trend data found.", color=discord.Color.red())
            return embed

        players.sort(key=lambda x: x["trend"], reverse=(direction == "riser"))
        top10 = players[:10]

        emoji = "📈" if direction == "riser" else "📉"
        time_emoji = "🗓️" if timeframe == "24" else "🕓"
        timeframe_text = "Last 24 Hours" if timeframe == "24" else "Last 4 Hours"
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console) – {time_emoji} {timeframe_text}"

        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left, right = "", ""

        for i, p in enumerate(top10):
            trend = p["trend"]
            booster = ""
            if direction == "riser" and trend > 100:
                booster = " 🚀"
            elif direction == "faller" and trend < -50:
                booster = " ❄️"
            trend_display = f"{trend:.2f}%" if direction == "riser" else f"-{trend:.2f}%"
            entry = (
                f"{number_emojis[i]} **{p['name']} ({p['rating']})**\n"
                f"💰 {p['price']}\n"
                f"{emoji} {trend_display}{booster}\n\n"
            )
            if i < 5:
                left += entry
            else:
                right += entry

        embed.add_field(name="\u200b", value=left.strip(), inline=True)
        embed.add_field(name="\u200b", value=right.strip(), inline=True)

        return embed

async def setup(bot):
    await bot.add_cog(Trending(bot))
