import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import requests
import json
import os
from datetime import datetime, timedelta

CONFIG_FILE = "autotrend_config.json"

DEFAULT_FREQ = 6  # hours
DEFAULT_TIME = "09:00"


# --- Config Helpers ---
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
    return any(role.name.lower() in [r.lower() for r in allowed_roles] for role in member.roles)


class AutoTrend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.trend_autopost.start()

    @app_commands.command(name="setupautotrending", description="🛠️ Configure auto-trend posting")
    @app_commands.describe(channel="Channel to post in", post_time="Start time (HH:MM 24hr)", frequency="Repeat every X hours", ping="Optional role or user to ping")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str, frequency: int = DEFAULT_FREQ, ping: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can configure this.", ephemeral=True)
            return

        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use HH:MM (24hr)", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time,
            "frequency": frequency,
            "ping_id": ping.id if ping else None,
            "last_post": None
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-trend will post every **{frequency}h** starting from **{post_time}** in {channel.mention}{f' with {ping.mention}' if ping else ''}")

    @tasks.loop(minutes=1)
    async def trend_autopost(self):
        now = datetime.now()
        for gid, cfg in self.config.items():
            channel = self.bot.get_channel(cfg.get("channel_id"))
            if not channel:
                continue

            start_time = datetime.strptime(cfg["time"], "%H:%M").replace(year=now.year, month=now.month, day=now.day)
            if now < start_time:
                continue

            freq = int(cfg.get("frequency", DEFAULT_FREQ))
            last_post = datetime.strptime(cfg["last_post"], "%Y-%m-%d %H:%M") if cfg.get("last_post") else None

            if not last_post or now >= last_post + timedelta(hours=freq):
                embed = await self.generate_combined_embed()
                ping = f"<@&{cfg['ping_id']}>" if cfg.get("ping_id") else None
                await channel.send(content=ping if ping else None, embed=embed)
                cfg["last_post"] = now.strftime("%Y-%m-%d %H:%M")
                save_config(self.config)

    @trend_autopost.before_loop
    async def before_autopost(self):
        await self.bot.wait_until_ready()

    async def generate_combined_embed(self) -> discord.Embed:
        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        players = {
            "riser": [],
            "faller": []
        }

        for section, selector in [("riser", "div.market-gain.xs-column.active"), ("faller", "div.market-losers.xs-column")]:
            blocks = soup.select(f"{selector} a.market-player-card")
            for card in blocks:
                name = card.select_one(".playercard-s-25-name").text.strip()
                rating = card.select_one(".playercard-s-25-rating").text.strip()
                price_tag = card.select_one(".platform-price-wrapper-small")
                price = price_tag.text.strip() if price_tag else "?"
                trend_tag = card.select_one(".market-player-change")
                if not trend_tag or "%" not in trend_tag.text:
                    continue
                trend_text = trend_tag.text.strip().replace("%", "").replace(",", "")
                try:
                    trend_val = float(trend_text)
                except ValueError:
                    continue

                players[section].append({
                    "name": name,
                    "rating": rating,
                    "price": price,
                    "trend": trend_val
                })

        # sort and trim
        players["riser"] = sorted(players["riser"], key=lambda x: x["trend"], reverse=True)[:10]
        players["faller"] = sorted(players["faller"], key=lambda x: x["trend"])[:10]

        # format embed
        embed = discord.Embed(
            title=f"📊 Top 10 Risers & Fallers (🎮 Console)",
            color=discord.Color.blurple(),
            description="Data from FUTBIN | Prices are estimates"
        )

        emoji_nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        def format_list(entries, section):
            output = ""
            symbol = "📈" if section == "riser" else "📉"
            for i, p in enumerate(entries):
                trend = f"{p['trend']:.2f}%"
                if section == "faller":
                    trend = f"-{trend}"
                booster = " 🚀" if section == "riser" and p['trend'] > 100 else " ❄️" if section == "faller" and p['trend'] < -50 else ""
                output += f"{emoji_nums[i]} {p['name']} ({p['rating']})\n💰 {p['price']}\n{symbol} {trend}{booster}\n\n"
            return output

        embed.add_field(name="📈 Risers", value=format_list(players["riser"], "riser"), inline=True)
        embed.add_field(name="📉 Fallers", value=format_list(players["faller"], "faller"), inline=True)
        return embed


async def setup(bot):
    await bot.add_cog(AutoTrend(bot))
