import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json
import logging
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import io
from datetime import datetime

log = logging.getLogger("fut-pricecheck")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)


class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()

    def load_players(self):
        try:
            with open("players_temp.json", "r", encoding="utf-8") as f:
                players = json.load(f)
                log.info("[LOAD] players_temp.json loaded successfully.")
                return players
        except Exception as e:
            log.error(f"[ERROR] Failed to load players: {e}")
            return []

    def fetch_price_data(self, url):
        """Fetch today's hourly price data from FUTBIN reliably"""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, "html.parser")

            # Grab all graph containers on page
            graph_divs = soup.find_all("div", class_="highcharts-graph-wrapper")
            log.info(f"[DEBUG] Found {len(graph_divs)} graph divs")

            price_data = []

            # ✅ First try: second graph div (usually hourly)
            if len(graph_divs) >= 2:
                hourly_graph = graph_divs[1]
                data_ps_raw = hourly_graph.get("data-ps-data", "[]")
                try:
                    price_data = json.loads(data_ps_raw)
                except json.JSONDecodeError:
                    log.warning("[SCRAPE] Hourly data JSON decode failed.")

            # ✅ Fallback: extract from FUTBIN <script> tags if graph parsing fails
            if not price_data:
                script_tags = soup.find_all("script")
                for script in script_tags:
                    if script.string and "highcharts" in script.string.lower():
                        match = re.search(r'data-ps-data="(\[.*?\])"', script.string)
                        if match:
                            try:
                                price_data = json.loads(match.group(1))
                                break
                            except json.JSONDecodeError:
                                continue

            if not price_data:
                log.warning("[SCRAPE] No hourly price data found for this player.")
                return []

            # Convert timestamps → datetime & keep positive prices only
            filtered = [
                (datetime.fromtimestamp(ts / 1000), price)
                for ts, price in price_data if price > 0
            ]

            # ✅ Keep only today's last 24 hourly points
            filtered = filtered[-24:]
            log.info(f"[SCRAPE] Parsed {len(filtered)} hourly price points.")

            return filtered

        except Exception as e:
            log.error(f"[ERROR] Failed to fetch hourly data: {e}")
            return []

    def generate_price_graph(self, price_data, player_name):
        """Generate a lime-green hourly price trend graph with black background + white text"""
        try:
            if len(price_data) < 2:
                log.warning("[GRAPH] Not enough data points to generate graph.")
                return None

            timestamps, prices = zip(*price_data)

            # Set up figure with black background
            fig, ax = plt.subplots(figsize=(6, 3))
            fig.patch.set_facecolor("#0D0D0D")
            ax.set_facecolor("#0D0D0D")

            # Lime-green FUT-style price line
            ax.plot(
                timestamps, prices,
                marker="o", linestyle="-", color="#39FF14",
                markersize=3, linewidth=2
            )

            # Titles & labels → white
            ax.set_title(
                f"{player_name} Price Trend (Today)",
                color="white", fontsize=11, fontweight="bold"
            )
            ax.set_xlabel("Time", color="white", fontsize=9)
            ax.set_ylabel("Coins", color="white", fontsize=9)

            # Grid lines → subtle gray
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3, color="#555555")

            # Set all spines to gray
            for spine in ax.spines.values():
                spine.set_color("#555555")

            # Format X-axis as HH:MM
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.xticks(rotation=45, color="white", fontsize=8)

            # Format Y-axis as 2,300,000 → 2300K
            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K")
            )
            plt.yticks(color="white", fontsize=8)

            # Tight layout for Discord display
            plt.tight_layout()

            # Save graph to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=220, facecolor=fig.get_facecolor())
            buf.seek(0)
            plt.close(fig)

            log.info("[GRAPH] Successfully generated styled black-background price graph.")
            return buf

        except Exception as e:
            log.error(f"[ERROR] Failed to generate graph: {e}")
            return None

    @app_commands.command(name="pricecheck", description="Check a player's FUTBIN price.")
    @app_commands.describe(player="Enter the name of the player", platform="Choose platform")
    @app_commands.choices(platform=[
        app_commands.Choice(name="🎮 Console", value="console"),
        app_commands.Choice(name="💻 PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        await interaction.response.defer()
        log.info(f"🔍 /pricecheck by {interaction.user.name} | Player: {player} | Platform: {platform.value}")

        match = next((p for p in self.players if f"{p['name']} {p['rating']}".lower() == player.lower()), None)
        if not match:
            await interaction.followup.send("❌ Player not found.")
            return

        url = match["url"]
        log.info(f"🔗 Scraping URL: {url}")

        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(res.text, "html.parser")

            price_box = soup.find("div", class_="price-box-original-player")
            price_tag = price_box.find("div", class_="price inline-with-icon lowest-price-1")
            price = price_tag.text.strip().replace(",", "") if price_tag else "N/A"
            price = f"{int(price):,}" if price.isdigit() else price

            trend_tag = price_box.find("div", class_="price-box-trend")
            raw_trend = trend_tag.get_text(strip=True).replace("Trend:", "") if trend_tag else "-"
            clean_trend = re.sub(r"[📉📈]", "", raw_trend).strip()
            trend_emoji = "📉" if "-" in clean_trend else "📈"
            trend_value = clean_trend

            delta_match = re.search(r"\(([\+\-]?\d+)\)", raw_trend)
            delta_k = f"{int(delta_match.group(1)) // 1000}K" if delta_match else ""
            trend_full = f"{trend_emoji} {trend_value} ({delta_k})" if delta_k else f"{trend_emoji} {trend_value}"

            range_tag = price_box.find("div", class_="price-pr")
            price_range = range_tag.text.strip().replace("PR:", "") if range_tag else "-"

            updated_tag = price_box.find("div", class_="prices-updated")
            updated = updated_tag.text.strip().replace("Price Updated:", "") if updated_tag else "-"

        except Exception as e:
            log.warning(f"[SCRAPE FAIL] {e}")
            price, trend_full, price_range, updated = "N/A", "-", "-", "-"

        embed = discord.Embed(
            title=f"{match['name']} ({match['rating']})",
            color=discord.Color.gold(),
        )
        embed.add_field(name="🎮 Platform", value="Console" if platform.value == "console" else "PC", inline=False)
        embed.add_field(name="💰 Price", value=f"{price} 🪙", inline=False)
        embed.add_field(name="📊 Range", value=price_range, inline=False)
        embed.add_field(name="📈 Trend", value=trend_full, inline=False)
        embed.add_field(name="🏟️ Club", value=match.get("club", "Unknown"), inline=True)
        embed.add_field(name="🌍 Nation", value=match.get("nation", "Unknown"), inline=True)
        embed.add_field(name="🧩 Position", value=match.get("position", "Unknown"), inline=True)
        embed.set_footer(text=f"🔴 Updated: {updated} • Data from FUTBIN")
        embed.set_thumbnail(url=f"https://cdn.futbin.com/content/fifa25/img/players/{match['id']}.png")

        # Fetch graph
        graph = None
        try:
            price_data = self.fetch_price_data(url)
            if price_data:
                graph = self.generate_price_graph(price_data, match['name'])
        except Exception as e:
            log.warning(f"[GRAPH FAIL] {e}")

        # Send embed with graph if available
        if graph:
            file = discord.File(graph, filename="graph.png")
            embed.set_image(url="attachment://graph.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            log.warning("[GRAPH] No graph generated — sending embed without image.")
            await interaction.followup.send(embed=embed)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            matches = [
                app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=f"{p['name']} {p['rating']}")
                for p in self.players if current.lower() in f"{p['name']} {p['rating']}".lower()
            ]
            return matches[:25]
        except Exception as e:
            log.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []


async def setup(bot):
    await bot.add_cog(PriceCheck(bot))