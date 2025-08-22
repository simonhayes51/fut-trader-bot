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
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, "html.parser")

            # Attempt to find the second graph container (usually 4h)
            graph_divs = soup.find_all("div", class_="highcharts-graph-wrapper")
            log.info(f"[DEBUG] Found {len(graph_divs)} graph divs")

            if len(graph_divs) >= 2:
                hourly_graph = graph_divs[1]
            elif graph_divs:
                hourly_graph = graph_divs[0]
            else:
                log.warning("[SCRAPE] No graph container found")
                return []

            data_ps_raw = hourly_graph.get("data-ps-data", "[]")
            price_data = json.loads(data_ps_raw)

            return [(datetime.fromtimestamp(ts / 1000), price) for ts, price in price_data]
        except Exception as e:
            log.error(f"[ERROR] Failed to fetch graph data: {e}")
            return []

    def generate_price_graph(self, price_data, player_name):
        try:
            timestamps, prices = zip(*price_data)

            fig, ax = plt.subplots(figsize=(6, 3))
            ax.plot(timestamps, prices, marker='o', linestyle='-', color='blue')
            ax.set_title(f"{player_name} Price Trend (Hourly)")
            ax.set_xlabel("Time")
            ax.set_ylabel("Coins")
            ax.grid(True)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x / 1000)}K"))
            plt.xticks(rotation=45)
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close(fig)
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

        graph = None
        try:
            price_data = self.fetch_price_data(url)
            if price_data:
                graph = self.generate_price_graph(price_data, match['name'])
        except Exception as e:
            log.warning(f"[GRAPH FAIL] {e}")

        if graph:
            file = discord.File(graph, filename="graph.png")
            embed.set_image(url="attachment://graph.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
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
