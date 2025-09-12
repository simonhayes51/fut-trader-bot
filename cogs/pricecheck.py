# cogs/pricecheck.py - Updated to use dashboard database and API patterns

import discord
from discord.ext import commands
from discord import app_commands
import asyncpg
import asyncio
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import io
from datetime import datetime
import aiohttp
import os
from typing import Dict, Any, Optional, List

log = logging.getLogger("fut-pricecheck")

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.player_pool = None
        self.http_session = None
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self.PRICE_CACHE_TTL = 5  # seconds
        
    async def cog_load(self):
        """Initialize database connection and HTTP session"""
        try:
            # Use the same database URL pattern as your main app
            DATABASE_URL = os.getenv("DATABASE_URL")
            PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL", DATABASE_URL)
            
            self.player_pool = await asyncpg.create_pool(
                PLAYER_DATABASE_URL, 
                min_size=1, 
                max_size=5
            )
            
            self.http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Referer": "https://www.fut.gg/",
                    "Origin": "https://www.fut.gg",
                }
            )
            log.info("✅ PriceCheck cog loaded with database connection")
            
        except Exception as e:
            log.error(f"❌ Failed to initialize PriceCheck cog: {e}")
            
    async def cog_unload(self):
        """Clean up connections"""
        if self.player_pool:
            await self.player_pool.close()
        if self.http_session:
            await self.http_session.close()

    async def search_players(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search players using the same logic as dashboard"""
        if not self.player_pool or not query.strip():
            return []
            
        try:
            # Normalize query for accent-insensitive search
            q_norm = query.lower().strip()
            
            async with self.player_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        card_id, name, rating, version, image_url, club, league, nation,
                        position, altposition, price
                    FROM fut_players
                    WHERE (LOWER(name) LIKE LOWER($1) OR card_id::text LIKE $1)
                    ORDER BY
                        CASE WHEN price IS NULL THEN 1 ELSE 0 END,
                        rating DESC NULLS LAST,
                        name ASC
                    LIMIT $2
                """, f"%{query}%", limit)
                
            return [dict(row) for row in rows]
            
        except Exception as e:
            log.error(f"Player search error: {e}")
            return []

    async def fetch_price(self, card_id: int, platform: str = "ps") -> Dict[str, Any]:
        """Unified price fetching using same logic as dashboard"""
        platform = (platform or "").lower()
        if platform == "console":
            platform = "ps"
            
        key = f"{card_id}|{platform}"
        now = asyncio.get_event_loop().time()

        # Check cache first
        if key in self._price_cache:
            cached = self._price_cache[key]
            if (now - cached["at"]) < self.PRICE_CACHE_TTL:
                return {
                    "price": cached["price"], 
                    "isExtinct": cached["isExtinct"], 
                    "updatedAt": cached["updatedAt"]
                }

        # Fetch from FUT.GG API
        url = f"https://www.fut.gg/api/fut/player-prices/26/{card_id}"
        
        def pick_platform_node(current: Dict[str, Any]) -> Dict[str, Any]:
            if any(k in current for k in ("ps", "xbox", "pc", "playstation")):
                key_map = {"ps": "ps", "xbox": "xbox", "pc": "pc", "console": "ps"}
                k = key_map.get(platform, "ps")
                node = current.get(k)
                if not node and k == "ps":
                    node = current.get("playstation")
                return node or {}
            return current

        try:
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    current = (data.get("data") or {}).get("currentPrice") or {}
                    node = pick_platform_node(current)
                    
                    price = node.get("price")
                    is_extinct = node.get("isExtinct", False)
                    updated_at = node.get("priceUpdatedAt") or current.get("priceUpdatedAt")
                    
                    # Cache the result
                    self._price_cache[key] = {
                        "at": now, 
                        "price": price, 
                        "isExtinct": is_extinct, 
                        "updatedAt": updated_at
                    }
                    
                    return {
                        "price": price, 
                        "isExtinct": is_extinct, 
                        "updatedAt": updated_at
                    }
                    
        except Exception as e:
            log.error(f"Price fetch error for {card_id}: {e}")
            
        # Return cached data if available, even if stale
        cached = self._price_cache.get(key)
        if cached:
            return {
                "price": cached["price"], 
                "isExtinct": cached["isExtinct"], 
                "updatedAt": cached["updatedAt"]
            }
            
        return {"price": None, "isExtinct": False, "updatedAt": None}

    async def get_price_history(self, card_id: int, platform: str = "ps", timeframe: str = "today") -> List[Dict]:
        """Fetch price history using same endpoint as dashboard"""
        try:
            # Use your FastAPI endpoint (assuming bot runs on same server or has access)
            api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
            url = f"{api_base}/api/price-history?playerId={card_id}&platform={platform}&tf={timeframe}"
            
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Normalize the data format
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "points" in data:
                        return data["points"]
                    elif isinstance(data, dict) and "data" in data:
                        return data["data"]
                    return []
        except Exception as e:
            log.error(f"Price history fetch error: {e}")
            return []

    def generate_price_graph(self, price_data: List[Dict], player_name: str) -> Optional[io.BytesIO]:
        """Generate price graph with same styling as dashboard"""
        try:
            if len(price_data) < 2:
                return None

            # Extract timestamps and prices
            times = []
            prices = []
            
            for point in price_data:
                if isinstance(point, dict):
                    # Handle different data formats
                    timestamp = point.get("t") or point.get("time") or point.get("timestamp")
                    price = point.get("price") or point.get("v") or point.get("y")
                elif isinstance(point, list) and len(point) >= 2:
                    timestamp, price = point[0], point[1]
                else:
                    continue
                    
                if timestamp and price:
                    try:
                        if isinstance(timestamp, (int, float)):
                            times.append(datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp))
                        else:
                            times.append(datetime.fromisoformat(str(timestamp)))
                        prices.append(float(price))
                    except:
                        continue

            if len(times) < 2:
                return None

            # Create the plot with dashboard styling
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor("#0D0D0D")
            ax.set_facecolor("#0D0D0D")

            # Plot the price line
            ax.plot(times, prices, marker="o", linestyle="-", color="#39FF14",
                   markersize=3, linewidth=2, alpha=0.9)

            # Styling
            ax.set_title(f"{player_name} - Price History", 
                        color="white", fontsize=14, fontweight="bold", pad=20)
            ax.set_xlabel("Time", color="white", fontsize=10)
            ax.set_ylabel("Price (Coins)", color="white", fontsize=10)

            # Grid
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")

            # Format axes
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K" if x >= 1000 else str(int(x)))
            )

            # Style the spines and ticks
            for spine in ax.spines.values():
                spine.set_color("#555555")
            ax.tick_params(colors="white", labelsize=8)

            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, facecolor=fig.get_facecolor(), 
                       bbox_inches='tight', edgecolor='none')
            buf.seek(0)
            plt.close(fig)

            return buf

        except Exception as e:
            log.error(f"Graph generation error: {e}")
            return None

    @app_commands.command(name="pricecheck", description="Check a player's current price and trend")
    @app_commands.describe(
        player="Enter the player name",
        platform="Choose platform (ps/xbox/pc)"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="🎮 PlayStation", value="ps"),
        app_commands.Choice(name="🎮 Xbox", value="xbox"),
        app_commands.Choice(name="💻 PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, 
                        platform: app_commands.Choice[str] = None):
        
        await interaction.response.defer()
        
        platform_value = platform.value if platform else "ps"
        log.info(f"🔍 /pricecheck by {interaction.user.name} | Player: {player} | Platform: {platform_value}")

        # Search for player
        players = await self.search_players(player, 1)
        if not players:
            await interaction.followup.send(f"❌ No player found matching '{player}'")
            return

        selected_player = players[0]
        card_id = int(selected_player["card_id"])
        
        # Get current price and history concurrently
        price_task = self.fetch_price(card_id, platform_value)
        history_task = self.get_price_history(card_id, platform_value, "today")
        
        price_data, history_data = await asyncio.gather(price_task, history_task, return_exceptions=True)
        
        if isinstance(price_data, Exception):
            price_data = {"price": None, "isExtinct": False, "updatedAt": None}
        if isinstance(history_data, Exception):
            history_data = []

        # Create embed
        embed = discord.Embed(
            title=f"{selected_player['name']} ({selected_player['rating']})",
            color=discord.Color.gold()
        )

        # Add player image
        if selected_player.get("image_url"):
            embed.set_thumbnail(url=selected_player["image_url"])

        # Platform
        platform_name = {"ps": "PlayStation", "xbox": "Xbox", "pc": "PC"}.get(platform_value, "PlayStation")
        embed.add_field(name="🎮 Platform", value=platform_name, inline=False)

        # Price
        if price_data["isExtinct"]:
            price_display = "Extinct 💀"
        elif price_data["price"]:
            price_display = f"{price_data['price']:,} 🪙"
        else:
            price_display = "N/A"
        embed.add_field(name="💰 Current Price", value=price_display, inline=False)

        # Calculate trend from history
        if len(history_data) >= 2:
            try:
                recent_prices = []
                for point in history_data[-10:]:  # Last 10 points
                    if isinstance(point, dict):
                        price = point.get("price") or point.get("v") or point.get("y")
                    elif isinstance(point, list) and len(point) >= 2:
                        price = point[1]
                    else:
                        continue
                    if price:
                        recent_prices.append(float(price))
                        
                if len(recent_prices) >= 2:
                    trend_pct = ((recent_prices[-1] - recent_prices[0]) / recent_prices[0]) * 100
                    trend_emoji = "📈" if trend_pct > 0 else "📉" if trend_pct < 0 else "➡️"
                    trend_display = f"{trend_emoji} {trend_pct:+.1f}%"
                else:
                    trend_display = "➡️ No trend data"
            except:
                trend_display = "➡️ No trend data"
        else:
            trend_display = "➡️ No trend data"
            
        embed.add_field(name="📊 Recent Trend", value=trend_display, inline=False)

        # Player details
        if selected_player.get("club"):
            embed.add_field(name="🏟️ Club", value=selected_player["club"], inline=True)
        if selected_player.get("nation"):
            embed.add_field(name="🌍 Nation", value=selected_player["nation"], inline=True)
        if selected_player.get("position"):
            embed.add_field(name="🎯 Position", value=selected_player["position"], inline=True)

        # Footer
        if price_data.get("updatedAt"):
            try:
                updated_time = datetime.fromisoformat(price_data["updatedAt"].replace("Z", "+00:00"))
                embed.set_footer(text=f"🔴 Updated: {updated_time.strftime('%H:%M %d/%m')} • Data from FUT.GG")
            except:
                embed.set_footer(text="🔴 Data from FUT.GG")
        else:
            embed.set_footer(text="🔴 Data from FUT.GG")

        # Generate and attach graph
        graph_buffer = None
        if history_data:
            graph_buffer = self.generate_price_graph(history_data, selected_player["name"])

        if graph_buffer:
            file = discord.File(graph_buffer, filename="price_history.png")
            embed.set_image(url="attachment://price_history.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for player search"""
        if not current or len(current) < 2:
            return []
            
        try:
            players = await self.search_players(current, 25)
            return [
                app_commands.Choice(
                    name=f"{p['name']} ({p['rating']}) - {p.get('version', 'Base')}",
                    value=f"{p['name']} {p['rating']}"
                )
                for p in players
            ]
        except Exception as e:
            log.error(f"Autocomplete error: {e}")
            return []


async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
