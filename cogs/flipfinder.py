import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from utils.futbin_api import _futbin_api

log = logging.getLogger("fut.flipfinder")

class FlipFinder(commands.Cog):
    """
    Find profitable flip opportunities in real-time
    The feature that helps users make coins FAST
    """

    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None

        # Store flip opportunities
        self.current_flips: List[Dict] = []
        self.last_update: Optional[datetime] = None

        # Premium users (in production, load from database)
        self.premium_users: set = set()

        # Popular tradeable items (update for FC26)
        self.flip_candidates = {
            # Chemistry Styles
            "Shadow": {"id": "shadow", "type": "chem", "typical_price": 4500},
            "Hunter": {"id": "hunter", "type": "chem", "typical_price": 4000},
            "Catalyst": {"id": "catalyst", "type": "chem", "typical_price": 2500},
            "Engine": {"id": "engine", "type": "chem", "typical_price": 2000},

            # Position Modifiers
            "CF→CAM": {"id": "cf_cam", "type": "position", "typical_price": 800},
            "CM→CAM": {"id": "cm_cam", "type": "position", "typical_price": 600},
            "ST→CF": {"id": "st_cf", "type": "position", "typical_price": 500},

            # Common fodder (by rating)
            "83 Rated": {"id": "83_fodder", "type": "fodder", "typical_price": 1500},
            "84 Rated": {"id": "84_fodder", "type": "fodder", "typical_price": 2500},
            "85 Rated": {"id": "85_fodder", "type": "fodder", "typical_price": 5000},

            # Meta players (examples - would be dynamic in production)
            "Mbappe": {"id": 231, "type": "player", "typical_price": 1200000},
            "Haaland": {"id": 276, "type": "player", "typical_price": 850000},
        }

    async def cog_load(self):
        """Initialize resources"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        self.update_flips.start()

    def cog_unload(self):
        """Clean up resources"""
        self.update_flips.cancel()
        if self.session:
            self.bot.loop.create_task(self.session.close())

    @tasks.loop(minutes=5)  # Update every 5 minutes
    async def update_flips(self):
        """Update flip opportunities"""
        try:
            await self._scan_for_flips()
            self.last_update = datetime.utcnow()
            log.info(f"[FlipFinder] Updated {len(self.current_flips)} flip opportunities")
        except Exception as e:
            log.error(f"[FlipFinder] Error updating flips: {e}")

    @update_flips.before_loop
    async def before_update_flips(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()

    async def _scan_for_flips(self):
        """Scan market for flip opportunities"""
        new_flips = []

        # In production: fetch real prices from market
        # For now, simulate flip opportunities

        # Example: Chemistry style flips
        new_flips.append({
            "name": "Shadow Chemistry Style",
            "type": "consumable",
            "buy_price": 3200,
            "sell_price": 4500,
            "profit": self._calculate_profit(3200, 4500),
            "roi": self._calculate_roi(3200, 4500),
            "time_to_sell": "Instant",
            "risk": "low",
            "supply": "high",
            "demand": "very_high",
            "confidence": 95,
        })

        new_flips.append({
            "name": "Hunter Chemistry Style",
            "type": "consumable",
            "buy_price": 2900,
            "sell_price": 4200,
            "profit": self._calculate_profit(2900, 4200),
            "roi": self._calculate_roi(2900, 4200),
            "time_to_sell": "Instant",
            "risk": "low",
            "supply": "high",
            "demand": "high",
            "confidence": 90,
        })

        # Fodder flips
        new_flips.append({
            "name": "83 Rated Fodder",
            "type": "fodder",
            "buy_price": 1100,
            "sell_price": 1800,
            "profit": self._calculate_profit(1100, 1800),
            "roi": self._calculate_roi(1100, 1800),
            "time_to_sell": "1-3 days",
            "risk": "low",
            "supply": "high",
            "demand": "medium",
            "confidence": 85,
        })

        new_flips.append({
            "name": "84 Rated Fodder",
            "type": "fodder",
            "buy_price": 2000,
            "sell_price": 3500,
            "profit": self._calculate_profit(2000, 3500),
            "roi": self._calculate_roi(2000, 3500),
            "time_to_sell": "2-5 days",
            "risk": "medium",
            "supply": "medium",
            "demand": "medium",
            "confidence": 80,
        })

        # Player flips (meta cards)
        new_flips.append({
            "name": "Meta Gold Cards",
            "type": "player",
            "buy_price": 45000,
            "sell_price": 52000,
            "profit": self._calculate_profit(45000, 52000),
            "roi": self._calculate_roi(45000, 52000),
            "time_to_sell": "Weekend (2-3 days)",
            "risk": "medium",
            "supply": "medium",
            "demand": "high",
            "confidence": 75,
            "note": "Buy Thursday rewards, sell Friday WL hype"
        })

        # Sort by profit
        new_flips.sort(key=lambda x: x["profit"], reverse=True)

        self.current_flips = new_flips

    def _calculate_profit(self, buy: int, sell: int) -> int:
        """Calculate profit after EA tax"""
        tax = int(sell * 0.05)
        return sell - tax - buy

    def _calculate_roi(self, buy: int, sell: int) -> float:
        """Calculate ROI percentage"""
        profit = self._calculate_profit(buy, sell)
        return (profit / buy * 100) if buy > 0 else 0

    def _get_risk_emoji(self, risk: str) -> str:
        """Get emoji for risk level"""
        if risk == "low":
            return "🟢"
        elif risk == "medium":
            return "🟡"
        else:
            return "🔴"

    @app_commands.command(name="flips", description="💰 Find profitable flip opportunities NOW")
    @app_commands.describe(budget="Your budget (optional, shows all if not specified)")
    async def flips(self, interaction: discord.Interaction, budget: Optional[int] = None):
        """Show current flip opportunities"""
        await interaction.response.defer()

        if not self.current_flips:
            await self._scan_for_flips()

        # Filter by budget
        if budget:
            available_flips = [f for f in self.current_flips if f["buy_price"] <= budget]
        else:
            available_flips = self.current_flips

        # Limit based on premium status
        is_premium = interaction.user.id in self.premium_users
        max_flips = 20 if is_premium else 3

        available_flips = available_flips[:max_flips]

        if not available_flips:
            embed = discord.Embed(
                title="💰 Flip Opportunities",
                description=f"No flips found within your budget of {budget:,} coins." if budget else "No flips available right now.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        # Create embed
        embed = discord.Embed(
            title="💰 Profitable Flip Opportunities",
            description=f"Top {len(available_flips)} flips available NOW" + (f" (Budget: {budget:,} coins)" if budget else ""),
            color=discord.Color.gold()
        )

        for i, flip in enumerate(available_flips, 1):
            risk_emoji = self._get_risk_emoji(flip["risk"])

            value = f"**Buy:** {flip['buy_price']:,} 🪙\n"
            value += f"**Sell:** {flip['sell_price']:,} 🪙\n"
            value += f"**Profit:** {flip['profit']:,} 🪙 (ROI: {flip['roi']:.1f}%)\n"
            value += f"**Time:** {flip['time_to_sell']}\n"
            value += f"**Risk:** {risk_emoji} {flip['risk'].capitalize()}\n"

            if "note" in flip:
                value += f"*{flip['note']}*\n"

            embed.add_field(
                name=f"{i}. {flip['name']}",
                value=value,
                inline=False
            )

        # Footer
        if not is_premium and len(self.current_flips) > 3:
            footer_text = f"💎 Premium: See all {len(self.current_flips)} flips + updates every 5 min"
        else:
            footer_text = f"Last updated: {self.last_update.strftime('%H:%M UTC') if self.last_update else 'Never'}"

        embed.set_footer(text=footer_text)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quickflip", description="⚡ Find instant flip opportunities")
    async def quickflip(self, interaction: discord.Interaction):
        """Show instant flip opportunities (low risk, fast sell)"""
        await interaction.response.defer()

        if not self.current_flips:
            await self._scan_for_flips()

        # Filter for instant flips
        instant_flips = [f for f in self.current_flips if "instant" in f["time_to_sell"].lower() and f["risk"] == "low"]

        if not instant_flips:
            embed = discord.Embed(
                title="⚡ Quick Flips",
                description="No instant flips available right now. Check back in a few minutes!",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(
            title="⚡ Instant Flip Opportunities",
            description="These sell fast - act quickly!",
            color=discord.Color.green()
        )

        for i, flip in enumerate(instant_flips[:5], 1):
            value = f"**Buy:** {flip['buy_price']:,} 🪙 → **Sell:** {flip['sell_price']:,} 🪙\n"
            value += f"**Profit:** {flip['profit']:,} 🪙 ({flip['roi']:.1f}% ROI)\n"
            value += f"**Confidence:** {flip['confidence']}%"

            embed.add_field(
                name=f"{i}. {flip['name']}",
                value=value,
                inline=False
            )

        embed.set_footer(text="FC26 • Instant Flips • Buy now, sell within 1 hour")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="flipcalc", description="🧮 Calculate flip profit")
    @app_commands.describe(
        buy_price="Price you'll buy at",
        sell_price="Price you'll sell at",
        quantity="How many cards (default: 1)"
    )
    async def flipcalc(self, interaction: discord.Interaction, buy_price: int, sell_price: int, quantity: int = 1):
        """Calculate flip profit"""
        if quantity < 1 or quantity > 100:
            await interaction.response.send_message("❌ Quantity must be 1-100", ephemeral=True)
            return

        profit_per_card = self._calculate_profit(buy_price, sell_price)
        total_profit = profit_per_card * quantity
        roi = self._calculate_roi(buy_price, sell_price)

        total_investment = buy_price * quantity
        total_revenue = sell_price * quantity
        total_tax = int(total_revenue * 0.05)

        embed = discord.Embed(
            title="🧮 Flip Calculator",
            description=f"Profit analysis for {quantity}x card(s)",
            color=discord.Color.blue()
        )

        embed.add_field(name="💰 Buy Price", value=f"{buy_price:,} 🪙", inline=True)
        embed.add_field(name="💵 Sell Price", value=f"{sell_price:,} 🪙", inline=True)
        embed.add_field(name="📦 Quantity", value=f"{quantity}x", inline=True)

        embed.add_field(name="💸 Total Investment", value=f"{total_investment:,} 🪙", inline=True)
        embed.add_field(name="💰 EA Tax (5%)", value=f"{total_tax:,} 🪙", inline=True)
        embed.add_field(name="📈 Total Profit", value=f"**{total_profit:,}** 🪙", inline=True)

        embed.add_field(name="📊 ROI", value=f"{roi:.1f}%", inline=True)
        embed.add_field(name="💎 Per Card", value=f"{profit_per_card:,} 🪙", inline=True)

        # Advice
        if roi >= 20:
            advice = "🔥 Excellent flip!"
        elif roi >= 10:
            advice = "✅ Good flip"
        elif roi >= 5:
            advice = "👍 Decent flip"
        else:
            advice = "⚠️ Low profit margin"

        embed.add_field(name="💡 Analysis", value=advice, inline=False)

        embed.set_footer(text="FC26 • Flip Calculator")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="investcalc", description="💎 Calculate investment returns")
    @app_commands.describe(
        buy_price="Price per card",
        target_price="Target sell price",
        investment="Total coins to invest"
    )
    async def investcalc(self, interaction: discord.Interaction, buy_price: int, target_price: int, investment: int):
        """Calculate how many cards you can buy and potential profit"""
        quantity = investment // buy_price

        if quantity < 1:
            await interaction.response.send_message("❌ Not enough coins to buy even 1 card!", ephemeral=True)
            return

        actual_investment = buy_price * quantity
        leftover = investment - actual_investment

        profit_per_card = self._calculate_profit(buy_price, target_price)
        total_profit = profit_per_card * quantity
        roi = self._calculate_roi(buy_price, target_price)

        embed = discord.Embed(
            title="💎 Investment Calculator",
            description=f"Investing {investment:,} coins",
            color=discord.Color.purple()
        )

        embed.add_field(name="🛒 Cards to Buy", value=f"**{quantity}x** @ {buy_price:,} each", inline=False)
        embed.add_field(name="💰 Total Investment", value=f"{actual_investment:,} 🪙", inline=True)
        embed.add_field(name="💵 Leftover", value=f"{leftover:,} 🪙", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="🎯 Target Price", value=f"{target_price:,} 🪙", inline=True)
        embed.add_field(name="📈 Total Profit", value=f"**{total_profit:,}** 🪙", inline=True)
        embed.add_field(name="📊 ROI", value=f"**{roi:.1f}%**", inline=True)

        # Final balance
        final_balance = investment + total_profit
        embed.add_field(
            name="💎 Final Balance",
            value=f"**{final_balance:,}** 🪙 (from {investment:,})",
            inline=False
        )

        embed.set_footer(text="FC26 • Investment Calculator • Plan your trades")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(FlipFinder(bot))
