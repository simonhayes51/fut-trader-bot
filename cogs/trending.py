import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import asyncio
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


class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.auto_post_trends.start()

    def scrape_trending_players(self):
        url = "https://www.fut.gg/players/momentum/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        player_cards = soup.find_all("a", class_="group/player")
        risers, fallers = [], []

        for card in player_cards:
            name_tag = card.find("img")
            name = name_tag["alt"] if name_tag else "Unknown"
            rating = name.split(" - ")[1] if " - " in name else "?"
            price_tag = card.find("div", class_="flex items-center justify-center gap-[0.2em] grow shrink-0")
            price = price_tag.get_text(strip=True) if price_tag else "?"
            trend_tag = card.find("div", class_="font-bold text-xs text-green-500")
            trend = trend_tag.get_text(strip=True) if trend_tag else "?"
            position_tag = card.find("span", class_="text-[0.7em] text-black font-black leading-[1.2em]")
            position = position_tag.get_text(strip=True) if position_tag else "?"
            image_url = name_tag["src"] if name_tag else None

            player = {
                "name": name.split(" - ")[0],
                "rating": rating,
                "price": price,
                "trend": trend,
                "position": position,
                "image": image_url
            }

            if trend.startswith("-"):
                fallers.append(player)
            elif trend.startswith("+") or not trend.startswith("-"):
                risers.append(player)

            if len(risers) >= 10 and len(fallers) >= 10:
                break

        return risers[:10], fallers[:10]

    def build_embed(self, players, title, emoji, color):
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.utcnow()
        )
        if not players:
            embed.description = "No trending players found."
        else:
            for p in players:
                embed.add_field(
                    name=f"{p['name']} ({p['rating']})",
                    value=(
                        f"{emoji} `{p['trend']}`\n"
                        f"💰 `{p['price']}`\n"
                        f"🧭 {p['position']}"
                    ),
                    inline=False
                )
        return embed

    @app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM, 24h)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 09:00)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need 'Manage Server' permission to use this.", ephemeral=True)
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

    @app_commands.command(name="trending", description="📊 Show top 10 risers and fallers")
    async def trending(self, interaction: discord.Interaction):
        await interaction.response.defer()
        risers, fallers = self.scrape_trending_players()

        riser_embed = self.build_embed(risers, "📈 Top 10 Risers (🎮 Console)", "📈", discord.Color.green())
        faller_embed = self.build_embed(fallers, "📉 Top 10 Fallers (🎮 Console)", "📉", discord.Color.red())

        await interaction.followup.send(embeds=[riser_embed, faller_embed])

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue

            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue

            risers, fallers = self.scrape_trending_players()
            try:
                await channel.send(embed=self.build_embed(risers, "📈 Daily Top 10 Risers (🎮 Console)", "📈", discord.Color.green()))
                await asyncio.sleep(1)
                await channel.send(embed=self.build_embed(fallers, "📉 Daily Top 10 Fallers (🎮 Console)", "📉", discord.Color.red()))
            except Exception as e:
                print(f"Error posting to {channel.id}: {e}")

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Trending(bot))
