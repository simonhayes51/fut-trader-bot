# cogs/trending.py - Updated to use dashboard trending API

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

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
            headers={"User-Agent": "Mozilla/5.0"}
        )

    async def cog_unload(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        self.auto_post_trends.cancel()

    async def fetch_trending_data(self, trend_type: str, timeframe: str = "24h") -> List[Dict[str, Any]]:
        """Fetch trending data using dashboard API"""
        try:
            api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
            # Convert timeframe format
            tf = timeframe.replace("h", "")
            
            url = f"{api_base}/api/trending?type={trend_type}&tf={tf}&limit=10"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("items", [])
                else:
                    logger.error(f"API returned status {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to fetch trending data: {e}")
            return []

    def format_trending_embed(self, players: List[Dict[str, Any]], trend_type: str, timeframe: str) -> discord.Embed:
        """Format trending data into Discord embed"""
        
        title_map = {
            "risers": f"📈 Top 10 Risers ({timeframe})",
            "fallers": f"📉 Top 10 Fallers ({timeframe})", 
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
                price = player.get("price_ps") or player.get("price_console")
                
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
        timeframe="Choose timeframe (not applicable for Smart Movers)"
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="risers"),
            app_commands.Choice(name="📉 Fallers", value="fallers"),
            app_commands.Choice(name="🧠 Smart Movers", value="smart")
        ],
        timeframe=[
            app_commands.Choice(name="🕓 6 Hours", value="6h"),
            app_commands.Choice(name="🕐 12 Hours", value="12h"),
            app_commands.Choice(name="🗓️ 24 Hours", value="24h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, 
                      direction: app_commands.Choice[str], 
                      timeframe: app_commands.Choice[str] = None):
        
        await interaction.response.defer()
        
        trend_type = direction.value
        tf = timeframe.value if timeframe else "24h"
        
        # Smart movers don't use timeframe parameter
        if trend_type == "smart":
            tf = "6h_vs_24h"  # Just for display
        
        logger.info(f"📊 /trending by {interaction.user.name} | Type: {trend_type} | Timeframe: {tf}")
        
        try:
            players = await self.fetch_trending_data(trend_type, tf if trend_type != "smart" else "24h")
            
            if not players:
                await interaction.followup.send("❌ No trending data available at the moment.")
                return
            
            embed = self.format_trending_embed(players, trend_type, tf)
            
            # Add refresh button
            view = discord.ui.View(timeout=300)
            refresh_button = discord.ui.Button(
                label="🔄 Refresh",
                style=discord.ButtonStyle.secondary,
                custom_id=f"refresh_{trend_type}_{tf}"
            )
            
            async def refresh_callback(refresh_interaction):
                await refresh_interaction.response.defer()
                new_players = await self.fetch_trending_data(trend_type, tf if trend_type != "smart" else "24h")
                if new_players:
                    new_embed = self.format_trending_embed(new_players, trend_type, tf)
                    await refresh_interaction.edit_original_response(embed=new_embed, view=view)
                else:
                    await refresh_interaction.followup.send("❌ Failed to refresh data.", ephemeral=True)
            
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
                fallers = await self.fetch_trending_data("fallers", "24h")
                risers = await self.fetch_trending_data("risers", "24h")
                
                if fallers:
                    fallers_embed = self.format_trending_embed(fallers, "fallers", "24h")
                    await channel.send(embed=fallers_embed)
                
                if risers:
                    risers_embed = self.format_trending_embed(risers, "risers", "24h")
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

    @app_commands.command(name="setupautotrending", description="⚙️ Configure auto-posting of trends")
    @app_commands.describe(
        channel="Channel to post trending data",
        frequency="How often to post (hours)",
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
            f"🔔 Ping: {ping_role.mention if ping_role else 'None'}"
        )


async def setup(bot):
    await bot.add_cog(Trending(bot))
