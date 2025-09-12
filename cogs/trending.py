# cogs/trending.py - Fixed standalone version

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import json
import os
import logging
import re
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.config = self.load_config()
        self.auto_post_trends.start()

    def load_config(self):
        """Load auto-trending configuration"""
        config_file = "autotrend_config.json"
        if not os.path.exists(config_file):
            with open(config_file, "w") as f:
                json.dump({}, f)
        with open(config_file, "r") as f:
            return json.load(f)

    def save_config(self):
        """Save auto-trending configuration"""
        with open("autotrend_config.json", "w") as f:
            json.dump(self.config, f, indent=2)

    async def cog_load(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
                "Referer": "https://www.fut.gg/",
            }
        )

    async def cog_unload(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        self.auto_post_trends.cancel()

    async def fetch_momentum_page(self, timeframe: str, page: int = 1) -> str:
        """Fetch momentum page from FUT.GG"""
        url = f"https://www.fut.gg/players/momentum/{timeframe}/?page={page}"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"Failed to fetch momentum page: {response.status}")
                    return ""
        except Exception as e:
            logger.error(f"Error fetching momentum page: {e}")
            return ""

    def extract_trending_items(self, html: str) -> List[Dict[str, Any]]:
        """Extract trending items from HTML"""
        try:
            soup = BeautifulSoup(html, "html.parser")
            items = []
            
            # Look for player cards with percentage changes
            card_pattern = re.compile(r"/players/(\d+)-[a-z0-9-]+/26-(\d+)/?", re.IGNORECASE)
            pct_pattern = re.compile(r"([+\-]?\s?\d+(?:\.\d+)?)\s*%")
            
            for link in soup.find_all("a", href=True):
                match = card_pattern.search(link["href"])
                if not match:
                    continue
                
                card_id = int(match.group(2))
                
                # Find the percentage in the card's text
                card_text = link.get_text(separator=" ", strip=True)
                pct_match = pct_pattern.search(card_text)
                
                if pct_match:
                    try:
                        percent = float(pct_match.group(1).replace(" ", ""))
                        
                        # Extract player name from the link or nearby text
                        name_elem = link.find(class_=re.compile(r"player.*name", re.I))
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                        else:
                            # Fallback: try to extract from text before percentage
                            name_match = re.search(r"([A-Za-z\s]+)\s+[+\-]?\d+", card_text)
                            name = name_match.group(1).strip() if name_match else f"Player {card_id}"
                        
                        items.append({
                            "card_id": card_id,
                            "name": name,
                            "percent": percent
                        })
                        
                    except (ValueError, AttributeError):
                        continue
            
            return items
            
        except Exception as e:
            logger.error(f"Error extracting trending items: {e}")
            return []

    async def get_player_price(self, card_id: int, platform: str = "ps") -> Optional[int]:
        """Get current player price from FUT.GG"""
        try:
            url = f"https://www.fut.gg/api/fut/player-prices/26/{card_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    current_price = data.get("data", {}).get("currentPrice", {})
                    
                    # Handle platform-specific pricing
                    if platform in current_price:
                        return current_price[platform].get("price")
                    elif "ps" in current_price:
                        return current_price["ps"].get("price")
                    else:
                        return current_price.get("price")
        except Exception as e:
            logger.debug(f"Error fetching price for {card_id}: {e}")
        
        return None

    async def get_player_metadata(self, card_id: int) -> Dict[str, Any]:
        """Get player metadata from database"""
        if not hasattr(self.bot, 'player_pool') or not self.bot.player_pool:
            return {}
            
        try:
            async with self.bot.player_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT name, rating, version, image_url, club, nation, position
                    FROM fut_players
                    WHERE card_id = $1::text
                    LIMIT 1
                """, str(card_id))
                
            return dict(row) if row else {}
            
        except Exception as e:
            logger.debug(f"Error fetching metadata for {card_id}: {e}")
            return {}

    async def fetch_trending_data(self, direction: str, timeframe: str = "24") -> List[Dict[str, Any]]:
        """Fetch trending data based on direction"""
        try:
            if direction == "fallers":
                # Get first page for fallers (lowest percentages)
                html = await self.fetch_momentum_page(timeframe, 1)
                items = self.extract_trending_items(html)
                # Sort by percentage ascending (most negative first)
                items.sort(key=lambda x: x["percent"])
                trending_items = items[:10]
                
            elif direction == "risers":
                # Get last page for risers (highest percentages)
                # First get page 1 to determine total pages
                html = await self.fetch_momentum_page(timeframe, 1)
                soup = BeautifulSoup(html, "html.parser")
                
                # Find pagination to get last page
                last_page = 1
                for link in soup.find_all("a"):
                    href = link.get("href", "")
                    if "page=" in href:
                        try:
                            page_num = int(href.split("page=")[1].split("&")[0])
                            last_page = max(last_page, page_num)
                        except:
                            continue
                
                # Get the last page for highest percentages
                html = await self.fetch_momentum_page(timeframe, last_page)
                items = self.extract_trending_items(html)
                # Sort by percentage descending (most positive first)
                items.sort(key=lambda x: x["percent"], reverse=True)
                trending_items = items[:10]
                
            else:  # smart movers
                # For smart movers, we'd need to compare different timeframes
                # Simplified version: get some fallers and risers
                html_24h = await self.fetch_momentum_page("24", 1)
                html_6h = await self.fetch_momentum_page("6", 1)
                
                items_24h = self.extract_trending_items(html_24h)
                items_6h = self.extract_trending_items(html_6h)
                
                # Create a map for quick lookup
                map_6h = {item["card_id"]: item["percent"] for item in items_6h}
                
                smart_items = []
                for item_24h in items_24h:
                    card_id = item_24h["card_id"]
                    if card_id in map_6h:
                        pct_24h = item_24h["percent"]
                        pct_6h = map_6h[card_id]
                        
                        # Look for divergence (opposite directions or significant difference)
                        if (pct_24h * pct_6h < 0) or abs(pct_24h - pct_6h) > 5:
                            smart_items.append({
                                "card_id": card_id,
                                "name": item_24h["name"],
                                "percent_24h": pct_24h,
                                "percent_6h": pct_6h,
                                "percent": pct_6h  # Use 6h for main display
                            })
                
                trending_items = smart_items[:10]

            # Enrich with metadata and prices
            enriched_items = []
            for item in trending_items:
                # Get metadata from database
                metadata = await self.get_player_metadata(item["card_id"])
                
                # Get current price
                price = await self.get_player_price(item["card_id"], "ps")
                
                # Combine data
                enriched_item = {
                    "card_id": item["card_id"],
                    "name": metadata.get("name", item["name"]),
                    "rating": metadata.get("rating"),
                    "version": metadata.get("version", "Base"),
                    "image_url": metadata.get("image_url"),
                    "club": metadata.get("club"),
                    "nation": metadata.get("nation"),
                    "position": metadata.get("position"),
                    "percent": item["percent"],
                    "price_ps": price
                }
                
                # Add smart mover specific data
                if direction == "smart":
                    enriched_item["percent_6h"] = item.get("percent_6h")
                    enriched_item["percent_24h"] = item.get("percent_24h")
                
                enriched_items.append(enriched_item)

            return enriched_items

        except Exception as e:
            logger.error(f"Error fetching trending data: {e}")
            return []

    def format_trending_embed(self, players: List[Dict[str, Any]], trend_type: str, timeframe: str) -> discord.Embed:
        """Format trending data into Discord embed"""
        
        title_map = {
            "risers": f"📈 Top 10 Risers ({timeframe}h)",
            "fallers": f"📉 Top 10 Fallers ({timeframe}h)", 
            "smart": "🧠 Smart Movers (6h vs 24h)"
        }
        
        color_map = {
            "risers": discord.Color.green(),
            "fallers": discord.Color.red(),
            "smart": discord.Color.purple()
        }
        
        embed = discord.Embed(
            title=title_map.get(trend_type, "Trending Players"),
            color=color_map.get(trend_type, discord.Color.blue()),
            timestamp=datetime.utcnow()
        )
        
        if not players:
            embed.description = "No trending data available at the moment."
            return embed
        
        # Number emojis for ranking
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        # Split into two columns
        left_players = players[:5]
        right_players = players[5:10]
        
        def format_player_list(player_list: List[Dict[str, Any]], start_index: int = 0) -> str:
            lines = []
            for i, player in enumerate(player_list):
                emoji = number_emojis[start_index + i] if start_index + i < len(number_emojis) else f"{start_index + i + 1}."
                
                name = player.get("name", "Unknown")
                rating = player.get("rating")
                price = player.get("price_ps")
                
                # Handle different percent formats based on trend type
                if trend_type == "smart":
                    percent_6h = player.get("percent_6h", 0)
                    percent_24h = player.get("percent_24h", 0)
                    percent_display = f"6h: {percent_6h:+.1f}% | 24h: {percent_24h:+.1f}%"
                else:
                    percent = player.get("percent", 0)
                    percent_display = f"{percent:+.1f}%"
                
                price_display = f"{int(price):,}" if isinstance(price, (int, float)) else "N/A"
                
                line = f"{emoji} **{name}"
                if rating:
                    line += f" ({rating})"
                line += "**\n"
                line += f"💰 {price_display}\n"
                line += f"📊 {percent_display}\n"
                
                lines.append(line)
            
            return "\n".join(lines)
        
        if left_players:
            embed.add_field(
                name="\u200b", 
                value=format_player_list(left_players, 0), 
                inline=True
            )
        
        if right_players:
            embed.add_field(
                name="\u200b", 
                value=format_player_list(right_players, 5), 
                inline=True
            )
        
        embed.set_footer(text="Data from FUT.GG | Console prices")
        return embed

    @app_commands.command(name="trending", description="📊 Show trending players")
    @app_commands.describe(
        direction="Choose trending direction",
        timeframe="Choose timeframe (6h, 12h, 24h)"
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="risers"),
            app_commands.Choice(name="📉 Fallers", value="fallers"),
            app_commands.Choice(name="🧠 Smart Movers", value="smart")
        ],
        timeframe=[
            app_commands.Choice(name="🕓 6 Hours", value="6"),
            app_commands.Choice(name="🕐 12 Hours", value="12"),
            app_commands.Choice(name="🗓️ 24 Hours", value="24")
        ]
    )
    async def trending(self, interaction: discord.Interaction, 
                      direction: app_commands.Choice[str], 
                      timeframe: app_commands.Choice[str] = None):
        
        await interaction.response.defer()
        
        trend_type = direction.value
        tf = timeframe.value if timeframe else "24"
        
        logger.info(f"📊 /trending by {interaction.user.name} | Type: {trend_type} | Timeframe: {tf}h")
        
        try:
            players = await self.fetch_trending_data(trend_type, tf)
            
            if not players:
                await interaction.followup.send("❌ No trending data available at the moment. Please try again later.")
                return
            
            embed = self.format_trending_embed(players, trend_type, tf)
            
            # Add refresh button
            view = discord.ui.View(timeout=300)
            refresh_button = discord.ui.Button(
                label="🔄 Refresh",
                style=discord.ButtonStyle.secondary
            )
            
            async def refresh_callback(refresh_interaction):
                await refresh_interaction.response.defer()
                try:
                    new_players = await self.fetch_trending_data(trend_type, tf)
                    if new_players:
                        new_embed = self.format_trending_embed(new_players, trend_type, tf)
                        await refresh_interaction.edit_original_response(embed=new_embed, view=view)
                    else:
                        await refresh_interaction.followup.send("❌ Failed to refresh data.", ephemeral=True)
                except Exception as e:
                    logger.error(f"Refresh error: {e}")
                    await refresh_interaction.followup.send("❌ Error refreshing data.", ephemeral=True)
            
            refresh_button.callback = refresh_callback
            view.add_item(refresh_button)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Trending command error: {e}")
            await interaction.followup.send("❌ An error occurred while fetching trending data.")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        """Auto-post trending data to configured channels"""
        now = datetime.utcnow().strftime("%H:%M")
        
        for guild_id, config in self.config.items():
            try:
                if now != config.get("start_time", "00:00"):
                    continue
                if not config.get("enabled", False):
                    continue
                    
                # Check if already posted today
                if config.get("last_post") == now:
                    continue
                
                channel_id = config.get("channel_id")
                channel = self.bot.get_channel(channel_id)
                
                if not channel:
                    continue
                
                # Fetch both fallers and risers
                fallers = await self.fetch_trending_data("fallers", "24")
                risers = await self.fetch_trending_data("risers", "24")
                
                if fallers:
                    fallers_embed = self.format_trending_embed(fallers, "fallers", "24")
                    await channel.send(embed=fallers_embed)
                    await asyncio.sleep(1)  # Small delay between messages
                
                if risers:
                    risers_embed = self.format_trending_embed(risers, "risers", "24")
                    await channel.send(embed=risers_embed)
                
                # Optional ping
                ping_role = config.get("ping_role")
                if ping_role:
                    await channel.send(f"<@&{ping_role}>")
                
                # Update last post time
                self.config[guild_id]["last_post"] = now
                self.save_config()
                
                logger.info(f"✅ Auto-posted trends to guild {guild_id}")
                
            except Exception as e:
                logger.error(f"❌ Auto-post error in guild {guild_id}: {e}")

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        """Wait for bot to be ready before starting auto-post loop"""
        await self.bot.wait_until_ready()

    @app_commands.command(name="setupautotrending", description="⚙️ Configure auto-posting of trends")
    @app_commands.describe(
        channel="Channel to post trending data",
        frequency="How often to post (hours) - currently only daily is supported",
        start_time="What time to start posting (HH:MM UTC)",
        ping_role="Optional role to ping"
    )
    async def setupautotrending(self, interaction: discord.Interaction, 
                               channel: discord.TextChannel, 
                               frequency: int, 
                               start_time: str, 
                               ping_role: discord.Role = None):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
            return
        
        # Validate time format
        try:
            datetime.strptime(start_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use HH:MM (e.g., 18:00)", ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "frequency": frequency,
            "start_time": start_time,
            "enabled": True,
            "ping_role": ping_role.id if ping_role else None
        }
        
        self.save_config()
        
        await interaction.response.send_message(
            f"✅ Auto-trending configured!\n"
            f"📍 Channel: {channel.mention}\n"
            f"⏰ Time: {start_time} UTC daily\n"
            f"🔔 Ping: {ping_role.mention if ping_role else 'None'}\n\n"
            f"💡 The bot will post daily trending data at the specified time."
        )

    @app_commands.command(name="disableautotrending", description="❌ Disable auto-posting of trends")
    async def disableautotrending(self, interaction: discord.Interaction):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        if guild_id in self.config:
            self.config[guild_id]["enabled"] = False
            self.save_config()
            await interaction.response.send_message("✅ Auto-trending disabled for this server.")
        else:
            await interaction.response.send_message("❌ Auto-trending is not configured for this server.")


async def setup(bot):
    await bot.add_cog(Trending(bot))
