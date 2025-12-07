import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

log = logging.getLogger("fut.marketanalysis")

class MarketAnalysis(commands.Cog):
    """FC26 Market analysis and investment suggestions"""

    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.price_tracker: Dict[str, List[Dict]] = {}  # Track price history
        self.market_trends: Dict[str, str] = {}  # Store trend analysis

    async def cog_load(self):
        """Initialize resources"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()

    def _analyze_volatility(self, prices: List[int]) -> Tuple[float, str]:
        """Calculate price volatility"""
        if len(prices) < 2:
            return 0.0, "📊 Stable"

        # Calculate standard deviation
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5

        # Coefficient of variation (CV) as percentage
        cv = (std_dev / mean * 100) if mean > 0 else 0

        if cv > 20:
            return cv, "🔴 Very Volatile"
        elif cv > 10:
            return cv, "🟠 Volatile"
        elif cv > 5:
            return cv, "🟡 Moderately Stable"
        else:
            return cv, "🟢 Very Stable"

    def _calculate_trend(self, prices: List[int]) -> str:
        """Calculate price trend direction"""
        if len(prices) < 3:
            return "📊 Insufficient Data"

        recent = prices[-3:]
        older = prices[-6:-3] if len(prices) >= 6 else prices[:-3]

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older) if older else recent_avg

        change = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0

        if change > 10:
            return "📈 Strong Uptrend"
        elif change > 5:
            return "📈 Uptrend"
        elif change > 2:
            return "📈 Slight Rise"
        elif change < -10:
            return "📉 Strong Downtrend"
        elif change < -5:
            return "📉 Downtrend"
        elif change < -2:
            return "📉 Slight Drop"
        else:
            return "➡️ Sideways"

    @app_commands.command(name="marketoverview", description="📊 FC26 Market overview and trends")
    async def marketoverview(self, interaction: discord.Interaction):
        """Show general market overview"""
        await interaction.response.defer()

        embed = discord.Embed(
            title="📊 FC26 Market Overview",
            description="Current market trends and insights",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Market Phases (based on FC cycle)
        today = datetime.utcnow()
        # Determine market phase based on date
        if today.month == 9:
            phase = "🚀 Early Access - Prices HIGH"
            advice = "Sell high-rated cards, hold meta cards"
        elif today.month == 10:
            phase = "📉 Market Crash - Prices falling"
            advice = "Buy investments, avoid panic selling"
        elif today.month in [11, 12]:
            phase = "🎄 Black Friday/TOTY Hype"
            advice = "Prepare for crash, sell before promos"
        elif today.month in [1, 2]:
            phase = "⚽ TOTY Period - Volatile market"
            advice = "Trade carefully, flip promo cards"
        elif today.month in [3, 4]:
            phase = "🌸 Spring Period - Stable market"
            advice = "Long-term investments, SBC fodder"
        elif today.month in [5, 6]:
            phase = "☀️ TOTS Season - High volume"
            advice = "Flip TOTS cards, buy weekend dips"
        elif today.month in [7, 8]:
            phase = "🏖️ Summer - End of cycle"
            advice = "Prices declining, play not trade"
        else:
            phase = "📊 Normal Period"
            advice = "Standard trading strategies apply"

        embed.add_field(name="📅 Market Phase", value=phase, inline=False)
        embed.add_field(name="💡 Trading Advice", value=advice, inline=False)

        # Best times to buy/sell
        embed.add_field(
            name="⏰ Best Time to BUY",
            value="• Sunday evenings\n• During WL rewards\n• Thursday (Rivals rewards)\n• Monday mornings",
            inline=True
        )

        embed.add_field(
            name="⏰ Best Time to SELL",
            value="• Friday (WL starts)\n• Tuesday (SBC release)\n• Before content drops\n• Weekend mornings",
            inline=True
        )

        # Key tips
        tips = """
        🔥 **Hot Strategies for FC26:**
        • Buy meta cards during rewards
        • Sell meta cards Friday afternoon
        • Hold fodder before good SBCs
        • Buy IFs on Thursday, sell Tuesday
        • Watch for content leaks
        • Never panic sell during promos
        """
        embed.add_field(name="🎯 Pro Tips", value=tips, inline=False)

        # Current opportunities
        opps = """
        💎 **Current Opportunities:**
        • 83-84 rated fodder (always needed)
        • Position change consumables
        • League SBC cards
        • Evolution-viable cards
        • Shadow/Hunter chemistry styles
        """
        embed.add_field(name="💰 Investments", value=opps, inline=False)

        embed.set_footer(text="FC26 • Market Analysis • www.futhub.co.uk")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="investments", description="💎 Get FC26 investment suggestions")
    @app_commands.choices(budget=[
        app_commands.Choice(name="💰 Budget (<50k)", value="budget"),
        app_commands.Choice(name="💎 Medium (50k-200k)", value="medium"),
        app_commands.Choice(name="🔥 High (200k+)", value="high"),
    ])
    async def investments(self, interaction: discord.Interaction, budget: app_commands.Choice[str]):
        """Suggest investments based on budget"""
        await interaction.response.defer()

        embed = discord.Embed(
            title=f"💎 FC26 Investment Suggestions",
            description=f"Recommended investments for {budget.name}",
            color=discord.Color.gold()
        )

        if budget.value == "budget":
            # Budget investments (<50k)
            investments = {
                "📘 83-84 Fodder": {
                    "buy": "1,000-2,000 per card",
                    "why": "Always needed for SBCs, safe long-term hold",
                    "risk": "🟢 Low Risk",
                    "time": "1-4 weeks"
                },
                "⚽ League SBC Players": {
                    "buy": "Min bid to 5k",
                    "why": "Required for league SBCs, instant profit",
                    "risk": "🟢 Low Risk",
                    "time": "When SBC releases"
                },
                "🎯 Position Modifiers": {
                    "buy": "200-400 coins",
                    "why": "Always in demand, quick flips",
                    "risk": "🟢 Low Risk",
                    "time": "Daily flips"
                },
                "💨 Chemistry Styles": {
                    "buy": "Shadow/Hunter at 3-4k",
                    "why": "High demand, consistent profit",
                    "risk": "🟡 Medium Risk",
                    "time": "Weekend flips"
                },
            }

        elif budget.value == "medium":
            # Medium investments (50k-200k)
            investments = {
                "⭐ 85-86 Fodder": {
                    "buy": "Buy during rewards (Thursday)",
                    "why": "Icon SBCs and high-rated SBCs",
                    "risk": "🟡 Medium Risk",
                    "time": "2-6 weeks"
                },
                "🔥 Meta Golds": {
                    "buy": "Buy Sunday, sell Friday",
                    "why": "Weekend League demand spike",
                    "risk": "🟡 Medium Risk",
                    "time": "Weekly flips"
                },
                "📈 Inform Cards (TOTW)": {
                    "buy": "Buy Thursday rewards, sell Tuesday",
                    "why": "Marquee Matchups requirement",
                    "risk": "🟠 Medium-High Risk",
                    "time": "5 days"
                },
                "🎮 Special Cards": {
                    "buy": "Buy end of promo, sell hype",
                    "why": "Out of packs = price rise",
                    "risk": "🟠 Medium-High Risk",
                    "time": "1-3 weeks"
                },
            }

        else:  # high
            # High investments (200k+)
            investments = {
                "🔥 High-Rated Meta Cards": {
                    "buy": "Buy during market crash",
                    "why": "Always in demand, hold value",
                    "risk": "🟡 Medium Risk",
                    "time": "Long-term hold"
                },
                "⭐ Icons/Heroes": {
                    "buy": "Buy during panic sells",
                    "why": "Strong links, SBC fodder later",
                    "risk": "🟠 Medium-High Risk",
                    "time": "4-8 weeks"
                },
                "💎 87-89 Fodder (Mass)": {
                    "buy": "Buy rewards, sell before SBCs",
                    "why": "Icon SBCs need high-rated cards",
                    "risk": "🟡 Medium Risk",
                    "time": "3-6 weeks"
                },
                "🎯 Promo Cards (Top tier)": {
                    "buy": "Buy at pack weight peak",
                    "why": "Limited supply after promo",
                    "risk": "🔴 High Risk",
                    "time": "2-4 weeks"
                },
            }

        # Add investments to embed
        for name, details in investments.items():
            value = f"**Buy Price:** {details['buy']}\n**Why:** {details['why']}\n**Risk:** {details['risk']}\n**Hold Time:** {details['time']}"
            embed.add_field(name=name, value=value, inline=False)

        # General advice
        advice = """
        ⚠️ **Investment Rules:**
        • Never invest more than you can afford to lose
        • Diversify across multiple cards
        • Always check supply/demand
        • Buy during rewards, sell during hype
        • Set price targets and stick to them
        • Monitor content leaks and announcements
        """
        embed.add_field(name="📚 Golden Rules", value=advice, inline=False)

        embed.set_footer(text="FC26 • Investment Guide • Not financial advice - trade at your own risk")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="marketcalendar", description="📅 FC26 content calendar and key dates")
    async def marketcalendar(self, interaction: discord.Interaction):
        """Show FC26 content calendar"""
        embed = discord.Embed(
            title="📅 FC26 Content Calendar",
            description="Key dates and content releases",
            color=discord.Color.purple()
        )

        # Weekly schedule
        weekly = """
        **🔄 Weekly Schedule:**
        • **Monday:** Objectives refresh
        • **Tuesday:** SBC releases (Marquee Matchups)
        • **Wednesday:** TOTW reveal
        • **Thursday:** Rivals rewards + new TOTW
        • **Friday:** Weekend League starts
        • **Sunday:** Weekend League rewards
        """
        embed.add_field(name="📆 Weekly Routine", value=weekly, inline=False)

        # Monthly promos (typical FC cycle)
        promos = """
        **🎉 Annual Promo Schedule:**
        • **Sept:** Early Access / OTW
        • **Oct:** Rulebreakers / Scream
        • **Nov:** Black Friday / Icon SBC
        • **Dec:** Freeze / FUTMAS
        • **Jan:** TOTY
        • **Feb:** Future Stars / FUT Birthday
        • **Mar:** Shapeshifters / FUT Birthday
        • **Apr:** FUT Captains
        • **May:** TOTS (Team of the Season)
        • **June:** Summer Stars / Festival of FUTball
        • **July:** Batch releases
        • **Aug:** End of cycle content
        """
        embed.add_field(name="🎊 Major Promos", value=promos, inline=False)

        # Trading tips per day
        daily_tips = """
        **💡 Daily Trading Tips:**
        • **Mon-Wed:** Mass bid on cards
        • **Thursday AM:** Buy meta cards (rewards crash)
        • **Thursday PM:** Prices stabilize
        • **Friday:** Sell meta cards (WL hype)
        • **Weekend:** Flip special cards
        • **Sunday PM:** Buy for next week
        """
        embed.add_field(name="📈 Trading Schedule", value=daily_tips, inline=False)

        embed.set_footer(text="FC26 • Content Calendar • Subject to EA changes")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="foddercheck", description="📊 Check current fodder prices")
    async def foddercheck(self, interaction: discord.Interaction):
        """Show current fodder pricing guide"""
        await interaction.response.defer()

        embed = discord.Embed(
            title="📊 FC26 Fodder Price Guide",
            description="Approximate market rates for SBC fodder",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        # Typical fodder prices (these are estimates - real bot would fetch from API)
        fodder_guide = {
            "83 Rated": {"buy": "~1,000", "sell": "~1,500-2,000"},
            "84 Rated": {"buy": "~1,500-2,000", "sell": "~2,500-3,500"},
            "85 Rated": {"buy": "~3,000-4,000", "sell": "~5,000-7,000"},
            "86 Rated": {"buy": "~6,000-8,000", "sell": "~10,000-15,000"},
            "87 Rated": {"buy": "~12,000-15,000", "sell": "~20,000-30,000"},
            "88 Rated": {"buy": "~25,000-35,000", "sell": "~45,000-60,000"},
            "89 Rated": {"buy": "~50,000-70,000", "sell": "~90,000-120,000"},
        }

        for rating, prices in fodder_guide.items():
            embed.add_field(
                name=f"⭐ {rating}",
                value=f"Buy: {prices['buy']}\nSell: {prices['sell']}",
                inline=True
            )

        tips = """
        **📝 Fodder Trading Tips:**
        • Buy on Thursday during rewards
        • Sell before major Icon/Player SBCs
        • 83-84s are safest investments
        • 85+ needed for high-rated SBCs
        • Hold during promos, sell during SBC hype
        • Duplicate untradeables = demand spike
        """
        embed.add_field(name="💡 Trading Strategy", value=tips, inline=False)

        embed.set_footer(text="FC26 • Fodder Guide • Prices vary by supply/demand")

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MarketAnalysis(bot))
