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

    @app_commands.command(name="trending", description="\ud83d\udcca Show top trending players (Risers/Fallers)")
    @app_commands.describe(direction="Risers or Fallers", timeframe="4h or 24h timeframe")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="\ud83d\udcc8 Risers", value="riser"),
            app_commands.Choice(name="\ud83d\udcc9 Fallers", value="faller")
        ],
        timeframe=[
            app_commands.Choice(name="\ud83d\uddd3\ufe0f 24 Hours", value="24h"),
            app_commands.Choice(name="\ud83d\udd93 4 Hours", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str] = None):
        await interaction.response.defer()
        trend_embed = await self.generate_trend_embed(direction.value, timeframe.value if timeframe else "24h")
        if trend_embed:
            await interaction.followup.send(embed=trend_embed)
        else:
            await interaction.followup.send("\u26a0\ufe0f No trend data found.")

    @app_commands.command(name="setupautotrending", description="\ud83d\udee0\ufe0f Set daily auto-post channel and time (HH:MM 24hr)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 09:00)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("\u274c Only Admins/Owner can use this command.", ephemeral=True)
            return
        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("\u274c Invalid time format. Use HH:MM (24h)", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time
        }
        save_config(self.config)
        await interaction.response.send_message(f"\u2705 Auto-trending set for **{post_time}** in {channel.mention}")

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
                if embed:
                    await channel.send(embed=embed)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    async def generate_trend_embed(self, direction: str, timeframe: str) -> discord.Embed:
        tf_map = {
            "24h": {
                "container": "div.market-players-wrapper.market-24-hours.m-row.space-between",
                "emoji": "\ud83d\uddd3\ufe0f"
            },
            "4h": {
                "container": "div.market-players-wrapper.market-4-hours.m-row.space-between",
                "emoji": "\ud83d\udd93"
            }
        }

        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        container = soup.select_one(tf_map[timeframe]["container"])
        if not container:
            return None

        cards = container.select("a.market-player-card")
        all_players = []

        for card in cards:
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue

            trend_text = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
            try:
                trend = float(trend_text)
            except ValueError:
                continue

            if "day-change-negative" in trend_tag.get("class", []):
                trend = -abs(trend)
            else:
                trend = abs(trend)

            if direction == "riser" and trend <= 0:
                continue
            if direction == "faller" and trend >= 0:
                continue

            name_tag = card.select_one(".playercard-s-25-name")
            rating_tag = card.select_one(".playercard-s-25-rating")
            price_tag = card.select_one(".platform-price-wrapper-small .ps")  # PS price

            if not (name_tag and rating_tag and price_tag):
                continue

            all_players.append({
                "name": name_tag.text.strip(),
                "rating": rating_tag.text.strip(),
                "trend": trend,
                "price": price_tag.text.strip()
            })

        sorted_players = sorted(all_players, key=lambda x: x["trend"], reverse=(direction == "riser"))
        top10 = sorted_players[:10]

        if not top10:
            return None

        emoji = "\ud83d\udcc8" if direction == "riser" else "\ud83d\udcc9"
        time_emoji = tf_map[timeframe]["emoji"]
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (\ud83c\udfae Console) \u2013 {time_emoji} {timeframe}"

        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        number_emojis = ["1\ufe0f\u20e3", "2\ufe0f\u20e3", "3\ufe0f\u20e3", "4\ufe0f\u20e3", "5\ufe0f\u20e3", "6\ufe0f\u20e3", "7\ufe0f\u20e3", "8\ufe0f\u20e3", "9\ufe0f\u20e3", "\ud83d\udd1f"]
        left = ""
        right = ""

        for i, p in enumerate(top10):
            booster = ""
            if direction == "riser" and p["trend"] > 100:
                booster = " \ud83d\ude80"
            elif direction == "faller" and p["trend"] < -50:
                booster = " \u2744\ufe0f"

            trend_display = f"{p['trend']:.2f}%{booster}" if direction == "riser" else f"-{abs(p['trend']):.2f}%{booster}"
            entry = (
                f"**{number_emojis[i]} {p['name']} ({p['rating']})**\n"
                f"\ud83d\udcb0 {p['price']}\n"
                f"{emoji} {trend_display}\n\n"
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