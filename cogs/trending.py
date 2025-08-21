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
    """Load configuration from JSON file with validation"""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            valid_config = {}
            for guild_id, settings in config.items():
                if (isinstance(settings, dict) and 
                    "channel_id" in settings and 
                    "time" in settings and
                    isinstance(settings["channel_id"], int) and
                    isinstance(settings["time"], str)):
                    valid_config[guild_id] = settings
                else:
                    logger.warning(f"Invalid config for guild {guild_id}, skipping")
            return valid_config
    except json.JSONDecodeError:
        logger.error("Config file corrupted, creating new one")
        return {}

def save_config(data):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Configuration saved successfully")
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")

def is_admin_or_owner(member: discord.Member) -> bool:
    """Check if user has admin permissions"""
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
            logger.info("Auto-post trends task started")

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
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def get_ps_price(self, url: str, expected_rating: str) -> str:
        """Get PS price for the correct version of the player matching expected rating"""
        try:
            html_content = await self.fetch_url(url)
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, "html.parser")
            
            price_blocks = soup.select("div.player-page-price-versions > div")
            for block in price_blocks:
                rating_tag = block.select_one(".player-rating")
                price_tag = block.select_one("div.price.inline-with-icon.lowest-price-1")
                
                if rating_tag and price_tag:
                    if rating_tag.text.strip() == expected_rating:
                        return price_tag.text.strip()
            
            fallback = soup.select_one("div.price.inline-with-icon.lowest-price-1")
            if fallback:
                return fallback.text.strip()

        except Exception as e:
            logger.error(f"Error getting PS price for {url}: {e}")
            return None

        return None

    @app_commands.command(name="trending", description="📊 Show top trending players (Risers/Fallers)")
    @app_commands.describe(direction="Risers or Fallers", timeframe="4h or 24h timeframe")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ],
        timeframe=[
            app_commands.Choice(name="🗓️ 24 Hours", value="24h"),
            app_commands.Choice(name="🕓 4 Hours", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], timeframe: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_trend_embed(direction.value, timeframe.value)
        if embed:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("⚠️ Could not fetch trend data. Please try again later.")

    async def generate_trend_embed(self, direction: str, timeframe: str) -> discord.Embed:
        tf_map = {
            "24h": "div.market-players-wrapper.market-24-hours.m-row.space-between",
            "4h": "div.market-players-wrapper.market-4-hours.m-row.space-between"
        }

        try:
            url = "https://www.futbin.com/market"
            html_content = await self.fetch_url(url)
            if not html_content:
                return None

            soup = BeautifulSoup(html_content, "html.parser")
            container = soup.select_one(tf_map[timeframe])
            if not container:
                return None

            cards = container.select("a.market-player-card")
            players = []

            for card in cards:
                trend_tag = card.select_one(".market-player-change")
                if not trend_tag or "%" not in trend_tag.text:
                    continue

                try:
                    trend_text = trend_tag.text.strip().replace("%", "").replace("+", "").replace(",", "")
                    trend = float(trend_text)
                    if "day-change-negative" in trend_tag.get("class", []):
                        trend = -abs(trend)
                except (ValueError, AttributeError):
                    continue

                if direction == "riser" and trend <= 0:
                    continue
                if direction == "faller" and trend >= 0:
                    continue

                name_tag = card.select_one(".playercard-s-25-name")
                rating_tag = card.select_one(".playercard-s-25-rating")
                link = card.get("href")

                if not name_tag or not rating_tag or not link:
                    continue

                name = name_tag.text.strip()
                rating = rating_tag.text.strip()
                player_url = f"https://www.futbin.com{link}?platform=ps"

                await asyncio.sleep(0.3)
                price = await self.get_ps_price(player_url, rating)
                if not price:
                    continue

                players.append({
                    "name": name,
                    "rating": rating,
                    "trend": trend,
                    "price": price
                })

                if len(players) >= 10:
                    break

            if not players:
                return None

            emoji = "📈" if direction == "riser" else "📉"
            timeframe_emoji = "🗓️" if timeframe == "24h" else "🕓"
            title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 PS) – {timeframe_emoji} {timeframe}"

            embed = discord.Embed(
                title=title,
                color=discord.Color.green() if direction == "riser" else discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.set_footer(text="Data from FUTBIN | PS prices only")

            number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for i in range(0, len(players), 2):
                left = players[i]
                trend_str = f"-{abs(left['trend']):.1f}%" if direction == "faller" else f"{left['trend']:.1f}%"
                left_value = f"💰 {left['price']}\n{emoji} {trend_str}"

                if i + 1 < len(players):
                    right = players[i + 1]
                    trend_str_r = f"-{abs(right['trend']):.1f}%" if direction == "faller" else f"{right['trend']:.1f}%"
                    right_value = f"💰 {right['price']}\n{emoji} {trend_str_r}"

                    embed.add_field(name=f"{number_emojis[i]} {left['name']} ({left['rating']})", value=left_value, inline=True)
                    embed.add_field(name=f"{number_emojis[i+1]} {right['name']} ({right['rating']})", value=right_value, inline=True)
                    embed.add_field(name="\u200b", value="\u200b", inline=True)
                else:
                    embed.add_field(name=f"{number_emojis[i]} {left['name']} ({left['rating']})", value=left_value, inline=True)

            return embed

        except Exception as e:
            logger.error(f"Trend embed error: {e}")
            return None

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.now().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue

            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue

            try:
                for direction in ["riser", "faller"]:
                    embed = await self.generate_trend_embed(direction, "24h")
                    if embed:
                        await channel.send(embed=embed)
                        await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Auto-post error: {e}")

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM 24hr)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owner can use this command.", ephemeral=True)
            return

        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format.", ephemeral=True)
            return

        bot_member = interaction.guild.get_member(self.bot.user.id)
        if not channel.permissions_for(bot_member).send_messages:
            await interaction.response.send_message("❌ Missing send permissions in that channel.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-trending set for **{post_time}** in {channel.mention}")

    @app_commands.command(name="removeautotrending", description="🗑️ Remove auto-trending for this server")
    async def removeautotrending(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owner can use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        if guild_id in self.config:
            del self.config[guild_id]
            save_config(self.config)
            await interaction.response.send_message("✅ Auto-trending disabled.")
        else:
            await interaction.response.send_message("❌ Auto-trending wasn't enabled.")

    @app_commands.command(name="debugautopost", description="🔍 Debug auto-posting (Admin only)")
    async def debugautopost(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owner can use this command.", ephemeral=True)
            return

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        debug_info = []
        debug_info.append(f"**Current Time:** {current_time}")
        debug_info.append(f"**Task Running:** {'✅ Yes' if self.auto_post_trends.is_running() else '❌ No'}")
        debug_info.append(f"**Config Entries:** {len(self.config)}")

        guild_id = str(interaction.guild.id)
        if guild_id in self.config:
            settings = self.config[guild_id]
            debug_info.append("**This Guild Config:**")
            debug_info.append(f"  - Channel ID: {settings['channel_id']}")
            debug_info.append(f"  - Scheduled Time: {settings['time']}")
            debug_info.append(f"  - Time Match: {'✅ Yes' if settings['time'] == current_time else '❌ No'}")

            channel = self.bot.get_channel(settings["channel_id"])
            debug_info.append(f"  - Channel Found: {'✅ Yes' if channel else '❌ No'}")
            if channel:
                bot_member = interaction.guild.get_member(self.bot.user.id)
                can_send = channel.permissions_for(bot_member).send_messages
                debug_info.append(f"  - Can Send Messages: {'✅ Yes' if can_send else '❌ No'}")
        else:
            debug_info.append("**This Guild:** No auto-post configured")

        debug_info.append("\n**All Configured Guilds:**")
        for gid, settings in self.config.items():
            debug_info.append(f"Guild {gid}: {settings['time']} → Channel {settings['channel_id']}")

        await interaction.response.send_message("\n".join(debug_info))

    @app_commands.command(name="testautopost", description="🧪 Test auto-post now (Admin only)")
    async def testautopost(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owner can use this command.", ephemeral=True)
            return

        await interaction.response.defer()
        guild_id = str(interaction.guild.id)
        if guild_id not in self.config:
            await interaction.followup.send("❌ Auto-posting not configured for this server.")
            return

        settings = self.config[guild_id]
        channel = self.bot.get_channel(settings["channel_id"])
        if not channel:
            await interaction.followup.send(f"❌ Could not find channel with ID {settings['channel_id']}")
            return

        try:
            await interaction.followup.send("🧪 Testing auto-post... This may take a moment.")
            for direction in ["riser", "faller"]:
                embed = await self.generate_trend_embed(direction, "24h")
                if embed:
                    await channel.send(f"🧪 **TEST POST** - {direction.title()}s", embed=embed)
                    await asyncio.sleep(2)
                else:
                    await interaction.followup.send(f"❌ Failed to generate {direction} embed")
                    return
            await interaction.followup.send("✅ Test auto-post completed successfully!")
        except Exception as e:
            await interaction.followup.send(f"❌ Error during test: {str(e)}")
            logger.error(f"Test auto-post error: {e}")

async def setup(bot):
    await bot.add_cog(Trending(bot))