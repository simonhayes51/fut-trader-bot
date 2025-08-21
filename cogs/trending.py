import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import aiohttp
import json
import os
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "autotrend_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            valid_config = {}
            for guild_id, settings in config.items():
                if isinstance(settings, dict) and "channel_id" in settings and "time" in settings:
                    valid_config[guild_id] = settings
            return valid_config
    except json.JSONDecodeError:
        logger.error("Config file corrupted, creating new one")
        return {}

def save_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("✅ Configuration saved")
    except Exception as e:
        logger.error(f"❌ Failed to save config: {e}")

def is_admin_or_owner(member: discord.Member) -> bool:
    if member.guild and member.id == member.guild.owner_id:
        return True
    allowed_roles = ["Admin", "Owner"]
    return any(role.name.lower() in [r.lower() for r in allowed_roles] for role in member.roles)

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.session = None
        self.auto_post_trends.start()

    async def cog_load(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def fetch_url(self, url):
        try:
            async with self.session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as res:
                if res.status == 200:
                    return await res.text()
                logger.warning(f"⚠️ HTTP {res.status} for {url}")
        except Exception as e:
            logger.error(f"❌ Error fetching {url}: {e}")
        return None

    async def get_trend_data(self, timeframe, direction):
        url = "https://www.futbin.com/market"
        html = await self.fetch_url(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        selector = {
            "24h": "div.market-players-wrapper.market-24-hours.m-row.space-between",
            "4h": "div.market-players-wrapper.market-4-hours.m-row.space-between"
        }.get(timeframe)
        container = soup.select_one(selector)
        if not container:
            return []

        cards = container.select("a.market-player-card")
        results = []
        for card in cards:
            try:
                name = card.select_one(".playercard-s-25-name").text.strip()
                rating = card.select_one(".playercard-s-25-rating").text.strip()
                trend = card.select_one(".market-player-change").text.strip()
                href = card.get("href")
                trend_val = float(trend.replace("%", "").replace("+", "").replace(",", ""))
                if "day-change-negative" in card.select_one(".market-player-change").get("class", []):
                    trend_val = -abs(trend_val)
                if direction == "riser" and trend_val <= 0:
                    continue
                if direction == "faller" and trend_val >= 0:
                    continue
                results.append({
                    "name": name,
                    "rating": rating,
                    "trend": trend_val,
                    "link": f"https://www.futbin.com{href}?platform=ps"
                })
            except:
                continue
            if len(results) >= 20:
                break
        return results

    async def generate_trend_embed(self, direction, timeframe, smart=False):
        data = await self.get_trend_data(timeframe, direction)
        if not data:
            return None

        if smart:
            other = await self.get_trend_data("4h" if timeframe == "24h" else "24h", "riser" if direction == "faller" else "faller")
            smart_set = set((x["name"], x["rating"]) for x in other)
        else:
            smart_set = set()

        emoji = "📈" if direction == "riser" else "📉"
        title = f"{emoji} Top {len(data[:10])} {'Risers' if direction == 'riser' else 'Fallers'} (🎮 PS) – {'24h' if timeframe == '24h' else '4h'}"

        embed = discord.Embed(
            title=title,
            color=discord.Color.green() if direction == "riser" else discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="Data from FUTBIN")

        for i, player in enumerate(data[:10]):
            tag = "🔄" if (player["name"], player["rating"]) in smart_set else ""
            percent = f"{player['trend']:.2f}%"
            embed.add_field(
                name=f"{i+1}. {player['name']} ({player['rating']}) {tag}",
                value=f"{emoji} {percent} – [Link]({player['link']})",
                inline=False
            )
        return embed

    @app_commands.command(name="trending", description="📊 Show trending players")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ],
        timeframe=[
            app_commands.Choice(name="🕓 4h", value="4h"),
            app_commands.Choice(name="🗓️ 24h", value="24h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value, smart=True)
        if embed:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("⚠️ No data found.")

    class RefreshView(discord.ui.View):
        def __init__(self, cog, direction, timeframe):
            super().__init__(timeout=60)
            self.cog = cog
            self.direction = direction
            self.timeframe = timeframe

        @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
        async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            embed = await self.cog.generate_trend_embed(self.direction, self.timeframe, smart=True)
            if embed:
                await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
            else:
                await interaction.followup.send("⚠️ Could not refresh.")

    @app_commands.command(name="trendbutton", description="📊 Show trending players with refresh button")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ],
        timeframe=[
            app_commands.Choice(name="🕓 4h", value="4h"),
            app_commands.Choice(name="🗓️ 24h", value="24h")
        ]
    )
    async def trendbutton(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value, smart=True)
        if embed:
            await interaction.followup.send(embed=embed, view=self.RefreshView(self, direction.value, timeframe.value))
        else:
            await interaction.followup.send("⚠️ No data found.")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue
            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue
            ping = f"<@&{settings['role_id']}>" if "role_id" in settings else ""
            for direction in ["riser", "faller"]:
                embed = await self.generate_trend_embed(direction, "24h", smart=True)
                if embed:
                    await channel.send(content=ping, embed=embed)
                    await asyncio.sleep(2)

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setupautotrending", description="🛠️ Setup auto-posting for trending")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, time: str, frequency: int, ping_role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only admins can do that.", ephemeral=True)
            return
        try:
            datetime.strptime(time, "%H:%M")
        except:
            await interaction.response.send_message("❌ Invalid time format (HH:MM 24h).", ephemeral=True)
            return
        self.config[str(interaction.guild.id)] = {
            "channel_id": channel.id,
            "time": time,
            "frequency": frequency,
            "role_id": ping_role.id if ping_role else None
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-trending enabled for {channel.mention} at {time} every {frequency}h")

    @app_commands.command(name="removeautotrending", description="🗑️ Remove auto-posting")
    async def removeautotrending(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only admins can do that.", ephemeral=True)
            return
        if str(interaction.guild.id) in self.config:
            del self.config[str(interaction.guild.id)]
            save_config(self.config)
            await interaction.response.send_message("✅ Auto-posting disabled.")
        else:
            await interaction.response.send_message("ℹ️ No auto-posting was set up.")

async def setup(bot):
    await bot.add_cog(Trending(bot))