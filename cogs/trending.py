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

# Set up logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

CONFIG_FILE = “autotrend_config.json”

def load_config():
“”“Load configuration from JSON file with validation”””
if not os.path.exists(CONFIG_FILE):
with open(CONFIG_FILE, “w”) as f:
json.dump({}, f)
return {}

```
try:
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        # Validate config structure
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
```

def save_config(data):
“”“Save configuration to JSON file”””
try:
with open(CONFIG_FILE, “w”) as f:
json.dump(data, f, indent=2)
logger.info(“Configuration saved successfully”)
except Exception as e:
logger.error(f”Failed to save configuration: {e}”)

def is_admin_or_owner(member: discord.Member) -> bool:
“”“Check if user has admin permissions”””
if member.guild and member.id == member.guild.owner_id:
return True
allowed_roles = [“Admin”, “Owner”]
role_names = [role.name.lower() for role in member.roles]
return any(allowed.lower() in role_names for allowed in allowed_roles)

class Trending(commands.Cog):
def **init**(self, bot):
self.bot = bot
self.config = load_config()
self.session = None
self.auto_post_trends.start()

```
async def cog_load(self):
    """Initialize aiohttp session when cog loads"""
    self.session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=15),
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

async def cog_unload(self):
    """Clean up aiohttp session when cog unloads"""
    if self.session:
        await self.session.close()

async def fetch_url(self, url: str) -> str:
    """Fetch URL content with error handling"""
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
    logger.info(f"Fetching trends: {direction.value} {timeframe.value} for guild {interaction.guild.id}")
    
    embed = await self.generate_trend_embed(direction.value, timeframe.value)
    if embed:
        await interaction.followup.send(embed=embed)
        logger.info("Successfully sent trend embed")
    else:
        await interaction.followup.send("⚠️ Could not fetch trend data. Please try again later.")
        logger.warning("Failed to generate trend embed")

async def generate_trend_embed(self, direction: str, timeframe: str) -> discord.Embed:
    """Generate trending players embed with 5x2 layout"""
    tf_map = {
        "24h": "div.market-players-wrapper.market-24-hours.m-row.space-between",
        "4h": "div.market-players-wrapper.market-4-hours.m-row.space-between"
    }

    try:
        url = "https://www.futbin.com/market"
        html_content = await self.fetch_url(url)
        if not html_content:
            logger.error("Failed to fetch market page")
            return None

        soup = BeautifulSoup(html_content, "html.parser")
        container = soup.select_one(tf_map[timeframe])
        if not container:
            logger.error(f"Could not find container for timeframe {timeframe}")
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

            # Add delay between requests to be respectful
            await asyncio.sleep(0.3)
            
            # Scrape player page for PS price
            price = await self.get_ps_price(player_url)
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
            logger.warning(f"No {direction} players found for {timeframe}")
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
        
        # Create 5x2 layout by adding fields in pairs
        for i in range(0, len(players), 2):
            # Left column (positions 1, 3, 5, 7, 9)
            left_player = players[i]
            booster_left = (" 🚀" if left_player["trend"] > 100 and direction == "riser" 
                           else " ❄️" if left_player["trend"] < -50 and direction == "faller" 
                           else "")
            trend_str_left = (f"-{abs(left_player['trend']):.1f}%" if direction == "faller" 
                             else f"{left_player['trend']:.1f}%")
            
            left_content = f"💰 {left_player['price']}\n{emoji} {trend_str_left}{booster_left}"
            
            # Right column (positions 2, 4, 6, 8, 10) - if it exists
            if i + 1 < len(players):
                right_player = players[i + 1]
                booster_right = (" 🚀" if right_player["trend"] > 100 and direction == "riser" 
                                else " ❄️" if right_player["trend"] < -50 and direction == "faller" 
                                else "")
                trend_str_right = (f"-{abs(right_player['trend']):.1f}%" if direction == "faller" 
                                  else f"{right_player['trend']:.1f}%")
                
                right_content = f"💰 {right_player['price']}\n{emoji} {trend_str_right}{booster_right}"
                
                # Add both players side by side
                embed.add_field(
                    name=f"{number_emojis[i]} {left_player['name']} ({left_player['rating']})",
                    value=left_content,
                    inline=True
                )
                embed.add_field(
                    name=f"{number_emojis[i + 1]} {right_player['name']} ({right_player['rating']})",
                    value=right_content,
                    inline=True
                )
                # Add invisible field to create line break (Discord embed trick)
                embed.add_field(name="\u200b", value="\u200b", inline=True)
            else:
                # Odd number of players - add the last one alone
                embed.add_field(
                    name=f"{number_emojis[i]} {left_player['name']} ({left_player['rating']})",
                    value=left_content,
                    inline=True
                )

        logger.info(f"Generated embed with {len(players)} players")
        return embed

    except Exception as e:
        logger.error(f"Error generating trend embed: {e}")
        return None

async def get_ps_price(self, url: str) -> str:
    """Get PlayStation price for a player"""
    try:
        html_content = await self.fetch_url(url)
        if not html_content:
            return None
        
        soup = BeautifulSoup(html_content, "html.parser")
        price_tag = soup.select_one("div.price.inline-with-icon.lowest-price-1")
        if price_tag:
            price = price_tag.text.strip()
            logger.debug(f"Found price: {price} for {url}")
            return price
    except Exception as e:
        logger.error(f"Error getting PS price for {url}: {e}")
        return None
    return None

@tasks.loop(minutes=1)
async def auto_post_trends(self):
    """Auto-post trends at scheduled times"""
    now = datetime.now().strftime("%H:%M")
    
    for guild_id, settings in self.config.items():
        if settings.get("time") != now:
            continue
        
        channel = self.bot.get_channel(settings["channel_id"])
        if not channel:
            logger.warning(f"Could not find channel {settings['channel_id']} for guild {guild_id}")
            continue
        
        logger.info(f"Auto-posting trends for guild {guild_id} at {now}")
        
        try:
            for direction in ["riser", "faller"]:
                embed = await self.generate_trend_embed(direction, "24h")
                if embed:
                    await channel.send(embed=embed)
                    # Add delay between posts to avoid rate limits
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"Failed to generate {direction} embed for auto-post")
                    
        except discord.Forbidden:
            logger.error(f"No permission to send messages in channel {settings['channel_id']}")
        except discord.HTTPException as e:
            logger.error(f"Discord API error during auto-post: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during auto-post: {e}")

@auto_post_trends.before_loop
async def before_auto_post(self):
    """Wait for bot to be ready before starting auto-post loop"""
    await self.bot.wait_until_ready()
    logger.info("Auto-post trends task started")

@app_commands.command(name="setupautotrending", description="🛠️ Set daily auto-post channel and time (HH:MM 24hr)")
@app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 09:00)")
async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
    if not is_admin_or_owner(interaction.user):
        await interaction.response.send_message("❌ Only Admins/Owner can use this command.", ephemeral=True)
        return
    
    # Validate time format
    try:
        datetime.strptime(post_time, "%H:%M")
    except ValueError:
        await interaction.response.send_message("❌ Invalid time format. Use HH:MM (24h format, e.g., 09:00)", ephemeral=True)
        return

    # Check bot permissions in the channel
    bot_member = interaction.guild.get_member(self.bot.user.id)
    if not channel.permissions_for(bot_member).send_messages:
        await interaction.response.send_message("❌ I don't have permission to send messages in that channel.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    self.config[guild_id] = {
        "channel_id": channel.id,
        "time": post_time
    }
    save_config(self.config)
    
    logger.info(f"Auto-trending configured for guild {guild_id}: {post_time} in channel {channel.id}")
    await interaction.response.send_message(
        f"✅ Auto-trending set for **{post_time}** in {channel.mention}\n"
        f"📊 Daily risers and fallers will be posted automatically!"
    )

@app_commands.command(name="removeautotrending", description="🗑️ Remove auto-trending for this server")
async def removeautotrending(self, interaction: discord.Interaction):
    if not is_admin_or_owner(interaction.user):
        await interaction.response.send_message("❌ Only Admins/Owner can use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id in self.config:
        del self.config[guild_id]
        save_config(self.config)
        logger.info(f"Auto-trending removed for guild {guild_id}")
        await interaction.response.send_message("✅ Auto-trending has been disabled for this server.")
    else:
        await interaction.response.send_message("❌ Auto-trending is not currently set up for this server.")
```

async def setup(bot):
await bot.add_cog(Trending(bot))