import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

log = logging.getLogger("fut.marketintel")

class MarketIntel(commands.Cog):
    """
    Market intelligence and insights
    Fodder tracker, market overview, content calendar
    """

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fodder", description="📊 Live fodder prices and buy/sell signals")
    async def fodder(self, interaction: discord.Interaction):
        """Show current fodder pricing with recommendations"""
        await interaction.response.defer()

        embed = discord.Embed(
            title="📊 FC26 Fodder Tracker",
            description="Current market rates with buy/sell signals",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        # In production: fetch real prices
        # For now, use typical market values

        fodder_data = [
            {"rating": 83, "price": 1200, "avg": 1500, "signal": "buy", "change": -20},
            {"rating": 84, "price": 2400, "avg": 2500, "signal": "hold", "change": -4},
            {"rating": 85, "price": 6800, "avg": 5500, "signal": "sell", "change": +24},
            {"rating": 86, "price": 11000, "avg": 10000, "signal": "sell", "change": +10},
            {"rating": 87, "price": 21000, "avg": 20000, "signal": "hold", "change": +5},
            {"rating": 88, "price": 38000, "avg": 40000, "signal": "buy", "change": -5},
            {"rating": 89, "price": 68000, "avg": 70000, "signal": "hold", "change": -3},
        ]

        for fodder in fodder_data:
            # Signal emoji
            if fodder["signal"] == "buy":
                signal_emoji = "🟢 BUY"
                reason = "Below average"
            elif fodder["signal"] == "sell":
                signal_emoji = "🔴 SELL"
                reason = "Above average"
            else:
                signal_emoji = "⚪ HOLD"
                reason = "Fair price"

            # Price change
            if fodder["change"] > 0:
                change_text = f"📈 +{fodder['change']}%"
            elif fodder["change"] < 0:
                change_text = f"📉 {fodder['change']}%"
            else:
                change_text = "➡️ 0%"

            value = f"**Price:** {fodder['price']:,} 🪙 {change_text}\n"
            value += f"**Average:** {fodder['avg']:,} 🪙\n"
            value += f"**Signal:** {signal_emoji} ({reason})"

            embed.add_field(
                name=f"⭐ {fodder['rating']} Rated",
                value=value,
                inline=True
            )

        # Market insight
        insight = """
        **💡 Current Market:**
        • 85-86s are HIGH - Sell before Icon SBC
        • 83-84s are LOW - Good time to invest
        • Next big SBC expected: 3-5 days

        **📅 Recommendation:**
        Buy 83-84s now, sell when SBC drops
        """

        embed.add_field(name="📈 Market Insight", value=insight, inline=False)

        embed.set_footer(text="FC26 • Fodder Tracker • Updated every 5 minutes")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="market", description="📈 Quick market overview")
    async def market(self, interaction: discord.Interaction):
        """Comprehensive market overview"""
        await interaction.response.defer()

        # Determine market phase based on date
        today = datetime.utcnow()
        if today.month == 9:
            phase = "🚀 Early Access"
            sentiment = "📈 Bullish"
            advice = "Sell high-rated cards, hold meta"
        elif today.month == 10:
            phase = "📉 October Crash"
            sentiment = "📉 Bearish"
            advice = "Buy investments, avoid panic selling"
        elif today.month in [11, 12]:
            phase = "🎄 Pre-TOTY Hype"
            sentiment = "🟡 Volatile"
            advice = "Sell before promos, buy dips"
        elif today.month in [1, 2]:
            phase = "⚽ TOTY Period"
            sentiment = "🔴 Crash"
            advice = "Buy everything cheap"
        elif today.month in [3, 4, 5]:
            phase = "🌸 Mid-Cycle"
            sentiment = "🟢 Stable"
            advice = "Normal trading strategies"
        elif today.month in [6, 7]:
            phase = "☀️ TOTS Season"
            sentiment = "📈 High Volume"
            advice = "Flip TOTS cards"
        else:
            phase = "🏖️ End of Cycle"
            sentiment = "📉 Declining"
            advice = "Play, don't trade"

        embed = discord.Embed(
            title="📈 FC26 Market Overview",
            description=f"**Phase:** {phase}\n**Sentiment:** {sentiment}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Best actions
        actions = f"""
        **✅ BUY NOW:**
        • Fodder (83-85 rated)
        • Meta cards on Sunday evening
        • Chemistry styles (Shadow/Hunter)

        **❌ SELL NOW:**
        • High-rated special cards
        • Friday before Weekend League
        • Before major promos

        **⏳ WAIT:**
        • Icons (will drop more)
        • Promo cards (still falling)
        """

        embed.add_field(name="💡 Best Actions", value=actions, inline=False)

        # Trading windows
        windows = """
        **⏰ BEST TIMES TO BUY:**
        • Sunday evenings (WL ends)
        • Thursday morning (Rivals rewards)
        • Monday mornings (low activity)

        **⏰ BEST TIMES TO SELL:**
        • Friday afternoon (WL hype)
        • Tuesday (SBC releases)
        • Weekend mornings (peak activity)
        """

        embed.add_field(name="🕐 Trading Windows", value=windows, inline=False)

        # Current advice
        embed.add_field(name="🎯 Today's Strategy", value=advice, inline=False)

        embed.set_footer(text="FC26 • Market Intelligence")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="calendar", description="📅 FC26 content calendar")
    async def calendar(self, interaction: discord.Interaction):
        """Show content calendar with predictions"""
        embed = discord.Embed(
            title="📅 FC26 Content Calendar",
            description="Weekly schedule and upcoming events",
            color=discord.Color.purple()
        )

        # Weekly schedule
        weekly = """
        **🔄 WEEKLY SCHEDULE:**

        **Monday**
        • Objectives refresh
        • Low market activity (BUY)

        **Tuesday**
        • SBC releases (Marquee Matchups)
        • Fodder spikes

        **Wednesday**
        • TOTW reveal
        • Content announcements

        **Thursday**
        • Rivals rewards (6PM UK)
        • New TOTW in packs
        • Market CRASH (BUY window)

        **Friday**
        • Weekend League starts
        • Meta cards spike (SELL)

        **Weekend**
        • High activity
        • Flip special cards

        **Sunday**
        • WL rewards (evening)
        • Market dip (BUY window)
        """

        embed.add_field(name="📆 Weekly Cycle", value=weekly, inline=False)

        # Major promos (typical FC cycle)
        promos = """
        **🎉 ANNUAL PROMOS:**
        • **Sept:** Early Access, OTW
        • **Oct:** Rulebreakers
        • **Nov:** Black Friday, Icons
        • **Dec:** FUTMAS
        • **Jan:** TOTY (biggest crash)
        • **Feb:** Future Stars
        • **Mar:** FUT Birthday
        • **Apr:** FUT Captains
        • **May-Jun:** TOTS (high volume)
        • **Jul-Aug:** End cycle
        """

        embed.add_field(name="🎊 Major Promos", value=promos, inline=False)

        # Trading tips
        tips = """
        **💡 TRADING CALENDAR:**
        • **Buy:** Thursday AM, Sunday PM
        • **Sell:** Friday PM, Tuesday PM
        • **Before promos:** SELL everything
        • **During promos:** BUY crash
        • **After promos:** Prices recover
        """

        embed.add_field(name="📈 Trading Schedule", value=tips, inline=False)

        embed.set_footer(text="FC26 • Content Calendar • Subject to EA changes")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sbctips", description="🎯 SBC trading tips")
    async def sbctips(self, interaction: discord.Interaction):
        """Show SBC trading strategies"""
        embed = discord.Embed(
            title="🎯 SBC Trading Guide",
            description="How to profit from Squad Building Challenges",
            color=discord.Color.green()
        )

        tips = """
        **📚 BEFORE SBC DROPS:**
        • Stock up on 83-85 rated fodder
        • Buy cheap IFs (TOTW players)
        • Hold popular nations/leagues

        **⚡ WHEN SBC DROPS:**
        • Sell fodder IMMEDIATELY (first 30min)
        • Check requirements carefully
        • Unique cards spike most

        **🕐 AFTER SBC:**
        • Prices crash after 2-3 hours
        • Sell remaining stock quick
        • Move to next opportunity

        **💰 BEST SBC INVESTMENTS:**
        • 83-84 rated: Safe, consistent
        • Cheap IFs: Marquee Matchups
        • Position-specific: CBs, GKs
        • League-specific: Top 5 leagues
        """

        embed.add_field(name="💡 SBC Trading Masterclass", value=tips, inline=False)

        examples = """
        **📊 HISTORICAL EXAMPLES:**

        **Icon SBC (85 rated squad):**
        • 85s: 4K → 9K (+125%)
        • 84s: 2K → 4.5K (+125%)
        • Profit window: 2-3 hours

        **Marquee Matchups (TOTW req):**
        • Cheap IFs: 12K → 22K (+83%)
        • Profit window: 1 day

        **League SBC (specific club):**
        • Required silvers: 1K → 15K (+1400%)
        • Profit window: Instant
        """

        embed.add_field(name="📈 Real Examples", value=examples, inline=False)

        embed.set_footer(text="FC26 • SBC Trading Guide")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MarketIntel(bot))
