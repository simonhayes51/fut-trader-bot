# cogs/pricecheck.py - Updated with API client integration

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
import os
from typing import Dict, Any, Optional, List

# Import the API client
from utils.api_client import APIClient, format_price, format_percentage, get_trend_emoji, normalize_platform

log = logging.getLogger("fut-pricecheck")

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_client = APIClient()
        
    async def cog_load(self):
        """Initialize the cog"""
        log.info("✅ PriceCheck cog loaded with API integration")
            
    async def cog_unload(self):
        """Clean up on unload"""
        log.info("🔄 PriceCheck cog unloaded")

    async def search_players(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search players using the API client or database fallback"""
        try:
            # Try API first
            async with APIClient() as client:
                players = await client.search_players(query, limit)
                if players:
                    return players
        except Exception as e:
            log.warning(f"API search failed, falling back to database: {e}")
        
        # Fallback to direct database search
        if not hasattr(self.bot, 'player_pool') or not self.bot.player_pool:
            log.error("No player database connection available")
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

    async def get_player_price(self, card_id: int, platform: str = "ps") -> Dict[str, Any]:
        """Get current player price"""
        try:
            async with APIClient() as client:
                return await client.get_player_price(card_id, platform)
        except Exception as e:
            log.error(f"Error fetching price for {card_id}: {e}")
            return {"price": None, "isExtinct": False, "updatedAt": None}

    async def get_price_history(self, card_id: int, platform: str = "ps", timeframe: str = "today") -> List[Dict]:
        """Get price history"""
        try:
            async with APIClient() as client:
                return await client.get_price_history(card_id, platform, timeframe)
        except Exception as e:
            log.error(f"Error fetching price history for {card_id}: {e}")
            return []

    def generate_price_graph(self, price_data: List[Dict], player_name: str) -> Optional[io.BytesIO]:
        """Generate price graph with consistent styling"""
        try:
            if len(price_data) < 2:
                return None

            # Extract timestamps and prices
            times = []
            prices = []
            
            for point in price_data:
                try:
                    if isinstance(point, dict):
                        timestamp = point.get("t") or point.get("time") or point.get("timestamp")
                        price = point.get("price") or point.get("v") or point.get("y")
                    elif isinstance(point, list) and len(point) >= 2:
                        timestamp, price = point[0], point[1]
                    else:
                        continue
                        
                    if timestamp and price:
                        if isinstance(timestamp, (int, float)):
                            # Handle both milliseconds and seconds timestamps
                            if timestamp > 1e10:  # milliseconds
                                times.append(datetime.fromtimestamp(timestamp / 1000))
                            else:  # seconds
                                times.append(datetime.fromtimestamp(timestamp))
                        else:
                            times.append(datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")))
                        prices.append(float(price))
                except Exception as e:
                    log.debug(f"Skipping invalid data point: {e}")
                    continue

            if len(times) < 2:
                return None

            # Create the plot with dashboard styling
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(12, 6))
            fig.patch.set_facecolor("#0D0D0D")
            ax.set_facecolor("#0D0D0D")

            # Plot the price line with FUT green
            ax.plot(times, prices, marker="o", linestyle="-", color="#39FF14",
                   markersize=4, linewidth=2.5, alpha=0.9)

            # Enhanced styling
            ax.set_title(f"{player_name} - Price History", 
                        color="white", fontsize=16, fontweight="bold", pad=20)
            ax.set_xlabel("Time", color="white", fontsize=12)
            ax.set_ylabel("Price (Coins)", color="white", fontsize=12)

            # Grid styling
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")

            # Format axes
            if len(times) > 1:
                time_span = (times[-1] - times[0]).total_seconds()
                if time_span < 86400:  # Less than 24 hours
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                else:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
            
            # Format y-axis
            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K" if x >= 1000 else str(int(x)))
            )

            # Style the spines and ticks
            for spine in ax.spines.values():
                spine.set_color("#555555")
                spine.set_linewidth(1)
            ax.tick_params(colors="white", labelsize=10)

            # Add price range annotation
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) / len(prices)
                
                ax.axhline(y=avg_price, color='yellow', linestyle=':', alpha=0.6, linewidth=1)
                ax.text(0.02, 0.98, f"Range: {format_price(int(min_price))} - {format_price(int(max_price))}\nAverage: {format_price(int(avg_price))}", 
                       transform=ax.transAxes, fontsize=10, color='white', 
                       verticalalignment='top', bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))

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

    @app_commands.command(name="pricecheck", description="Check a player's current price and market trend")
    @app_commands.describe(
        player="Enter the player name (e.g., 'Messi', 'Mbappe')",
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
        
        platform_value = normalize_platform(platform.value if platform else "ps")
        log.info(f"🔍 /pricecheck by {interaction.user.name} | Player: {player} | Platform: {platform_value}")

        # Log command usage if we have access to the main database
        if hasattr(self.bot, 'pool') and self.bot.pool:
            try:
                async with self.bot.pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO command_usage (user_id, command, guild_id, used_at) VALUES ($1, $2, $3, NOW()) ON CONFLICT DO NOTHING",
                        str(interaction.user.id), "pricecheck", str(interaction.guild.id) if interaction.guild else None
                    )
            except Exception as e:
                log.debug(f"Failed to log command usage: {e}")

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
        
        # Get current price and history concurrently
        price_task = self.get_player_price(card_id, platform_value)
        history_task = self.get_price_history(card_id, platform_value, "today")
        
        try:
            price_data, history_data = await asyncio.gather(price_task, history_task, return_exceptions=True)
        except Exception as e:
            log.error(f"Error fetching data: {e}")
            await interaction.followup.send("❌ An error occurred while fetching player data.")
            return
        
        if isinstance(price_data, Exception):
            log.error(f"Price data error: {price_data}")
            price_data = {"price": None, "isExtinct": False, "updatedAt": None}
        if isinstance(history_data, Exception):
            log.error(f"History data error: {history_data}")
            history_data = []

        # Create enhanced embed
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

        # Current Price with enhanced display
        if price_data["isExtinct"]:
            price_display = "**Extinct** 💀"
            price_color = discord.Color.dark_red()
        elif price_data["price"]:
            price_display = f"**{format_price(price_data['price'])}** 🪙"
            price_color = discord.Color.gold()
        else:
            price_display = "**N/A** ❓"
            price_color = discord.Color.dark_grey()
        
        embed.add_field(name="💰 Current Price", value=price_display, inline=True)
        embed.color = price_color

        # Calculate enhanced trend analysis
        trend_display = "➡️ No trend data"
        if len(history_data) >= 2:
            try:
                recent_prices = []
                timestamps = []
                
                for point in history_data:
                    try:
                        if isinstance(point, dict):
                            price = point.get("price") or point.get("v") or point.get("y")
                            timestamp = point.get("t") or point.get("time") or point.get("timestamp")
                        elif isinstance(point, list) and len(point) >= 2:
                            timestamp, price = point[0], point[1]
                        else:
                            continue
                            
                        if price and timestamp:
                            recent_prices.append(float(price))
                            timestamps.append(timestamp)
                    except:
                        continue
                        
                if len(recent_prices) >= 2:
                    # Calculate multiple trend periods
                    current_price = recent_prices[-1]
                    
                    # Short term trend (last few hours)
                    short_term_idx = max(0, len(recent_prices) - 6)
                    if short_term_idx < len(recent_prices) - 1:
                        short_term_start = recent_prices[short_term_idx]
                        short_trend_pct = ((current_price - short_term_start) / short_term_start) * 100
                    else:
                        short_trend_pct = 0
                    
                    # Overall trend
                    overall_start = recent_prices[0]
                    overall_trend_pct = ((current_price - overall_start) / overall_start) * 100
                    
                    # Create trend display
                    short_emoji = get_trend_emoji(short_trend_pct)
                    overall_emoji = get_trend_emoji(overall_trend_pct)
                    
                    trend_display = f"{short_emoji} Recent: {format_percentage(short_trend_pct)}\n{overall_emoji} Overall: {format_percentage(overall_trend_pct)}"
                    
                    # Add volatility indicator
                    if len(recent_prices) > 5:
                        price_changes = [abs(recent_prices[i] - recent_prices[i-1]) for i in range(1, len(recent_prices))]
                        avg_change = sum(price_changes) / len(price_changes)
                        volatility = (avg_change / current_price) * 100
                        
                        if volatility > 5:
                            trend_display += f"\n⚡ High volatility ({volatility:.1f}%)"
                        elif volatility > 2:
                            trend_display += f"\n📊 Moderate volatility ({volatility:.1f}%)"
                            
            except Exception as e:
                log.debug(f"Trend calculation error: {e}")
                
        embed.add_field(name="📊 Market Trend", value=trend_display, inline=False)

        # Price statistics from history
        if history_data and len(history_data) > 1:
            try:
                all_prices = []
                for point in history_data:
                    try:
                        if isinstance(point, dict):
                            price = point.get("price") or point.get("v") or point.get("y")
                        elif isinstance(point, list) and len(point) >= 2:
                            price = point[1]
                        else:
                            continue
                        if price:
                            all_prices.append(float(price))
                    except:
                        continue
                
                if all_prices:
                    min_price = min(all_prices)
                    max_price = max(all_prices)
                    avg_price = sum(all_prices) / len(all_prices)
                    
                    stats_text = f"**Low:** {format_price(int(min_price))}\n**High:** {format_price(int(max_price))}\n**Avg:** {format_price(int(avg_price))}"
                    embed.add_field(name="📈 24h Stats", value=stats_text, inline=True)
            except Exception as e:
                log.debug(f"Stats calculation error: {e}")

        # Player details in a more organized way
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
            embed.add_field(name="ℹ️ Player Info", value="\n".join(details), inline=True)

        # Footer with update time and source
        footer_text = "🔴 Data from FUT.GG"
        if price_data.get("updatedAt"):
            try:
                updated_time = datetime.fromisoformat(price_data["updatedAt"].replace("Z", "+00:00"))
                footer_text += f" • Updated: {updated_time.strftime('%H:%M %d/%m')}"
            except:
                pass
        embed.set_footer(text=footer_text)

        # Generate and attach graph
        graph_buffer = None
        if history_data and len(history_data) > 1:
            graph_buffer = self.generate_price_graph(history_data, selected_player["name"])

        # Send response with enhanced interactivity
        view = discord.ui.View(timeout=300)
        
        # Refresh button
        refresh_button = discord.ui.Button(
            label="🔄 Refresh Price",
            style=discord.ButtonStyle.secondary,
            custom_id=f"refresh_price_{card_id}_{platform_value}"
        )
        
        async def refresh_callback(button_interaction):
            await button_interaction.response.defer()
            # Re-fetch current price
            new_price_data = await self.get_player_price(card_id, platform_value)
            
            # Update embed with new price
            for i, field in enumerate(embed.fields):
                if field.name == "💰 Current Price":
                    if new_price_data["isExtinct"]:
                        new_price_display = "**Extinct** 💀"
                    elif new_price_data["price"]:
                        new_price_display = f"**{format_price(new_price_data['price'])}** 🪙"
                    else:
                        new_price_display = "**N/A** ❓"
                    
                    embed.set_field_at(i, name="💰 Current Price", value=new_price_display, inline=True)
                    break
            
            embed.timestamp = datetime.utcnow()
            await button_interaction.edit_original_response(embed=embed, view=view)
        
        refresh_button.callback = refresh_callback
        view.add_item(refresh_button)
        
        # Watchlist button (if user is authenticated)
        watchlist_button = discord.ui.Button(
            label="📌 Add to Watchlist",
            style=discord.ButtonStyle.primary,
            custom_id=f"add_watchlist_{card_id}"
        )
        
        async def watchlist_callback(button_interaction):
            await button_interaction.response.send_message(
                f"💡 To add **{selected_player['name']}** to your watchlist, visit the dashboard at your configured URL and use the player search feature.",
                ephemeral=True
            )
        
        watchlist_button.callback = watchlist_callback
        view.add_item(watchlist_button)

        # Send the response
        if graph_buffer:
            file = discord.File(graph_buffer, filename=f"{selected_player['name']}_price_history.png")
            embed.set_image(url=f"attachment://{selected_player['name']}_price_history.png")
            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        """Enhanced autocomplete for player search"""
        if not current or len(current) < 2:
            return []
            
        try:
            players = await self.search_players(current, 25)
            choices = []
            
            for p in players:
                # Create descriptive choice names
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
                
                # Value for the command
                value = f"{name} {rating}" if rating else name
                
                choices.append(app_commands.Choice(name=display_name, value=value))
            
            return choices[:25]  # Discord limit
            
        except Exception as e:
            log.error(f"Autocomplete error: {e}")
            return [app_commands.Choice(name="Search error - please try again", value="error")]

    @app_commands.command(name="price", description="Quick price check (alias for pricecheck)")
    @app_commands.describe(player="Player name")
    async def price_alias(self, interaction: discord.Interaction, player: str):
        """Alias command for quick price checks"""
        await self.pricecheck(interaction, player)

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
