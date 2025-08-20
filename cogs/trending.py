import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import os
import requests
from bs4 import BeautifulSoup

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

def is_admin_or_owner(member: discord.Member) -> bool:
    return member.guild and (member.guild.owner_id == member.id or any(r.name.lower() in ["admin", "owner"] for r in member.roles))

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        print("✅ Trending cog initialized")
        self.auto_post_trends.start()

    @app_commands.command(name="trending", description="📊 Show top trending players")
    @app_commands.describe(
        direction="Choose trend direction",
        period="Choose timeframe"
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="📈 Risers", value="riser"),
            app_commands.Choice(name="📉 Fallers", value="faller")
        ],
        period=[
            app_commands.Choice(name="🗓️ 24 Hour", value="24h"),
            app_commands.Choice(name="🕓 4 Hour", value="4h")
        ]
    )
    async def trending(self, interaction: discord.Interaction, direction: app_commands.Choice[str], period: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await self.generate_embed(direction.value, period.value)
        await interaction.followup.send(embed=embed or "Error\nUnable to fetch market data.")

    @app_commands.command(name="setupautotrending", description="⚙️ Set up auto-post for trending players")
    @app_commands.describe(channel="Channel to post in", frequency="Frequency (6/12/24 hours)", start_time="Start time (HH:MM)", ping_role="Optional ping role")
    async def setupautotrending(self, interaction: discord.Interaction, channel: discord.TextChannel, frequency: int, start_time: str, ping_role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ You must be an Admin or Server Owner.", ephemeral=True)
            return

        if frequency not in [6, 12, 24]:
            await interaction.response.send_message("❌ Frequency must be 6, 12, or 24.", ephemeral=True)
            return

        try:
            datetime.strptime(start_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use HH:MM (24h)", ephemeral=True)
            return

        self.config[str(channel.id)] = {
            "frequency": frequency,
            "start_time": start_time,
            "ping_role": ping_role.id if ping_role else None
        }
        save_config(self.config)
        await interaction.response.send_message(f"✅ Auto-trending set for every {frequency}h starting at {start_time} in {channel.mention}")

    @tasks.loop(minutes=1)
    async def auto_post_trends(self):
        now = datetime.utcnow().replace(second=0, microsecond=0)
        print(f"[LOOP] Tick at {now.strftime('%H:%M')} UTC")

        for channel_id, settings in self.config.items():
            try:
                frequency = int(settings["frequency"])
                start = datetime.strptime(settings["start_time"], "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )

                # Shift back until within correct window
                while start > now:
                    start -= timedelta(hours=frequency)
                while start + timedelta(hours=frequency) <= now:
                    start += timedelta(hours=frequency)

                if now != start:
                    continue  # Not yet time to post

                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    print(f"[WARN] Channel {channel_id} not found")
                    continue

                embed = await self.generate_combined_embed("24h")
                if not embed:
                    print(f"[ERROR] Could not generate embed")
                    continue

                ping = settings.get("ping_role")
                content = f"<@&{ping}>" if ping else None
                await channel.send(content=content, embed=embed)
                print(f"[POSTED] Sent market trends to {channel.name} ({channel_id})")

            except Exception as e:
                print(f"[ERROR] Autopost error for channel {channel_id}: {e}")

    @auto_post_trends.before_loop
    async def before_auto(self):
        print("⏳ Waiting for bot to be ready...")
        await self.bot.wait_until_ready()
        print("✅ Auto-post loop ready")

    async def generate_embed(self, direction, period) -> discord.Embed:
        data = self.scrape_futbin_data(direction, period)
        if not data:
            return None

        emoji = "📈" if direction == "riser" else "📉"
        color = discord.Color.green() if direction == "riser" else discord.Color.red()
        title = f"{emoji} Top 10 {'Risers' if direction == 'riser' else 'Fallers'} (🎮 Console) – {period}"
        embed = discord.Embed(title=title, color=color)
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, p in enumerate(data[:10]):
            boost = ""
            if direction == "riser" and p["trend"] > 100:
                boost = " 🚀"
            elif direction == "faller" and p["trend"] < -50:
                boost = " ❄️"

            trend = f"-{p['trend']:.2f}%" if direction == "faller" else f"{p['trend']:.2f}%"
            embed.add_field(
                name=f"{number_emojis[i]} {p['name']} ({p['rating']})",
                value=f"💰 {p['price']}\n{emoji} {trend}{boost}",
                inline=False
            )

        return embed

    async def generate_combined_embed(self, period) -> discord.Embed:
        risers = self.scrape_futbin_data("riser", period)
        fallers = self.scrape_futbin_data("faller", period)
        if not risers or not fallers:
            return None

        embed = discord.Embed(title=f"📊 Top 10 Market Movers (🎮 Console) – {period}", color=discord.Color.gold())
        embed.set_footer(text="Data from FUTBIN | Prices are estimates")

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        left = ""
        right = ""

        for i in range(10):
            r = risers[i]
            f = fallers[i]

            boost = " 🚀" if r["trend"] > 100 else ""
            drop = " ❄️" if f["trend"] < -50 else ""

            left += f"**{number_emojis[i]} {r['name']} ({r['rating']})**\n💰 {r['price']}\n📈 {r['trend']:.2f}%{boost}\n\n"
            right += f"**{number_emojis[i]} {f['name']} ({f['rating']})**\n💰 {f['price']}\n📉 -{f['trend']:.2f}%{drop}\n\n"

        embed.add_field(name="📈 Risers", value=left.strip(), inline=True)
        embed.add_field(name="📉 Fallers", value=right.strip(), inline=True)
        return embed

    def scrape_futbin_data(self, direction, period):
        url = "https://www.futbin.com/market"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        wrapper_class = "market-24-hours" if period == "24h" else "market-4-hours"
        wrapper = soup.select_one(f"div.market-players-wrapper.{wrapper_class}.m-row.space-between")
        if not wrapper:
            print(f"[SCRAPE] No wrapper found for {wrapper_class}")
            return []

        cards = wrapper.select("a.market-player-card")
        players = []

        for card in cards:
            trend_tag = card.select_one(".market-player-change")
            if not trend_tag or "%" not in trend_tag.text:
                continue

            try:
                trend = float(trend_tag.text.replace("%", "").replace("+", "").replace(",", ""))
            except:
                continue

            if direction == "riser" and trend <= 0:
                continue
            if direction == "faller" and trend >= 0:
                continue

            name = card.select_one(".playercard-s-25-name")
            rating = card.select_one(".playercard-s-25-rating")
            price = card.select_one(".platform-price-wrapper-small")

            if not (name and rating and price):
                continue

            players.append({
                "name": name.text.strip(),
                "rating": rating.text.strip(),
                "price": price.text.strip(),
                "trend": trend
            })

        return sorted(players, key=lambda x: x["trend"], reverse=(direction == "riser"))[:10]

# ✅ Register cog
async def setup(bot):
    print("📦 Registering Trending cog")
    await bot.add_cog(Trending(bot))