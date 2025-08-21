import discord
from discord.ext import commands, tasks
from discord import app_commands
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import json
import os
import logging
from datetime import datetime, timedelta

CONFIG_FILE = "autotrend_config.json"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.info(f"Loaded config: {self.config}")
        self.session = None
        if not self.auto_post_trends.is_running():
            self.auto_post_trends.start()

    async def cog_load(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Mozilla/5.0"}
        )

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def fetch_url(self, url: str) -> str:
        if not self.session:
            await self.cog_load()
        try:
            async with self.session.get(url) as response:
                return await response.text() if response.status == 200 else None
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return None

    async def get_ps_price(self, url: str, expected_rating: str) -> str:
        try:
            html = await self.fetch_url(url)
            if not html:
                return None
            soup = BeautifulSoup(html, "html.parser")
            blocks = soup.select("div.player-page-price-versions > div")
            for b in blocks:
                rating = b.select_one(".player-rating")
                price = b.select_one("div.price.inline-with-icon.lowest-price-1")
                if rating and price and rating.text.strip() == expected_rating:
                    return price.text.strip()
            fallback = soup.select_one("div.price.inline-with-icon.lowest-price-1")
            return fallback.text.strip() if fallback else None
        except Exception as e:
            logger.error(f"Price error: {e}")
            return None

    async def fetch_trending_data(self, timeframe):
        tf_map = {
            "24h": "div.market-players-wrapper.market-24-hours.m-row.space-between",
            "4h": "div.market-players-wrapper.market-4-hours.m-row.space-between"
        }
        url = "https://www.futbin.com/market"
        html = await self.fetch_url(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(tf_map[timeframe])
        cards = container.select("a.market-player-card") if container else []

        players = []
        for card in cards:
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue
            trend_text = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
            try:
                trend = float(trend_text)
                if "day-change-negative" in trend_tag.get("class", []):
                    trend = -abs(trend)
            except:
                continue
            name = card.select_one(".playercard-s-25-name")
            rating = card.select_one(".playercard-s-25-rating")
            link = card.get("href")
            if not name or not rating or not link:
                continue
            players.append({
                "name": name.text.strip(),
                "rating": rating.text.strip(),
                "trend": trend,
                "url": f"https://www.futbin.com{link}?platform=ps"
            })
        return players

    async def generate_trend_embed(self, direction, timeframe):
        raw = await self.fetch_trending_data(timeframe)
        emoji = "📈" if direction == "riser" else "📉"
        tf_emoji = "🗓️" if timeframe == "24h" else "🕓"

        if direction == "smart":
            short = await self.fetch_trending_data("4h")
            long = await self.fetch_trending_data("24h")
            map_4h = {(p["name"], p["rating"]): p["trend"] for p in short}
            smart = []
            for p in long:
                key = (p["name"], p["rating"])
                if key in map_4h and ((map_4h[key] > 0 > p["trend"]) or (map_4h[key] < 0 < p["trend"])):
                    p["trend"] = f"🔁 4h: {map_4h[key]:.1f}%, 24h: {p['trend']:.1f}%"
                    smart.append(p)
            raw = smart[:10]
            title = "🧠 Smart Movers – Trend flipped from 4h to 24h"
        else:
            raw = [p for p in raw if (p["trend"] > 0 if direction == "riser" else p["trend"] < 0)][:10]
            title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 PS) – {tf_emoji} {timeframe}"

        if not raw:
            return None

        embed = discord.Embed(title=title, color=discord.Color.green() if direction == "riser" else discord.Color.red())
        embed.set_footer(text="Data from FUTBIN")
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for idx, p in enumerate(raw):
            price = await self.get_ps_price(p["url"], p["rating"]) if direction != "smart" else "N/A"
            trend = p["trend"] if isinstance(p["trend"], str) else f"{p['trend']:+.1f}%"
            embed.add_field(
                name=f"{number_emojis[idx]} {p['name']} ({p['rating']})",
                value=f"💰 {price}\n{emoji} {trend}",
                inline=True
            )
        return embed
        
    @app_commands.command(name="trending", description="📊 Show trending players")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller"),
            app_commands.Choice(name="🧠 Smart Movers", value="smart")
        ],
        timeframe=[
            app_commands.Choice(name="🗓️ 24 Hours", value="24h"),
            app_commands.Choice(name="🕓 4 Hours", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str] = None):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value if timeframe else "24h")
        if embed:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("⚠️ Could not generate embed.")

    @app_commands.command(name="trendbutton", description="📊 Trending with refresh button")
    async def trendbutton(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = await self.generate_trend_embed("riser", "24h")
        if not embed:
            await interaction.followup.send("⚠️ Could not fetch data.")
            return

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="🔁 Refresh", style=discord.ButtonStyle.primary, custom_id="refresh_trending"))
        await interaction.followup.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "refresh_trending":
            await interaction.response.defer()
            embed = await self.generate_trend_embed("riser", "24h")
            if embed:
                await interaction.edit_original_response(embed=embed)
            else:
                await interaction.followup.send("⚠️ Refresh failed.")

    @app_commands.command(name="setupautotrending", description="🛠️ Configure auto-posting")
    @app_commands.describe(channel="Channel to post in", post_time="Time (HH:MM)", frequency="Post every X hours", ping_role="Optional role to ping")
    @app_commands.choices(
        frequency=[
            app_commands.Choice(name="Every 6 hours", value="6"),
            app_commands.Choice(name="Every 12 hours", value="12"),
            app_commands.Choice(name="Every 24 hours", value="24")
        ]
    )
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str, frequency: app_commands.Choice[str], ping_role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            datetime.strptime(post_time, "%H:%M")
        except:
            await interaction.response.send_message("⛔ Invalid time format (HH:MM)", ephemeral=True)
            return
        bot_member = interaction.guild.get_member(self.bot.user.id)
        if not channel.permissions_for(bot_member).send_messages:
            await interaction.response.send_message("⛔ I can’t send messages in that channel.", ephemeral=True)
            return
        self.config[str(interaction.guild.id)] = {
            "channel_id": channel.id,
            "time": post_time,
            "frequency": frequency.value,
            "role_id": ping_role.id if ping_role else None
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-posting set every {frequency.value}h at **{post_time}** in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for gid, settings in self.config.items():
            if settings["time"] != now:
                continue
            if str(datetime.now().hour % int(settings["frequency"])) != "0":
                continue
            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue
            role_mention = f"<@&{settings['role_id']}>" if "role_id" in settings else None
            for direction in ["riser", "faller"]:
                embed = await self.generate_trend_embed(direction, "24h")
                if embed:
                    await channel.send(content=role_mention if role_mention else None, embed=embed)
                    await asyncio.sleep(2)

    @auto_post_trends.before_loop
    async def before_autopost(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="debugautopost", description="🔍 Debug autopost")
    async def debugautopost(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        now = datetime.now().strftime("%H:%M")
        info = [f"🕒 Current time: **{now}**", f"Task running: {'✅' if self.auto_post_trends.is_running() else '❌'}"]
        if gid in self.config:
            c = self.config[gid]
            info.append(f"Config: Channel <#{c['channel_id']}>, Time {c['time']}, Freq {c['frequency']}h")
        else:
            info.append("No auto-post config found.")
        await interaction.response.send_message("\n".join(info), ephemeral=True)

    @app_commands.command(name="testautopost", description="🧪 Force auto-post now")
    async def testautopost(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gid = str(interaction.guild.id)
        if gid not in self.config:
            await interaction.followup.send("⛔ Not configured.")
            return
        c = self.config[gid]
        ch = self.bot.get_channel(c["channel_id"])
        role = f"<@&{c['role_id']}>" if "role_id" in c else None
        for d in ["riser", "faller"]:
            embed = await self.generate_trend_embed(d, "24h")
            if embed:
                await ch.send(content=role if role else None, embed=embed)
                await asyncio.sleep(2)
        await interaction.followup.send("✅ Test post done.")

async def setup(bot):
    await bot.add_cog(Trending(bot))