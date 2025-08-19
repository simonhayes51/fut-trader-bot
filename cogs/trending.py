import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import requests
import asyncio
import json
import os

CONFIG_FILE = "autotrend_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.auto_post_trends.start()

    def get_trending_players(self, trend_type: str, rarity: str):
        sort = "trend_desc" if trend_type == "riser" else "trend_asc"
        url = f"https://www.fut.gg/api/fc/players/?sort={sort}&platform=ps"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        data = response.json()

        # DEBUG: Log sample player
        if "players" in data and data["players"]:
            print("[DEBUG] Sample player object:")
            print(json.dumps(data["players"][0], indent=2))
        else:
            print("[DEBUG] No players key or empty list in response")

        players = []
        for player in data.get("players", []):
            # Temporarily disable rarity filtering for debugging
            # if rarity != "all" and player.get("rarity", "").lower() != rarity:
            #     continue
            players.append({
                "name": player.get("name"),
                "rating": player.get("rating"),
                "price": player.get("price"),
                "trend": player.get("priceTrend"),
                "club": player.get("clubName"),
                "position": player.get("position")
            })
            if len(players) >= 10:
                break
        return players

    @app_commands.command(name="trending", description="\ud83d\udcca Show top trending players on console")
    @app_commands.choices(
        trend_type=[
            app_commands.Choice(name="\ud83d\udcc8 Risers", value="riser"),
            app_commands.Choice(name="\ud83d\udcc9 Fallers", value="faller")
        ],
        rarity=[
            app_commands.Choice(name="\ud83c\udf10 All", value="all"),
            app_commands.Choice(name="\ud83d\udd2b Bronze", value="bronze"),
            app_commands.Choice(name="\u26aa Silver", value="silver"),
            app_commands.Choice(name="\ud83d\udfe1 Gold", value="gold"),
            app_commands.Choice(name="\ud83d\udd23 Special", value="special")
        ]
    )
    async def trending(
        self,
        interaction: discord.Interaction,
        trend_type: app_commands.Choice[str],
        rarity: app_commands.Choice[str]
    ):
        await interaction.response.defer()
        players = self.get_trending_players(trend_type.value, rarity.value)

        emoji = "\ud83d\udcc8" if trend_type.value == "riser" else "\ud83d\udcc9"
        embed = discord.Embed(
            title=f"{emoji} Top 10 {trend_type.name} ({rarity.name} \u2013 \ud83c\udfae Console)",
            color=discord.Color.green() if trend_type.value == "riser" else discord.Color.red()
        )

        if not players:
            embed.description = "No players found for this filter."
        else:
            for player in players:
                embed.add_field(
                    name=f"{player['name']} ({player['rating']})",
                    value=(
                        f"{emoji} `{player['trend']}%`\n"
                        f"\ud83d\udcb0 `{player['price']:,} coins`\n"
                        f"\ud83e\udeed {player['position']} \u2013 {player['club']}"
                    ),
                    inline=False
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setupautotrending", description="\ud83d\udee0\ufe0f Set daily auto-post channel and time (HH:MM)")
    @app_commands.describe(channel="Channel to send posts in", post_time="Time in 24h format (e.g. 09:00)")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, post_time: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("\u274c You need 'Manage Server' permission to use this.", ephemeral=True)
            return

        # Validate time format
        try:
            datetime.strptime(post_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("\u274c Invalid time format. Use HH:MM (24-hour)", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = {
            "channel_id": channel.id,
            "time": post_time
        }
        save_config(self.config)
        await interaction.response.send_message(f"\u2705 Auto-trending set to post daily at **{post_time}** in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().strftime("%H:%M")
        for guild_id, settings in self.config.items():
            if settings.get("time") != now:
                continue

            channel = self.bot.get_channel(settings["channel_id"])
            if not channel:
                continue

            for trend_type in ["riser", "faller"]:
                players = self.get_trending_players(trend_type, "all")
                emoji = "\ud83d\udcc8" if trend_type == "riser" else "\ud83d\udcc9"
                embed = discord.Embed(
                    title=f"{emoji} Daily Top 10 {trend_type.title()}s (\ud83c\udfae Console)",
                    color=discord.Color.green() if trend_type == "riser" else discord.Color.red(),
                    timestamp=datetime.utcnow()
                )

                if not players:
                    embed.description = "No trending players found."
                else:
                    for player in players:
                        embed.add_field(
                            name=f"{player['name']} ({player['rating']})",
                            value=(
                                f"{emoji} `{player['trend']}%`\n"
                                f"\ud83d\udcb0 `{player['price']:,} coins`\n"
                                f"\ud83e\udeed {player['position']} \u2013 {player['club']}"
                            ),
                            inline=False
                        )

                try:
                    await channel.send(embed=embed)
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"Error posting to {channel.id}: {e}")

    @auto_post_trends.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Trending(bot))
