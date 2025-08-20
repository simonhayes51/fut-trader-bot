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
    @app_commands.describe(direction="Risers or Fallers")
    @app_commands.choices(direction=[
        app_commands.Choice(name="📈 Risers", value="riser"),
        app_commands.Choice(name="📉 Fallers", value="faller")
    ])
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value)
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
                embed = await self.generate_trend_embed(direction)
                await channel.send(embed=embed)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    async def generate_trend_embed(self, direction: str) -> discord.Embed:
        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        if direction == "riser":
            section = soup.find("div", class_="market-gain xs-column active")
            emoji = "📈"
            boost_threshold = 100
            boost_emoji = "🚀"
            embed_color = discord.Color.green()
            title = "📈 Top 10 Risers (🎮 Console)"
        else:
            section = soup.find("div", class_="market-losers xs-column")
            emoji = "📉"
            boost_threshold = 50
            boost_emoji = "❄️"
            embed_color = discord.Color.red()
            title = "📉 Top 10 Fallers (🎮 Console)"

        players = []
        seen = set()

        if section:
            cards = section.select("a.market-player-card")
            for card in cards:
                try:
                    name = card.select_one(".playercard-s-25-name").text.strip()
                    rating = card.select_one(".playercard-s-25-rating").text.strip()
                    trend_tag = card.select_one(".market-player-change")
                    price_tag = card.select_one(".platform-price-wrapper-small")

                    key = f"{name}-{rating}"
                    if key in seen:
                        continue
                    seen.add(key)

                    raw_trend = trend_tag.text.strip().replace("▲", "").replace("▼", "").replace("%", "").replace(",", "")
                    trend_val = float(raw_trend)
                    booster = boost_emoji if trend_val > boost_threshold else ""
                    trend = f"{trend_val:.2f}% {booster}".strip()

                    price = price_tag.text.strip() if price_tag else "?"

                    players.append({
                        "name": name,
                        "rating": rating,
                        "trend": trend,
                        "price": price
                    })
                except Exception:
                    continue

        top10 = players[:10]
        embed = discord.Embed(title=title, color=embed_color)
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        for i, p in enumerate(top10, start=1):
            embed.add_field(
                name=f"{i}️⃣ {p['name']} ({p['rating']})",
                value=f"💰 {p['price']}\n{emoji} {p['trend']}",
                inline=False
            )

        return embed

async def setup(bot):
    await bot.add_cog(Trending(bot))
