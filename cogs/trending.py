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
        direction="Risers or Fallers",
        period="Choose 24h or 4h trend data"
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="📈 Risers", value="riser"),
        app_commands.Choice(name="📉 Fallers", value="faller")
    ], period=[
        app_commands.Choice(name="🗓️ 24h", value="day"),
        app_commands.Choice(name="🕓 4h", value="4hour")
    ])
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], period: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, period.value)
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
                embed = await self.generate_trend_embed(direction, "day")
                await channel.send(embed=embed)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    async def generate_trend_embed(self, direction: str, period: str) -> discord.Embed:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://www.futbin.com/market"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            embed = discord.Embed(title="Error", description="Unable to fetch market data.", color=discord.Color.red())
            return embed

        soup = BeautifulSoup(response.text, "html.parser")
        target_class = "market-gain" if direction == "riser" else "market-losers"
        timeframe_class = "day" if period == "day" else "four"
        wrapper = soup.find("div", class_=f"{target_class} xs-column {timeframe_class}")

        if not wrapper:
            embed = discord.Embed(title="Error", description="No trend data available.", color=discord.Color.red())
            return embed

        player_rows = wrapper.select("div.market-row")
        players = []

        for row in player_rows[:10]:
            name_tag = row.select_one(".market-row-name")
            price_tag = row.select_one(".market-row-price")
            change_tag = row.select_one(".market-player-change")

            if not name_tag or not price_tag or not change_tag:
                continue

            name = name_tag.text.strip()
            price = price_tag.text.strip().replace("\n", " ").replace("  ", " ").strip()
            trend_text = change_tag.text.strip().replace("%", "").replace(",", "")

            try:
                trend = float(trend_text)
            except ValueError:
                continue

            players.append({
                "name": name,
                "price": price,
                "trend": trend
            })

        emoji = "📈" if direction == "riser" else "📉"
        period_emoji = "🗓️" if period == "day" else "🕓"
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console) {period_emoji}"
        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left = ""
        right = ""

        for i, p in enumerate(players):
            booster = ""
            trend_val = p["trend"]
            if direction == "riser" and trend_val > 100:
                booster = " 🚀"
            elif direction == "faller" and trend_val < 50:
                booster = " ❄️"

            sign = "" if direction == "riser" else "-"

            entry = (
                f"**{number_emojis[i]} {p['name']}**\n"
                f"💰 {p['price']}\n"
                f"{emoji} {sign}{trend_val:.2f}%{booster}\n\n"
            )

            if i < 5:
                left += entry
            else:
                right += entry

        embed.add_field(name="\u200b", value=left, inline=True)
        embed.add_field(name="\u200b", value=right, inline=True)
        return embed


async def setup(bot):
    await bot.add_cog(Trending(bot))
