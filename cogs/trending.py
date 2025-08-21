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
    @app_commands.describe(direction="Risers or Fallers", timeframe="4h or 24h timeframe")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ],
        timeframe=[
            app_commands.Choice(name="🗓️ 24 Hours", value="24h"),
            app_commands.Choice(name="🕓 4 Hours", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value)
        if embed:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("⚠️ Could not fetch trend data.")

    async def generate_trend_embed(self, direction: str, timeframe: str) -> discord.Embed:
        tf_map = {
            "24h": "div.market-players-wrapper.market-24-hours.m-row.space-between",
            "4h": "div.market-players-wrapper.market-4-hours.m-row.space-between"
        }

        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        container = soup.select_one(tf_map[timeframe])
        if not container:
            return None

        cards = container.select("a.market-player-card")
        players = []

        for card in cards:
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue
            try:
                trend_text = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
                trend = float(trend_text)
                if "day-change-negative" in trend_tag.get("class", []):
                    trend = -abs(trend)
            except:
                continue

            if direction == "riser" and trend <= 0:
                continue
            if direction == "faller" and trend >= 0:
                continue

            name_tag = card.select_one(".playercard-s-25-name")
            rating_tag = card.select_one(".playercard-s-25-rating")
            link = card.get("href")

            if not name_tag or not rating_tag or not link:
                continue

            name = name_tag.text.strip()
            rating = rating_tag.text.strip()
            player_url = f"https://www.futbin.com{link}?platform=ps"

            # Scrape player page for PS price
            price = self.get_ps_price(player_url)
            if not price:
                continue

            players.append({
                "name": name,
                "rating": rating,
                "trend": trend,
                "price": price
            })

            if len(players) >= 10:
                break

        if not players:
            return None

        emoji = "📈" if direction == "riser" else "📉"
        timeframe_emoji = "🗓️" if timeframe == "24h" else "🕓"
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 PS) – {timeframe_emoji} {timeframe}"

        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())
        embed.set_footer(text="Data from FUTBIN | PS prices only")

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, p in enumerate(players):
            booster = " 🚀" if p["trend"] > 100 and direction == "riser" else " ❄️" if p["trend"] < -50 and direction == "faller" else ""
            trend_str = f"-{abs(p['trend']):.2f}%" if direction == "faller" else f"{p['trend']:.2f}%"
            embed.add_field(
                name=f"{number_emojis[i]} {p['name']} ({p['rating']})",
                value=f"💰 {p['price']}\n{emoji} {trend_str}{booster}",
                inline=False
            )

        return embed

    def get_ps_price(self, url: str):
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.text, "html.parser")
            price_tag = soup.select_one("div.price.inline-with-icon.lowest-price-1")
            if price_tag:
                return price_tag.text.strip()
        except:
            return None
        return None

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue
            channel = self.bot.get_channel(settings["channel_id"])
            if channel:
                for direction in ["riser", "faller"]:
                    embed = await self.generate_trend_embed(direction, "24h")
                    if embed:
                        await channel.send(embed=embed)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM 24hr)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 09:00)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owner can use this command.", ephemeral=True)
            return
        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use HH:MM (24h)", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-trending set for **{post_time}** in {channel.mention}")

async def setup(bot):
    await bot.add_cog(Trending(bot))