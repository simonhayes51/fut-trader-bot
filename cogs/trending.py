import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import os
import requests
from bs4 import BeautifulSoup

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
    return member.guild and (member.guild.owner_id == member.id or any(r.name.lower() in ["admin", "owner"] for r in member.roles))

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.auto_post_trends.start()

    @app_commands.command(name="trending", description="\ud83d\udcca Show top trending players")
    @app_commands.describe(
        direction="Choose trend direction",
        period="Choose timeframe"
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="\ud83d\udcc8 Risers", value="riser"),
            app_commands.Choice(name="\ud83d\udd89\ufe0f Fallers", value="faller")
        ],
        period=[
            app_commands.Choice(name="\ud83d\uddd3\ufe0f 24 Hour", value="24h"),
            app_commands.Choice(name="\ud83d\udd53 4 Hour", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], period: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_embed(direction.value, period.value)
        await interaction.followup.send(embed=embed or "Error\nUnable to fetch market data.")

    @app_commands.command(name="setupautotrending", description="\u2699\ufe0f Set up auto-post for trending players")
    @app_commands.describe(channel="Channel to post in", frequency="Frequency (6/12/24 hours)", start_time="Start time (HH:MM)", ping_role="Optional ping role")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, frequency: int, start_time: str, ping_role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("\u274c You must be an Admin or Server Owner.", ephemeral=True)
            return

        if frequency not in [6, 12, 24]:
            await interaction.response.send_message("\u274c Frequency must be 6, 12, or 24.", ephemeral=True)
            return

        try:
            datetime.strptime(start_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("\u274c Invalid time format. Use HH:MM (24h)", ephemeral=True)
            return

        self.config[str(channel.id)] = {
            "frequency": frequency,
            "start_time": start_time,
            "ping_role": ping_role.id if ping_role else None
        }
        save_config(self.config)
        await interaction.response.send_message(f"\u2705 Auto-trending set for every {frequency}h starting at {start_time} in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().replace(second=0, microsecond=0)
        print(f"[LOOP] Tick at {now.strftime('%H:%M')} UTC")

        for channel_id, settings in self.config.items():
            try:
                start = datetime.strptime(settings["start_time"], "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                while start > now:
                    start -= timedelta(hours=settings["frequency"])
                while start + timedelta(hours=settings["frequency"]) <= now:
                    start += timedelta(hours=settings["frequency"])

                if now != start:
                    continue

                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    print(f"[WARN] Channel {channel_id} not found")
                    continue

                embed = await self.generate_combined_embed("24h")
                if not embed:
                    print(f"[ERROR] Could not generate embed")
                    continue

                ping = settings.get("ping_role")
                content = f"<@&{ping}>" if ping else None
                await channel.send(content=content, embed=embed)
                print(f"[POSTED] Sent market trends to {channel.name}")

            except Exception as e:
                print(f"[ERROR] Autopost error for channel {channel_id}: {e}")

    @auto_post_trends.before_loop
    async def before_auto(self):
        print("\u23f3 Waiting for bot to be ready...")
        await self.bot.wait_until_ready()
        print("\u2705 Bot ready — starting auto loop")

    async def generate_embed(self, direction, period) -> discord.Embed:
        data = self.scrape_futbin_data(direction, period)
        if not data:
            return None

        emoji = "\ud83d\udcc8" if direction == "riser" else "\ud83d\udd89\ufe0f"
        color = discord.Color.green() if direction == "riser" else discord.Color.red()
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (\ud83c\udfae Console) – {period}"

        embed = discord.Embed(title=title, color=color)
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")
        number_emojis = ["1\ufe0f\u20e3", "2\ufe0f\u20e3", "3\ufe0f\u20e3", "4\ufe0f\u20e3", "5\ufe0f\u20e3", "6\ufe0f\u20e3", "7\ufe0f\u20e3", "8\ufe0f\u20e3", "9\ufe0f\u20e3", "\ud83d\udd1f"]

        for i, p in enumerate(data[:10]):
            boost = ""
            if direction == "riser" and p["trend"] > 100:
                boost = " \ud83d\ude80"
            elif direction == "faller" and p["trend"] < -50:
                boost = " \u2744\ufe0f"

            trend = f"-{p['trend']:.2f}%" if direction == "faller" else f"{p['trend']:.2f}%"
            embed.add_field(
                name=f"{number_emojis[i]} {p['name']} ({p['rating']})",
                value=f"