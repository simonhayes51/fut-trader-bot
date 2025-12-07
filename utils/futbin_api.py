import requests
import aiohttp
import asyncio
from typing import Optional, Dict, Any
import time

class FutbinAPI:
    """Enhanced Futbin API client for FC26 with rate limiting and caching"""

    BASE_URL = "https://www.futbin.com/26"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-GB,en;q=0.9'
    }

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 120  # 2 minutes cache
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 500ms between requests

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache:
            return False
        cached_time, _ = self.cache[key]
        return (time.time() - cached_time) < self.cache_ttl

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get data from cache if valid"""
        if self._is_cache_valid(key):
            _, data = self.cache[key]
            return data
        return None

    def _save_to_cache(self, key: str, data: Dict):
        """Save data to cache with timestamp"""
        self.cache[key] = (time.time(), data)

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def get_player_price(self, player_id: int) -> Dict[str, Any]:
        """Get player price from Futbin (synchronous)"""
        cache_key = f"price_{player_id}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Rate limit
        self._rate_limit()

        url = f"{self.BASE_URL}/playerPrices?player={player_id}"
        try:
            res = requests.get(url, headers=self.HEADERS, timeout=10)
            if res.status_code == 200:
                data = res.json().get(str(player_id), {}).get("prices", {})
                self._save_to_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"[Futbin API] Price fetch error for {player_id}: {e}")
        return {}

    async def get_player_price_async(self, session: aiohttp.ClientSession, player_id: int) -> Dict[str, Any]:
        """Get player price from Futbin (async)"""
        cache_key = f"price_{player_id}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        url = f"{self.BASE_URL}/playerPrices?player={player_id}"
        try:
            async with session.get(url, headers=self.HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    data = json_data.get(str(player_id), {}).get("prices", {})
                    self._save_to_cache(cache_key, data)
                    await asyncio.sleep(self.rate_limit_delay)
                    return data
        except Exception as e:
            print(f"[Futbin API] Async price fetch error for {player_id}: {e}")
        return {}

# Global instance
_futbin_api = FutbinAPI()

# Legacy function for backwards compatibility
def get_player_price(player_id):
    """Legacy function - uses new API client"""
    return _futbin_api.get_player_price(player_id)