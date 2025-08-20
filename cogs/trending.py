import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
from datetime import datetime
import json
import os

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
            await interaction.response.send_message("❌ Only Admins or Owners can use this.", ephemeral=True)
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
        await interaction.response.send_message(f"✅ Auto-trending set for **{post_time}** in {channel.mention}")

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
        url = "https://www.futbin.com/24/playersData?sortby=updated_at&sort=desc"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        data = response.json()

        is_riser = direction == "riser"
        filtered = [p for p in data if (p.get("prp", 0) > 0 if is_riser else p.get("prp", 0) < 0)]
        top10 = sorted(filtered, key=lambda x: x["prp"], reverse=is_riser)[:10]

        emoji = "📈" if is_riser else "📉"
        color = discord.Color.green() if is_riser else discord.Color.red()
        title = f"{emoji} Top 10 {'Risers' if is_riser else 'Fallers'} (🎮 Console)"
        embed = discord.Embed(title=title, color=color)

        # Set thumbnail image of the top player
        if top10 and top10[0].get("image"):
            embed.set_thumbnail(url=top10[0]["image"])

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left_column, right_column = "", ""

        for i, p in enumerate(top10):
            name = p.get("name", "Unknown")
            rating = p.get("rating", "?")
            price = p.get("ps_price", "?")
            trend = p.get("prp", 0.0)
            booster = ""
            if is_riser and trend > 100:
                booster = " 🚀"
            elif not is_riser and trend < -50:
                booster = " ❄️"

            entry = (
                f"**{number_emojis[i]} {name} ({rating})**\n"
                f"💰 {price}\n"
                f"{emoji} {trend:.2f}%{booster}\n\n"
            )
            if i < 5:
                left_column += entry
            else:
                right_column += entry

        embed.add_field(name="\u200b", value=left_column.strip(), inline=True)
        embed.add_field(name="\u200b", value=right_column.strip(), inline=True)

        return embed


async def setup(bot):
    await bot.add_cog(Trending(bot))
