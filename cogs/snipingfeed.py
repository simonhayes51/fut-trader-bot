import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.futbin_api import _futbin_api
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Tuple

log = logging.getLogger("fut.sniping")

# FC26 Meta Players to Track (updated IDs for FC26)
DEFAULT_PLAYERS = {
    "Mbappe": 231,
    "Haaland": 276,
    "Vini Jr": 225,
    "Bellingham": 30150,
    "Salah": 192,
    "De Bruyne": 192985,
    "Messi": 158,
    "Ronaldo": 20801,
    "Lewandowski": 188545,
    "Kane": 200104
}

class SnipingFeed(commands.Cog):
    """Enhanced sniping feed with smart alerts and profit calculations"""

    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.players_to_track = DEFAULT_PLAYERS.copy()
        self.price_history: Dict[str, List[int]] = {}  # Track price movements
        self.alert_threshold = 0.92  # Alert when price drops below 92% of average
        self.profit_threshold = 0.05  # Minimum 5% profit margin after tax
        self.last_alerts: Dict[str, datetime] = {}  # Prevent spam
        self.alert_cooldown = 300  # 5 minutes between same alert

    async def cog_load(self):
        """Initialize HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        self.sniping_loop.start()

    def cog_unload(self):
        """Clean up resources"""
        self.sniping_loop.cancel()
        if self.session:
            self.bot.loop.create_task(self.session.close())

    def _calculate_profit(self, buy_price: int, sell_price: int) -> Tuple[int, float]:
        """Calculate profit after EA tax (5%)"""
        tax = int(sell_price * 0.05)
        profit = sell_price - tax - buy_price
        roi = (profit / buy_price * 100) if buy_price > 0 else 0
        return profit, roi

    def _should_send_alert(self, player_name: str) -> bool:
        """Check if enough time has passed to send another alert"""
        if player_name not in self.last_alerts:
            return True
        elapsed = (datetime.utcnow() - self.last_alerts[player_name]).total_seconds()
        return elapsed >= self.alert_cooldown

    def _update_price_history(self, player_name: str, price: int):
        """Track price history for trend analysis"""
        if player_name not in self.price_history:
            self.price_history[player_name] = []
        self.price_history[player_name].append(price)
        # Keep only last 20 prices
        if len(self.price_history[player_name]) > 20:
            self.price_history[player_name].pop(0)

    def _get_price_trend(self, player_name: str) -> str:
        """Analyze price trend"""
        history = self.price_history.get(player_name, [])
        if len(history) < 3:
            return "📊 Stable"

        recent = sum(history[-3:]) / 3
        older = sum(history[-10:-3]) / 7 if len(history) >= 10 else recent

        change = ((recent - older) / older * 100) if older > 0 else 0

        if change > 5:
            return "📈 Rising Fast"
        elif change > 2:
            return "📈 Rising"
        elif change < -5:
            return "📉 Falling Fast"
        elif change < -2:
            return "📉 Falling"
        return "📊 Stable"

    @tasks.loop(minutes=3)
    async def sniping_loop(self):
        """Enhanced sniping loop with better alerts"""
        channel = discord.utils.get(self.bot.get_all_channels(), name="sniping-feed")
        if not channel:
            log.warning("No #sniping-feed channel found")
            return

        for name, pid in self.players_to_track.items():
            try:
                prices = await _futbin_api.get_player_price_async(self.session, pid)
                if not prices:
                    continue

                # Parse prices safely
                ps_price = int(str(prices.get("ps", {}).get("LCPrice", "0")).replace(',', ''))
                xbox_price = int(str(prices.get("xbox", {}).get("LCPrice", "0")).replace(',', ''))
                pc_price = int(str(prices.get("pc", {}).get("LCPrice", "0")).replace(',', ''))

                if ps_price == 0 and xbox_price == 0:
                    continue

                # Calculate metrics
                avg_price = sum(p for p in [ps_price, xbox_price, pc_price] if p > 0) // sum(1 for p in [ps_price, xbox_price, pc_price] if p > 0)
                threshold = int(avg_price * self.alert_threshold)

                # Update price history
                self._update_price_history(name, avg_price)

                # Check for snipe opportunities
                snipe_found = False
                snipe_platforms = []

                for platform, price in [("PS", ps_price), ("Xbox", xbox_price), ("PC", pc_price)]:
                    if price > 0 and price < threshold:
                        profit, roi = self._calculate_profit(price, avg_price)
                        if roi >= (self.profit_threshold * 100):
                            snipe_platforms.append((platform, price, profit, roi))
                            snipe_found = True

                # Send alert if snipe found and cooldown passed
                if snipe_found and self._should_send_alert(name):
                    embed = discord.Embed(
                        title=f"🎯 SNIPE ALERT: {name}",
                        description="Price below market average - potential profit opportunity!",
                        color=discord.Color.gold(),
                        timestamp=datetime.utcnow()
                    )

                    for platform, price, profit, roi in snipe_platforms:
                        embed.add_field(
                            name=f"💰 {platform} Console",
                            value=f"**Buy:** {price:,} 🪙\n**Sell:** {avg_price:,} 🪙\n**Profit:** {profit:,} 🪙\n**ROI:** {roi:.1f}%",
                            inline=True
                        )

                    # Add market info
                    trend = self._get_price_trend(name)
                    embed.add_field(
                        name="📊 Market Trend",
                        value=trend,
                        inline=False
                    )

                    embed.add_field(name="⏱️ Average Price", value=f"{avg_price:,} 🪙", inline=True)
                    embed.add_field(name="📉 Threshold", value=f"{threshold:,} 🪙", inline=True)

                    embed.set_footer(text="FC26 • Futbin Data • Sniping Bot by www.futhub.co.uk")

                    await channel.send(embed=embed)
                    self.last_alerts[name] = datetime.utcnow()
                    log.info(f"[Snipe Alert] {name} - {snipe_platforms}")

            except Exception as e:
                log.error(f"[Sniping Error] {name}: {e}")

    @sniping_loop.before_loop
    async def before_sniping_loop(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()

    @app_commands.command(name="addsnipe", description="➕ Add a player to the sniping tracker")
    @app_commands.describe(
        name="Player name",
        player_id="Futbin player ID"
    )
    async def addsnipe(self, interaction: discord.Interaction, name: str, player_id: int):
        """Add a player to track"""
        self.players_to_track[name] = player_id
        await interaction.response.send_message(
            f"✅ Added **{name}** (ID: {player_id}) to sniping tracker!",
            ephemeral=True
        )
        log.info(f"Added {name} (ID: {player_id}) to sniping tracker")

    @app_commands.command(name="removesnipe", description="➖ Remove a player from sniping tracker")
    @app_commands.describe(name="Player name to remove")
    async def removesnipe(self, interaction: discord.Interaction, name: str):
        """Remove a player from tracking"""
        if name in self.players_to_track:
            del self.players_to_track[name]
            await interaction.response.send_message(
                f"✅ Removed **{name}** from sniping tracker!",
                ephemeral=True
            )
            log.info(f"Removed {name} from sniping tracker")
        else:
            await interaction.response.send_message(
                f"❌ **{name}** not found in tracker!",
                ephemeral=True
            )

    @app_commands.command(name="snipelist", description="📋 View all tracked players")
    async def snipelist(self, interaction: discord.Interaction):
        """List all tracked players"""
        if not self.players_to_track:
            await interaction.response.send_message("📋 No players being tracked.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 Sniping Tracker List",
            description=f"Tracking {len(self.players_to_track)} players for snipe opportunities",
            color=discord.Color.blue()
        )

        player_list = "\n".join([f"• **{name}** (ID: {pid})" for name, pid in self.players_to_track.items()])
        embed.add_field(name="Players", value=player_list, inline=False)
        embed.add_field(name="⚙️ Settings", value=f"Alert Threshold: {int(self.alert_threshold * 100)}%\nMin Profit: {int(self.profit_threshold * 100)}%", inline=False)
        embed.set_footer(text="FC26 • Use /addsnipe to add more players")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SnipingFeed(bot))