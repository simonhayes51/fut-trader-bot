# cogs/pricecheck.py - Fixed version that works standalone

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
import aiohttp
import time
from datetime import datetime
import os
from typing import Dict, Any, Optional, List

log = logging.getLogger("fut-pricecheck")

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.http_session = None
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self.PRICE_CACHE_TTL = 5  # seconds
        
    async def cog_load(self):
        """Initialize HTTP session"""
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
        log.info("✅ PriceCheck cog loaded")
            
    async def cog_unload(self):
        """Clean up resources"""
        if self.http_session:
            await self.http_session.close()

    async def search_players(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search players using direct database access"""
        if not hasattr(self.bot, 'player_pool') or not self.bot.player_pool:
            log.error("No player database connection available")
            return []
            
        if not query.strip():
            return []
            
        try:
            async with self.bot.player_pool.acquire() as conn:
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
            log.error(f"Database search error: {e}")
            return []

    async def fetch_price(self, card_id: int, platform: str = "ps") -> Dict[str, Any]:
        """Fetch price directly from FUT.GG API"""
        platform = (platform or "").lower()
        if platform == "console":
            platform = "ps"
            
        key = f"{card_id}|{platform}"
        now = time.time()

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

    async def get_price_history_futgg(self, card_id: int, platform: str = "ps") -> List[Dict]:
        """Get price history directly from FUT.GG API"""
        try:
            # FUT.GG doesn't have a direct history endpoint, so we'll return limited data
            # You could implement your own price tracking or use a different source
            current_price = await self.fetch_price(card_id, platform)
            
            # Create a simple history with current price
            if current_price["price"]:
                now = datetime.now()
                return [
                    {"timestamp": now.timestamp() * 1000, "price": current_price["price"]},
                ]
            return []
            
        except Exception as e:
            log.error(f"Error fetching price history for {card_id}: {e}")
            return []

    def generate_price_graph(self, price_data: List[Dict], player_name: str) -> Optional[io.BytesIO]:
        """Generate price graph - simplified for limited data"""
        try:
            if len(price_data) < 1:
                return None

            # For single price point, create a simple info graphic instead
            if len(price_data) == 1:
                price = price_data[0].get("price", 0)
                
                plt.style.use('dark_background')
                fig, ax = plt.subplots(figsize=(8, 4))
                fig.patch.set_facecolor("#0D0D0D")
                ax.set_facecolor("#0D0D0D")

                # Create a simple bar chart
                ax.bar([0], [price], color="#39FF14", width=0.5, alpha=0.8)
                
                ax.set_title(f"{player_name} - Current Price", 
                            color="white", fontsize=16, fontweight="bold", pad=20)
                ax.set_ylabel("Price (Coins)", color="white", fontsize=12)
                
                # Format y-axis
                ax.yaxis.set_major_formatter(
                    ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K" if x >= 1000 else str(int(x)))
                )
                
                # Remove x-axis labels
                ax.set_xticks([])
                
                # Style
                for spine in ax.spines.values():
                    spine.set_color("#555555")
                ax.tick_params(colors="white", labelsize=10)
                
                # Add price text
                ax.text(0, price/2, f"{int(price):,}\nCoins", 
                       ha='center', va='center', color='black', 
                       fontsize=14, fontweight='bold')

                plt.tight_layout()

                # Save to buffer
                buf = io.BytesIO()
                plt.savefig(buf, format="png", dpi=150, facecolor=fig.get_facecolor(), 
                           bbox_inches='tight', edgecolor='none')
                buf.seek(0)
                plt.close(fig)

                return buf

            # If we have multiple points, use the original graph logic
            times = []
            prices = []
            
            for point in price_data:
                try:
                    if isinstance(point, dict):
                        timestamp = point.get("timestamp") or point.get("t") or point.get("time")
                        price = point.get("price") or point.get("v") or point.get("y")
                    elif isinstance(point, list) and len(point) >= 2:
                        timestamp, price = point[0], point[1]
                    else:
                        continue
                        
                    if timestamp and price:
                        if isinstance(timestamp, (int, float)):
                            if timestamp > 1e10:  # milliseconds
                                times.append(datetime.fromtimestamp(timestamp / 1000))
                            else:  # seconds
                                times.append(datetime.fromtimestamp(timestamp))
                        prices.append(float(price))
                except Exception as e:
                    log.debug(f"Skipping invalid data point: {e}")
                    continue

            if len(times) < 2:
                return None

            # Create the plot
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor("#0D0D0D")
            ax.set_facecolor("#0D0D0D")

            # Plot the price line
            ax.plot(times, prices, marker="o", linestyle="-", color="#39FF14",
                   markersize=4, linewidth=2.5, alpha=0.9)

            # Styling
            ax.set_title(f"{player_name} - Price History", 
                        color="white", fontsize=16, fontweight="bold", pad=20)
            ax.set_xlabel("Time", color="white", fontsize=12)
            ax.set_ylabel("Price (Coins)", color="white", fontsize=12)

            # Grid
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")

            # Format axes
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K" if x >= 1000 else str(int(x)))
            )

            # Style spines and ticks
            for spine in ax.spines.values():
                spine.set_color("#555555")
            ax.tick_params(colors="white", labelsize=10)

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

    def format_price(self, price: Optional[int]) -> str:
        """Format price for display"""
        if price is None:
            return "N/A"
        return f"{price:,}"

    def get_trend_emoji(self, percent: Optional[float]) -> str:
        """Get emoji for trend direction"""
        if percent is None:
            return "➡️"
        elif percent > 0:
            return "📈"
        elif percent < 0:
            return "📉"
        else:
            return "➡️"

    @app_commands.command(name="pricecheck", description="Check a player's current price")
    @app_commands.describe(
        player="Enter the player name",
        platform="Choose platform"
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
            embed = discord.Embed(
                title="❌ Player Not Found",
                description=f"No player found matching '{player}'. Try checking the spelling or use a more specific search.",
                color=discord.Color.red()
            )
            embed.add_field(name="💡 Tips", value="• Try just the last name\n• Check for accents (é, ñ, etc.)\n• Use full player name", inline=False)
            await interaction.followup.send(embed=embed)
            return

        selected_player = players[0]
        card_id = int(selected_player["card_id"])
        
        # Get current price and history
        try:
            price_data = await self.fetch_price(card_id, platform_value)
            history_data = await self.get_price_history_futgg(card_id, platform_value)
        except Exception as e:
            log.error(f"Error fetching data: {e}")
            await interaction.followup.send("❌ An error occurred while fetching player data.")
            return

        # Create embed
        embed = discord.Embed(
            title=f"{selected_player['name']} ({selected_player['rating']})",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        # Add player image
        if selected_player.get("image_url"):
            embed.set_thumbnail(url=selected_player["image_url"])

        # Platform display
        platform_names = {"ps": "PlayStation 🎮", "xbox": "Xbox 🎮", "pc": "PC 💻"}
        platform_display = platform_names.get(platform_value, "PlayStation 🎮")
        embed.add_field(name="Platform", value=platform_display, inline=True)

        # Current Price
        if price_data["isExtinct"]:
            price_display = "**Extinct** 💀"
            embed.color = discord.Color.dark_red()
        elif price_data["price"]:
            price_display = f"**{self.format_price(price_data['price'])}** 🪙"
            embed.color = discord.Color.gold()
        else:
            price_display = "**N/A** ❓"
            embed.color = discord.Color.dark_grey()
        
        embed.add_field(name="💰 Current Price", value=price_display, inline=True)

        # Player details
        details = []
        if selected_player.get("club"):
            details.append(f"🏟️ **Club:** {selected_player['club']}")
        if selected_player.get("nation"):
            details.append(f"🌍 **Nation:** {selected_player['nation']}")
        if selected_player.get("position"):
            details.append(f"🎯 **Position:** {selected_player['position']}")
        if selected_player.get("version") and selected_player["version"] != "Base":
            details.append(f"⭐ **Version:** {selected_player['version']}")
            
        if details:
            embed.add_field(name="ℹ️ Player Info", value="\n".join(details), inline=False)

        # Footer
        footer_text = "🔴 Data from FUT.GG"
        if price_data.get("updatedAt"):
            try:
                updated_time = datetime.fromisoformat(price_data["updatedAt"].replace("Z", "+00:00"))
                footer_text += f" • Updated: {updated_time.strftime('%H:%M %d/%m')}"
            except:
                pass
        embed.set_footer(text=footer_text)

        # Generate graph if we have data
        graph_buffer = None
        if history_data:
            graph_buffer = self.generate_price_graph(history_data, selected_player["name"])

        # Create interactive view
        view = discord.ui.View(timeout=300)
        
        # Refresh button
        refresh_button = discord.ui.Button(
            label="🔄 Refresh",
            style=discord.ButtonStyle.secondary
        )
        
        async def refresh_callback(button_interaction):
            await button_interaction.response.defer()
            
            # Re-fetch price
            new_price_data = await self.fetch_price(card_id, platform_value)
            
            # Update embed
            for i, field in enumerate(embed.fields):
                if field.name == "💰 Current Price":
                    if new_price_data["isExtinct"]:
                        new_price_display = "**Extinct** 💀"
                    elif new_price_data["price"]:
                        new_price_display = f"**{self.format_price(new_price_data['price'])}** 🪙"
                    else:
                        new_price_display = "**N/A** ❓"
                    
                    embed.set_field_at(i, name="💰 Current Price", value=new_price_display, inline=True)
                    break
            
            embed.timestamp = datetime.utcnow()
            await button_interaction.edit_original_response(embed=embed, view=view)
        
        refresh_button.callback = refresh_callback
        view.add_item(refresh_button)

        # Send response
        if graph_buffer:
            file = discord.File(graph_buffer, filename=f"{selected_player['name']}_price.png")
            embed.set_image(url=f"attachment://{selected_player['name']}_price.png")
            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for player search"""
        if not current or len(current) < 2:
            return []
            
        try:
            players = await self.search_players(current, 25)
            choices = []
            
            for p in players:
                name = p['name']
                rating = p.get('rating', '')
                version = p.get('version', '')
                club = p.get('club', '')
                
                # Build display name
                display_parts = [name]
                if rating:
                    display_parts.append(f"({rating})")
                if version and version != "Base":
                    display_parts.append(f"[{version}]")
                if club:
                    display_parts.append(f"- {club}")
                
                display_name = " ".join(display_parts)
                
                # Truncate if too long
                if len(display_name) > 100:
                    display_name = display_name[:97] + "..."
                
                value = f"{name} {rating}" if rating else name
                choices.append(app_commands.Choice(name=display_name, value=value))
            
            return choices[:25]
            
        except Exception as e:
            log.error(f"Autocomplete error: {e}")
            return []

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
