# utils/api_client.py - Utility functions for bot-API communication

import aiohttp
import asyncio
import logging
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class APIClient:
    """Client for communicating with the FastAPI backend"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={
                "User-Agent": "FUT-Discord-Bot/1.0",
                "Accept": "application/json"
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_trending(self, trend_type: str, timeframe: str = "24", limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch trending data from the API"""
        try:
            url = f"{self.base_url}/api/trending"
            params = {
                "type": trend_type,
                "tf": timeframe.replace("h", ""),
                "limit": limit
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("items", [])
                else:
                    logger.error(f"API trending request failed: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching trending data: {e}")
            return []

    async def get_price_history(self, player_id: int, platform: str = "ps", timeframe: str = "today") -> List[Dict]:
        """Fetch price history from the API"""
        try:
            url = f"{self.base_url}/api/price-history"
            params = {
                "playerId": player_id,
                "platform": platform,
                "tf": timeframe
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API price history request failed: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching price history: {e}")
            return []

    async def search_players(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search players using the API"""
        try:
            url = f"{self.base_url}/api/search-players"
            params = {
                "q": query,
                "limit": limit
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("players", [])
                else:
                    logger.error(f"API player search request failed: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error searching players: {e}")
            return []

    async def get_player_price(self, card_id: int, platform: str = "ps") -> Dict[str, Any]:
        """Get current player price from the API"""
        try:
            url = f"{self.base_url}/api/fut-player-price/{card_id}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    current_price = data.get("data", {}).get("currentPrice", {})
                    
                    # Handle platform-specific pricing
                    platform_map = {"ps": "ps", "xbox": "xbox", "pc": "pc", "console": "ps"}
                    platform_key = platform_map.get(platform.lower(), "ps")
                    
                    if platform_key in current_price:
                        price_data = current_price[platform_key]
                    else:
                        price_data = current_price
                    
                    return {
                        "price": price_data.get("price"),
                        "isExtinct": price_data.get("isExtinct", False),
                        "updatedAt": price_data.get("priceUpdatedAt") or current_price.get("priceUpdatedAt")
                    }
                else:
                    logger.error(f"API price request failed: {response.status}")
                    return {"price": None, "isExtinct": False, "updatedAt": None}
                    
        except Exception as e:
            logger.error(f"Error fetching player price: {e}")
            return {"price": None, "isExtinct": False, "updatedAt": None}


# Utility functions for data formatting
def format_price(price: Optional[int]) -> str:
    """Format price for Discord display"""
    if price is None:
        return "N/A"
    return f"{price:,}"

def format_percentage(percent: Optional[float], signed: bool = True) -> str:
    """Format percentage for Discord display"""
    if percent is None:
        return "N/A"
    
    sign = "+" if signed and percent > 0 else ""
    return f"{sign}{percent:.1f}%"

def get_trend_emoji(percent: Optional[float]) -> str:
    """Get appropriate emoji for trend direction"""
    if percent is None:
        return "➡️"
    elif percent > 0:
        return "📈"
    elif percent < 0:
        return "📉"
    else:
        return "➡️"

def normalize_platform(platform: str) -> str:
    """Normalize platform input"""
    platform = platform.lower().strip()
    if platform in ["ps", "playstation", "console"]:
        return "ps"
    elif platform in ["xbox", "xb"]:
        return "xbox"
    elif platform in ["pc", "origin"]:
        return "pc"
    else:
        return "ps"  # default

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text for Discord embeds"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

# Rate limiting decorator
def rate_limit(calls: int, period: int):
    """Simple rate limiting decorator"""
    call_times = []
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            nonlocal call_times
            now = asyncio.get_event_loop().time()
            
            # Remove old calls outside the period
            call_times = [t for t in call_times if now - t < period]
            
            if len(call_times) >= calls:
                sleep_time = period - (now - call_times[0])
                await asyncio.sleep(sleep_time)
                call_times = call_times[1:]
            
            call_times.append(now)
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

# Database utilities
async def ensure_user_exists(pool, user_id: str, username: str = None):
    """Ensure user exists in database"""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_profiles (user_id, username, created_at, updated_at)
                VALUES ($1, $2, NOW(), NOW())
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id, username
            )
    except Exception as e:
        logger.error(f"Error ensuring user exists: {e}")

async def log_command_usage(pool, user_id: str, command: str, guild_id: str = None):
    """Log command usage for analytics"""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO command_usage (user_id, command, guild_id, used_at)
                VALUES ($1, $2, $3, NOW())
                """,
                user_id, command, guild_id
            )
    except Exception as e:
        logger.debug(f"Error logging command usage: {e}")  # Debug level since this is non-critical
