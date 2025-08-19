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
        max_page = 76
        pages = range(max_page, 0, -1) if direction == "riser" else range(1, max_page + 1)
        all_players = []

        for page in pages:
            url = f"https://www.fut.gg/players/momentum/?page={page}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")

            player_blocks = soup.select("a[href^='/players/'][class*='group/player']")
            for block in player_blocks:
                name_tag = block.find("img", alt=True)
                if not name_tag:
                    continue
                alt = name_tag["alt"].strip()
                split_alt = alt.split(" - ")
                if len(split_alt) != 3:
                    continue
                name, rating, card_type = split_alt

                trend_tag = block.select_one("div.text-green-500, div.text-red-500")
                if not trend_tag:
                    continue
                trend_text = trend_tag.text.strip().replace('%', '').replace('+', '').replace('−', '-')
                try:
                    trend = float(trend_text)
                except ValueError:
                    continue

                price = "?"
                coin_tag = block.find("img", alt="Coin")
                if coin_tag:
                    price_div = coin_tag.find_parent("div")
                    if price_div:
                        price = price_div.get_text(strip=True).replace("Coin", "").strip()

                all_players.append({
                    "name": name,
                    "rating": rating,
                    "card_type": card_type,
                    "price": price,
                    "trend": trend
                })

        all_players = sorted(all_players, key=lambda x: x["trend"], reverse=(direction == "riser"))
        top10 = all_players[:10]

        emoji = "📈" if direction == "riser" else "📉"
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console)"
        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())

        if not top10:
            embed.description = "No trending players found."
        else:
            for p in top10:
                embed.add_field(
                    name=f"{p['name']} ({p['rating']})",
                    value=f"{p['card_type']}\n💰 {p['price']}\n{emoji} {p['trend']}%",
                    inline=False
                )

        return embed

async def setup(bot):
    await bot.add_cog(Trending(bot))
