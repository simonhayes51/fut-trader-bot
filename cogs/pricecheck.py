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
from datetime import datetime
import tempfile
import os

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

    def generate_price_graph(self, data, player_name):
        timestamps = [datetime.fromtimestamp(ts / 1000) for ts, _ in data]
        prices = [price for _, price in data]

        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(timestamps, prices, marker='o', linestyle='-', color='blue', label="Console")
        ax.set_title(f"{player_name} Price Trend")
        ax.set_xlabel("Time")
        ax.set_ylabel("Price")
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.xticks(rotation=45)
        plt.tight_layout()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = tmp.name
            plt.savefig(path)
            plt.close()
            return path

    @app_commands.command(name="pricecheck", description="Check a player's FUTBIN price.")
    @app_commands.describe(player="Enter the name of the player", platform="Choose platform")
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: str = "console"):
        log.info(f"🧪 /pricecheck by {interaction.user.name} | Player: {player} | Platform: {platform}")
        match = next((p for p in self.players if f"{p['name']} {p['rating']}".lower() == player.lower()), None)

        if not match:
            await interaction.response.send_message("❌ Player not found.", ephemeral=True)
            return

        url = match["url"]
        log.info(f"🔗 Scraping URL: {url}")

        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            log.error(f"[SCRAPE ERROR] {e}")
            await interaction.response.send_message("❌ Failed to fetch price data.", ephemeral=True)
            return

        try:
            price_box = soup.find("div", class_="price-box-original-player")
            price_tag = price_box.find("div", class_="price inline-with-icon lowest-price-1")
            price = price_tag.text.strip().replace(",", "") if price_tag else "N/A"
            price = f"{int(price):,}" if price.isdigit() else price

            trend_tag = price_box.find("div", class_="price-box-trend")
            raw_trend = trend_tag.get_text(strip=True).replace("Trend:", "") if trend_tag else "-"
            clean_trend = re.sub(r"[📉📈]", "", raw_trend).strip()
            trend_emoji = "📉" if "-" in clean_trend else "📈"
            trend = f"{trend_emoji} {clean_trend}"

            range_tag = price_box.find("div", class_="price-pr")
            price_range = range_tag.text.strip().replace("PR:", "") if range_tag else "-"

            updated_tag = price_box.find("div", class_="prices-updated")
            updated = updated_tag.text.strip().replace("Price Updated:", "") if updated_tag else "-"

            # Graph data
            graph_wrapper = soup.find("div", class_="highcharts-graph-wrapper")
            data_ps_raw = graph_wrapper["data-ps-data"] if graph_wrapper else "[]"
            data_ps = json.loads(data_ps_raw)

        except Exception as e:
            log.warning(f"[WARN] Could not parse some price elements: {e}")
            price, trend, price_range, updated, data_ps = "N/A", "-", "-", "-", []

        # Build embed
        embed = discord.Embed(
            title=f"{match['name']} ({match['rating']})",
            color=0xFFD700,
        )
        embed.add_field(name="🎮 Platform", value="Console" if platform == "console" else "PC", inline=False)
        embed.add_field(name="💰 Price", value=f"{price} 🪙", inline=False)
        embed.add_field(name="📊 Range", value=price_range, inline=False)
        embed.add_field(name=f"{trend_emoji} Trend", value=clean_trend, inline=False)
        embed.add_field(name="🏟️ Club", value=match.get("club", "Unknown"), inline=True)
        embed.add_field(name="🌍 Nation", value=match.get("nation", "Unknown"), inline=True)
        embed.add_field(name="🧩 Position", value=match.get("position", "Unknown"), inline=True)
        embed.set_footer(text=f"🔴 Updated: {updated} • Data from FUTBIN")

        # Attach graph if we have data
        if data_ps:
            graph_path = self.generate_price_graph(data_ps, match['name'])
            file = discord.File(graph_path, filename="graph.png")
            embed.set_image(url="attachment://graph.png")
            await interaction.response.send_message(embed=embed, file=file)
            os.remove(graph_path)
        else:
            await interaction.response.send_message(embed=embed)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            suggestions = [
                app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=f"{p['name']} {p['rating']}")
                for p in self.players if current.lower() in f"{p['name']} {p['rating']}".lower()
            ][:25]
            return suggestions
        except Exception as e:
            log.error(f"[AUTOCOMPLETE ERROR] {e}")
            return []


async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
