import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path

TRACKING_FILE = Path("trade_tip_tracking.json")
TRACKING_ACTIONS = {
    "bought": "Bought",
    "watching": "Watching",
    "passed": "Passed",
    "sold": "Sold",
}

class PostATrade(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tree = bot.tree  # Hook into the bot's command tree

    def _load_tracking(self):
        if not TRACKING_FILE.exists():
            return {}
        try:
            return json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_tracking(self, data):
        TRACKING_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _new_tip_id(self, interaction: discord.Interaction):
        return f"{interaction.guild_id}-{interaction.user.id}-{int(interaction.created_at.timestamp())}"

    def _tracking_view(self, tip_id: str):
        view = discord.ui.View(timeout=None)
        buttons = [
            ("bought", "I bought this", discord.ButtonStyle.success),
            ("watching", "Watching", discord.ButtonStyle.primary),
            ("passed", "Passed", discord.ButtonStyle.secondary),
            ("sold", "Sold", discord.ButtonStyle.danger),
            ("view", "View trackers", discord.ButtonStyle.secondary),
        ]
        for action, label, style in buttons:
            view.add_item(discord.ui.Button(label=label, style=style, custom_id=f"trade_tip:{action}:{tip_id}"))
        return view

    def _tracker_summary(self, record):
        trackers = record.get("trackers", {})
        counts = []
        for key, label in TRACKING_ACTIONS.items():
            counts.append(f"**{label}:** {len(trackers.get(key, []))}")
        return " | ".join(counts)

    def _tracker_details(self, record):
        trackers = record.get("trackers", {})
        lines = []
        for key, label in TRACKING_ACTIONS.items():
            users = trackers.get(key, [])
            mentions = ", ".join(f"<@{user_id}>" for user_id in users[:25])
            extra = f" (+{len(users) - 25} more)" if len(users) > 25 else ""
            lines.append(f"**{label} ({len(users)})**\n{mentions or 'Nobody yet.'}{extra}")
        return "\n\n".join(lines)

    async def _refresh_tip_message(self, interaction: discord.Interaction, tip_id: str, record):
        channel_id = record.get("channel_id")
        message_id = record.get("message_id")
        if not channel_id or not message_id:
            return
        channel = interaction.guild.get_channel(int(channel_id)) if interaction.guild else None
        if not channel:
            return
        try:
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        if not message.embeds:
            return
        embed = message.embeds[0].copy()
        fields = [field for field in embed.fields if field.name != "📊 Tracking"]
        embed.clear_fields()
        for field in fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)
        embed.add_field(name="📊 Tracking", value=self._tracker_summary(record), inline=False)
        await message.edit(embed=embed, view=self._tracking_view(tip_id))

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id", "") if interaction.data else ""
        if not custom_id.startswith("trade_tip:"):
            return

        _, action, tip_id = custom_id.split(":", 2)
        data = self._load_tracking()
        record = data.get(tip_id)
        if not record:
            await interaction.response.send_message("I can't find tracking for this trade tip any more.", ephemeral=True)
            return

        if action == "view":
            is_owner = str(interaction.user.id) == str(record.get("author_id"))
            can_manage = interaction.user.guild_permissions.manage_messages if interaction.guild else False
            if not is_owner and not can_manage:
                await interaction.response.send_message(self._tracker_summary(record), ephemeral=True)
                return
            embed = discord.Embed(
                title=f"Trade trackers: {record.get('player', 'Trade tip')}",
                description=self._tracker_details(record),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if action not in TRACKING_ACTIONS:
            return

        trackers = record.setdefault("trackers", {key: [] for key in TRACKING_ACTIONS})
        user_id = str(interaction.user.id)
        for users in trackers.values():
            if user_id in users:
                users.remove(user_id)
        trackers.setdefault(action, []).append(user_id)
        data[tip_id] = record
        self._save_tracking(data)
        await self._refresh_tip_message(interaction, tip_id, record)
        await interaction.response.send_message(f"Logged you as **{TRACKING_ACTIONS[action]}** for this trade.", ephemeral=True)

    @app_commands.command(name="postatrade", description="📬 Post a trade tip to the server!")
    @app_commands.describe(
        name="Player name",
        version="Card version (e.g. Gold Rare, TOTW, TOTS)",
        buy_price="Buy price in coins",
        sell_time="When to sell (e.g. in 2 days, post SBC, etc)",
        platform="Platform used",
        reason="Optional tip or reasoning behind the trade",
        image="Optional image of the deal (e.g. screenshot)"
    )
    @app_commands.choices(
        platform=[
            app_commands.Choice(name="🎮 Console", value="Console"),
            app_commands.Choice(name="💻 PC", value="PC")
        ]
    )
    async def postatrade(
        self,
        interaction: discord.Interaction,
        name: str,
        version: str,
        buy_price: int,
        sell_time: str,
        platform: app_commands.Choice[str],
        reason: str = None,
        image: discord.Attachment = None
    ):
        tip_id = self._new_tip_id(interaction)
        embed = discord.Embed(
            title="📢 New Trade Tip Submitted!",
            description=f"Submitted by {interaction.user.mention}",
            color=discord.Color.blue()
        )

        embed.add_field(name="👤 Name", value=name, inline=True)
        embed.add_field(name="✨ Version", value=version, inline=True)
        embed.add_field(name="💰 Buy Price", value=f"{buy_price:,} coins", inline=True)
        embed.add_field(name="⏳ Sell Time", value=sell_time, inline=True)
        embed.add_field(name="🕹️ Platform", value=platform.name, inline=True)

        if reason:
            embed.add_field(name="🧠 Tip / Reason", value=reason, inline=False)

        embed.add_field(
            name="📊 Tracking",
            value="**Bought:** 0 | **Watching:** 0 | **Passed:** 0 | **Sold:** 0",
            inline=False
        )

        if image:
            embed.set_image(url=image.url)

        embed.set_footer(text=f"All trades are done at your own risk 📈 | Tip ID: {tip_id}")
        embed.timestamp = interaction.created_at

        await interaction.response.send_message("✅ Trade posted!", ephemeral=True)
        message = await interaction.channel.send(embed=embed, view=self._tracking_view(tip_id))

        data = self._load_tracking()
        data[tip_id] = {
            "guild_id": str(interaction.guild_id),
            "channel_id": str(interaction.channel_id),
            "message_id": str(message.id),
            "author_id": str(interaction.user.id),
            "player": name,
            "version": version,
            "buy_price": buy_price,
            "platform": platform.value,
            "trackers": {key: [] for key in TRACKING_ACTIONS},
        }
        self._save_tracking(data)

# ✅ Correct class reference here
async def setup(bot):
    await bot.add_cog(PostATrade(bot))
