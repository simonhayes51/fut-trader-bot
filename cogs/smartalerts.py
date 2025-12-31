import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncpg
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("fut.smartalerts")

DATABASE_URL = os.getenv("DATABASE_URL")

class SmartAlerts(commands.Cog):
    """
    Personal price alerts system
    Users get DM'd when their watched cards hit target prices
    """

    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.db: Optional[asyncpg.Pool] = None

        # In-memory cache of alerts (loaded from DB)
        self.alerts: Dict[int, List[Dict]] = {}  # user_id -> [alert1, alert2, ...]

        # Premium limits
        self.free_alert_limit = 5
        self.premium_alert_limit = 999  # Unlimited

    async def cog_load(self):
        """Initialize resources"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not self.db and DATABASE_URL:
            self.db = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=4)
            await self._init_database()
            await self._load_alerts()

        self.check_alerts.start()

    def cog_unload(self):
        """Clean up resources"""
        self.check_alerts.cancel()
        if self.session:
            self.bot.loop.create_task(self.session.close())
        if self.db:
            self.bot.loop.create_task(self.db.close())

    async def _init_database(self):
        """Create alerts table if it doesn't exist"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    player_name TEXT NOT NULL,
                    card_id TEXT,
                    condition TEXT NOT NULL,  -- '<', '>', '<=', '>='
                    target_price INTEGER NOT NULL,
                    current_price INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_checked TIMESTAMP,
                    triggered BOOLEAN DEFAULT FALSE,
                    premium BOOLEAN DEFAULT FALSE
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_alerts ON price_alerts(user_id, triggered)
            """)
        log.info("[SmartAlerts] Database initialized")

    async def _load_alerts(self):
        """Load all active alerts from database"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM price_alerts
                WHERE triggered = FALSE
                ORDER BY user_id, created_at
            """)

        self.alerts = {}
        for row in rows:
            user_id = row["user_id"]
            if user_id not in self.alerts:
                self.alerts[user_id] = []

            self.alerts[user_id].append({
                "id": row["id"],
                "player_name": row["player_name"],
                "card_id": row["card_id"],
                "condition": row["condition"],
                "target_price": row["target_price"],
                "current_price": row["current_price"],
                "created_at": row["created_at"],
                "premium": row["premium"],
            })

        log.info(f"[SmartAlerts] Loaded {sum(len(a) for a in self.alerts.values())} active alerts for {len(self.alerts)} users")

    @tasks.loop(minutes=5)  # Check every 5 minutes
    async def check_alerts(self):
        """Check all alerts and notify users"""
        try:
            for user_id, user_alerts in self.alerts.items():
                for alert in user_alerts:
                    await self._check_single_alert(user_id, alert)
        except Exception as e:
            log.error(f"[SmartAlerts] Error checking alerts: {e}")

    @check_alerts.before_loop
    async def before_check_alerts(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()

    async def _check_single_alert(self, user_id: int, alert: Dict):
        """Check a single alert and notify if triggered"""
        # Fetch REAL price from Futbin if we have a card_id
        current_price = None

        if alert["card_id"]:
            try:
                from utils.futbin_api import _futbin_api
                prices = await _futbin_api.get_player_price_async(self.session, int(alert["card_id"]))

                if prices:
                    ps_data = prices.get("ps", {})
                    xbox_data = prices.get("xbox", {})

                    # Parse prices
                    def parse_price(price_str):
                        try:
                            return int(str(price_str).replace(',', ''))
                        except:
                            return None

                    ps_price = parse_price(ps_data.get("LCPrice"))
                    xbox_price = parse_price(xbox_data.get("LCPrice"))

                    # Use average of both platforms
                    if ps_price and xbox_price:
                        current_price = (ps_price + xbox_price) // 2
                    elif ps_price:
                        current_price = ps_price
                    elif xbox_price:
                        current_price = xbox_price

            except Exception as e:
                log.error(f"[SmartAlerts] Error fetching price for alert {alert['id']}: {e}")

        # If we couldn't get a real price, skip this check
        if not current_price:
            return

        # Update current price in memory
        alert["current_price"] = current_price

        # Check condition
        condition = alert["condition"]
        target = alert["target_price"]
        triggered = False

        if condition == "<" and current_price < target:
            triggered = True
        elif condition == ">" and current_price > target:
            triggered = True
        elif condition == "<=" and current_price <= target:
            triggered = True
        elif condition == ">=" and current_price >= target:
            triggered = True

        if triggered:
            await self._send_alert_notification(user_id, alert, current_price)
            await self._mark_alert_triggered(alert["id"])

            # Remove from memory
            self.alerts[user_id] = [a for a in self.alerts[user_id] if a["id"] != alert["id"]]
            if not self.alerts[user_id]:
                del self.alerts[user_id]

    async def _send_alert_notification(self, user_id: int, alert: Dict, current_price: int):
        """Send DM to user when alert triggers"""
        try:
            user = await self.bot.fetch_user(user_id)
            if not user:
                return

            # Create embed
            embed = discord.Embed(
                title="🔔 Price Alert Triggered!",
                description=f"**{alert['player_name']}** has reached your target price!",
                color=discord.Color.green() if alert["condition"] in ["<", "<="] else discord.Color.red(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="🎯 Target",
                value=f"{alert['condition']} {alert['target_price']:,} 🪙",
                inline=True
            )
            embed.add_field(
                name="💰 Current Price",
                value=f"**{current_price:,}** 🪙",
                inline=True
            )

            # Action suggestion
            if alert["condition"] in ["<", "<="]:
                action = "🟢 **BUY NOW** - Price dropped to your target!"
            else:
                action = "🔴 **SELL NOW** - Price reached your target!"

            embed.add_field(name="💡 Recommendation", value=action, inline=False)

            embed.set_footer(text="FC26 • Smart Alerts • Act fast before the market changes!")

            await user.send(embed=embed)
            log.info(f"[SmartAlerts] Sent alert to user {user_id} for {alert['player_name']}")

        except discord.Forbidden:
            log.warning(f"[SmartAlerts] Cannot DM user {user_id} (DMs disabled)")
        except Exception as e:
            log.error(f"[SmartAlerts] Failed to send alert to {user_id}: {e}")

    async def _mark_alert_triggered(self, alert_id: int):
        """Mark alert as triggered in database"""
        if not self.db:
            return

        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE price_alerts
                SET triggered = TRUE, last_checked = NOW()
                WHERE id = $1
            """, alert_id)

    def _get_user_alert_count(self, user_id: int) -> int:
        """Get number of active alerts for user"""
        return len(self.alerts.get(user_id, []))

    def _is_premium_user(self, user_id: int) -> bool:
        """Check if user has premium (placeholder)"""
        # In production: check database or premium role
        return False

    # ===== COMMANDS =====

    @app_commands.command(name="alert", description="🔔 Set a price alert for a player")
    @app_commands.describe(
        player="Player name (e.g. 'Mbappe' or 'Mbappe 95')",
        condition="Condition (< or >)",
        price="Target price in coins"
    )
    @app_commands.choices(condition=[
        app_commands.Choice(name="Below (<)", value="<"),
        app_commands.Choice(name="Above (>)", value=">"),
    ])
    async def alert(self, interaction: discord.Interaction, player: str, condition: app_commands.Choice[str], price: int):
        """Set a new price alert"""
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id

        # Check alert limit
        current_count = self._get_user_alert_count(user_id)
        is_premium = self._is_premium_user(user_id)
        limit = self.premium_alert_limit if is_premium else self.free_alert_limit

        if current_count >= limit:
            embed = discord.Embed(
                title="❌ Alert Limit Reached",
                description=f"You have {current_count}/{limit} alerts active.",
                color=discord.Color.red()
            )
            if not is_premium:
                embed.add_field(
                    name="💎 Get Premium",
                    value="Upgrade to Premium for unlimited alerts!",
                    inline=False
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Try to resolve player name to card_id from player database
        card_id = None
        if self.db:
            try:
                async with self.db.acquire() as conn:
                    # Try to find player in fut_players table
                    player_row = await conn.fetchrow("""
                        SELECT card_id FROM public.fut_players
                        WHERE LOWER(name) LIKE LOWER($1)
                        ORDER BY rating DESC
                        LIMIT 1
                    """, f"%{player}%")

                    if player_row and player_row["card_id"]:
                        card_id = str(player_row["card_id"])
                        log.info(f"[SmartAlerts] Resolved '{player}' to card_id: {card_id}")
            except Exception as e:
                log.warning(f"[SmartAlerts] Could not resolve player name: {e}")

        # Create alert in database
        if self.db:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow("""
                    INSERT INTO price_alerts (user_id, player_name, card_id, condition, target_price, premium)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """, user_id, player, card_id, condition.value, price, is_premium)

                alert_id = row["id"]
        else:
            alert_id = len(self.alerts.get(user_id, [])) + 1

        # Add to memory
        if user_id not in self.alerts:
            self.alerts[user_id] = []

        self.alerts[user_id].append({
            "id": alert_id,
            "player_name": player,
            "card_id": card_id,  # Use resolved card_id
            "condition": condition.value,
            "target_price": price,
            "current_price": None,
            "created_at": datetime.utcnow(),
            "premium": is_premium,
        })

        embed = discord.Embed(
            title="✅ Alert Created",
            description=f"You'll be notified when **{player}** price goes {condition.name.lower()}:",
            color=discord.Color.green()
        )

        embed.add_field(name="🎯 Target", value=f"{condition.value} {price:,} 🪙", inline=True)
        embed.add_field(name="📊 Active Alerts", value=f"{current_count + 1}/{limit}", inline=True)

        embed.set_footer(text="You'll receive a DM when this alert triggers!")

        await interaction.followup.send(embed=embed, ephemeral=True)
        log.info(f"[SmartAlerts] User {user_id} created alert for {player} {condition.value} {price}")

    @app_commands.command(name="myalerts", description="📋 View your active price alerts")
    async def myalerts(self, interaction: discord.Interaction):
        """List user's active alerts"""
        user_id = interaction.user.id
        user_alerts = self.alerts.get(user_id, [])

        if not user_alerts:
            embed = discord.Embed(
                title="📋 Your Price Alerts",
                description="You don't have any active alerts.\n\nUse `/alert` to create one!",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        is_premium = self._is_premium_user(user_id)
        limit = self.premium_alert_limit if is_premium else self.free_alert_limit

        embed = discord.Embed(
            title="📋 Your Price Alerts",
            description=f"You have {len(user_alerts)}/{limit} active alerts",
            color=discord.Color.gold()
        )

        for i, alert in enumerate(user_alerts, 1):
            created = alert["created_at"].strftime("%b %d")
            value = f"**Condition:** {alert['condition']} {alert['target_price']:,} 🪙\n"
            value += f"**Created:** {created}\n"
            if alert["current_price"]:
                value += f"**Current:** ~{alert['current_price']:,} 🪙"

            embed.add_field(
                name=f"{i}. {alert['player_name']}",
                value=value,
                inline=False
            )

        embed.set_footer(text="Use /removealert to delete an alert")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="removealert", description="🗑️ Remove a price alert")
    @app_commands.describe(player="Player name (must match exactly)")
    async def removealert(self, interaction: discord.Interaction, player: str):
        """Remove an alert"""
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        user_alerts = self.alerts.get(user_id, [])

        # Find matching alert
        matching_alert = None
        for alert in user_alerts:
            if alert["player_name"].lower() == player.lower():
                matching_alert = alert
                break

        if not matching_alert:
            await interaction.followup.send(f"❌ No alert found for '{player}'", ephemeral=True)
            return

        # Remove from database
        if self.db:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    DELETE FROM price_alerts WHERE id = $1
                """, matching_alert["id"])

        # Remove from memory
        self.alerts[user_id] = [a for a in user_alerts if a["id"] != matching_alert["id"]]
        if not self.alerts[user_id]:
            del self.alerts[user_id]

        embed = discord.Embed(
            title="✅ Alert Removed",
            description=f"Alert for **{player}** has been deleted.",
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)
        log.info(f"[SmartAlerts] User {user_id} removed alert for {player}")

    @app_commands.command(name="clearalerts", description="🗑️ Remove ALL your price alerts")
    async def clearalerts(self, interaction: discord.Interaction):
        """Clear all alerts for user"""
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        count = self._get_user_alert_count(user_id)

        if count == 0:
            await interaction.followup.send("You don't have any alerts to clear.", ephemeral=True)
            return

        # Remove from database
        if self.db:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    DELETE FROM price_alerts WHERE user_id = $1 AND triggered = FALSE
                """, user_id)

        # Remove from memory
        if user_id in self.alerts:
            del self.alerts[user_id]

        embed = discord.Embed(
            title="✅ Alerts Cleared",
            description=f"Removed {count} alert(s).",
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)
        log.info(f"[SmartAlerts] User {user_id} cleared {count} alerts")

async def setup(bot):
    await bot.add_cog(SmartAlerts(bot))
