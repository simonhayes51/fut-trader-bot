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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.9"
        }

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        table_id = "top_movers_up" if direction == "riser" else "top_movers_down"
        rows = soup.select(f"#{table_id} tbody tr")

        emoji = "📈" if direction == "riser" else "📉"
        color = discord.Color.green() if direction == "riser" else discord.Color.red()
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console)"
        embed = discord.Embed(title=title, color=color)

        top10 = []
        for row in rows[:10]:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue

            name = cols[0].get_text(strip=True)
            rating = cols[1].get_text(strip=True)
            version = cols[2].get_text(strip=True)
            price = cols[3].get_text(strip=True)
            change = cols[4].get_text(strip=True).replace('%', '')
            img_tag = cols[0].find("img")
            image_url = img_tag["data-src"] if img_tag and "data-src" in img_tag.attrs else None

            try:
                trend = float(change.replace("+", "").replace("−", "-"))
            except:
                trend = 0.0

            top10.append({
                "name": name,
                "rating": rating,
                "version": version,
                "price": price,
                "trend": trend,
                "image": image_url
            })

        if top10 and top10[0]["image"]:
            embed.set_thumbnail(url=top10[0]["image"])

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left_column, right_column = "", ""

        for i, p in enumerate(top10):
            booster = ""
            if direction == "riser" and p["trend"] > 100:
                booster = " 🚀"
            elif direction == "faller" and p["trend"] < -50:
                booster = " ❄️"

            entry = (
                f"**{number_emojis[i]} {p['name']} ({p['rating']})**\n"
                f"{p['version']}\n"
                f"💰 {p['price']}\n"
                f"{emoji} {p['trend']:.2f}%{booster}\n\n"
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
