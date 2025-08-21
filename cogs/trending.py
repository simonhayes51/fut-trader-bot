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
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Configuration saved successfully")
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")

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
        try:
            html_content = await self.fetch_url(url)
            if not html_content:
                return None

            soup = BeautifulSoup(html_content, "html.parser")
            price_sections = soup.select("div.price-box-original-player div.player-price-info")

            for section in price_sections:
                rating_tag = section.select_one(".player-rating")
                price_tag = section.select_one("div.price.inline-with-icon.lowest-price-1")

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
