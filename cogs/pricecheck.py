import discord
from discord import app_commands
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()

    def load_players(self):
        try:
            with open("players_temp.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Couldn't load players: {e}")
            return []

    @app_commands.command(name="pricecheck", description="Check the current FUTBIN price of a player")
    @app_commands.describe(player="Enter player name and rating (e.g. Lamine Yamal 97)", platform="Choose platform")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Console", value="console"),
        app_commands.Choice(name="PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        print(f"🧪 /pricecheck triggered by {interaction.user} for {player} on {platform.name}")
        await interaction.response.defer()

        try:
            matched_player = next(
                (p for p in self.players if f"{p['name'].lower()} {p['rating']}" == player.lower()), None
            )

            if not matched_player:
                await interaction.followup.send("❌ Player not found in local data.")
                return

            player_id = matched_player["id"]
            player_name = matched_player["name"]
            rating = matched_player["rating"]
            slug = player_name.replace(" ", "-").lower()

            futbin_url = f"https://www.futbin.com/25/player/{player_id}/{slug}"
            print(f"🔗 Scraping URL: {futbin_url}")

            price = self.get_price(futbin_url, platform.value)

            embed = discord.Embed(
                title=f"{player_name} ({rating})",
                description=f"**Platform:** {platform.name}\n**Price:** {price} 🪙",
                color=discord.Color.green()
            )
            embed.set_footer(text="Data from FUTBIN")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[ERROR] pricecheck: {e}")
            await interaction.followup.send("⚠️ An error occurred while fetching the price.")

    def get_price(self, url, platform):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")

            print(f"🌐 [GET] Status: {response.status_code}")
            print(f"📄 Page Title: {soup.title.string if soup.title else 'N/A'}")

            prices_wrapper = soup.find("div", class_="lowest-prices-wrapper")
            if not prices_wrapper:
                print("[ERROR] Could not find prices wrapper")
                return "N/A"

            print("🧱 Matched container HTML:", str(prices_wrapper)[:300], "...")

            price_elements = prices_wrapper.find_all("div", class_="lowest-price")
            print(f"💬 Found {len(price_elements)} price elements:")
            for i, el in enumerate(price_elements):
                print(f"  [{i}] {el.text.strip()}")

            def get_price_text(index):
                if len(price_elements) > index:
                    raw_text = price_elements[index].text.strip()
                    print(f"🔎 Raw price @ index {index}: {raw_text}")
                    return raw_text.replace(",", "").replace("\n", "")
                return "0"

            if platform == "console":
                ps_price = get_price_text(0)
                xbox_price = get_price_text(1)
                price = ps_price if ps_price != "0" else xbox_price
                print(f"🎮 Selected Console Price: {price}")
            elif platform == "pc":
                price = get_price_text(2)
                print(f"💻 Selected PC Price: {price}")
            else:
                print(f"[ERROR] Unknown platform: {platform}")
                return "N/A"

            if price == "0" or price == "":
                print("[WARN] Price is zero or blank")
                return "N/A"

            formatted_price = f"{int(price):,}"
            print(f"✅ Final formatted price: {formatted_price}")
            return formatted_price

        except Exception as e:
            print(f"[SCRAPE ERROR] {e}")
            return "N/A"

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        return [
            app_commands.Choice(name=f"{p['name']} {p['rating']}", value=f"{p['name']} {p['rating']}")
            for p in self.players if current in f"{p['name']} {p['rating']}".lower()
        ][:25]

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
