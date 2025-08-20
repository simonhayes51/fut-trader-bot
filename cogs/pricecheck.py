import discord
from discord.ext import commands
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json
import logging
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
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

            # ✅ Use 4-hour trend data
            graph_divs = soup.find_all("div", class_="highcharts-graph-wrapper")
            if len(graph_divs) >= 2:
                hourly_graph = graph_divs[1]
            else:
                hourly_graph = graph_divs[0]

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
            ax.plot(timestamps, prices, marker='o', linestyle='-', color='blue', label="Console")
            ax.set_title(f"{player_name} Price Trend (Last 4h)")
            ax.set_xlabel("Time")
            ax.set_ylabel("Coins")
            ax.grid(True)

            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K"))

            plt.xticks(rotation=45)
            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            plt.close(fig)
            return buffer
        except Exception as e:
            log.error(f"[ERROR] Failed to generate graph: {e}")
            return None

    def format_trend(self, raw_text):
        try:
            percent, delta = raw_text.split("(")
            delta_val = int(delta.replace(",", "").replace(")", ""))
            delta_k = f"{'+' if delta_val >= 0 else '-'}{abs(delta_val)//1000}K"
            arrow = "📈" if delta_val >= 0 else "📉"
            return f"{arrow} {percent.strip()} ({delta_k})"
        except:
            return raw_text

    @app_commands.command(name="pricecheck", description="Check a player's FUTBIN price.")
    @app_commands.describe(player="Enter the name of the player", platform="Choose platform")
    @app_commands.choices(platform=[
        app_commands.Choice(name="🎮 Console", value="ps"),
        app_commands.Choice(name="💻 PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        await interaction.response.defer()

        player_match = next((p for p in self.players if p["name"].lower() == player.lower()), None)
        if not player_match:
            await interaction.followup.send("❌ Player not found.")
            return

        futbin_id = player_match["id"]
        player_name = player_match["name"]
        rating = player_match["rating"]
        url = f"https://www.futbin.com/25/player/{futbin_id}"
        log.info(f"[LOOKUP] {player_name} - {url}")

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, "html.parser")

            # ✅ Price
            price_block = soup.find("div", class_="price-box-original-player")
            if not price_block:
                log.warning("[SCRAPE] Missing price block.")
            price_el = price_block.find("div", class_="price inline-with-icon lowest-price-1") if price_block else None
            price = price_el.text.strip().replace(",", "") if price_el else "N/A"

            # ✅ Trend
            trend_block = soup.find("div", class_="trend-card-body")
            trend_val_el = trend_block.find("div", class_="trend-value") if trend_block else None
            trend_raw = trend_val_el.text.strip() if trend_val_el else "N/A"
            trend_display = self.format_trend(trend_raw)

            # ✅ Price Range
            price_range_block = soup.find("div", class_="ps-lowest")
            price_range = price_range_block.text.strip() if price_range_block else "N/A"

            # ✅ Metadata
            club = player_match.get("club", "Unknown")
            nation = player_match.get("nation", "Unknown")
            position = player_match.get("position", "Unknown")

            # ✅ Graph
            price_data = self.fetch_price_data(url)
            graph = self.generate_price_graph(price_data, player_name)

            # ✅ Embed
            embed = discord.Embed(
                title=f"{player_name} ({rating})",
                description=(
                    f"**🎮 Platform:** {platform.name}\n"
                    f"**💰 Price:** {price} 🪙\n"
                    f"**📊 Range:** {price_range}\n"
                    f"**{trend_display}**\n"
                    f"**🏟️ Club:** {club}\n"
                    f"**🌍 Nation:** {nation}\n"
                    f"**🧩 Position:** {position}\n\n"
                    f"🔴 Updated: just now • Data from FUTBIN"
                ),
                color=discord.Color.blue()
            )
            embed.url = url

            if graph:
                file = discord.File(graph, filename="trend.png")
                embed.set_image(url="attachment://trend.png")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"[ERROR] Something went wrong: {e}")
            await interaction.followup.send("❌ Failed to fetch player data.")

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        matches = [p["name"] for p in self.players if current.lower() in p["name"].lower()]
        return [app_commands.Choice(name=name, value=name) for name in matches[:25]]

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
