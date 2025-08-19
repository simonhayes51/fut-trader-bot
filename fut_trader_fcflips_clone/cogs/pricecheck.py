import discord
from discord import app_commands
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json
import re
import unicodedata
import time
from difflib import SequenceMatcher

class PriceCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = self.load_players()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def load_players(self):
        try:
            with open("players_temp.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[INFO] Loaded {len(data)} players from database")
                return data
        except Exception as e:
            print(f"[ERROR] Couldn't load players: {e}")
            return []

    def similarity(self, a, b):
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def find_best_match(self, search_term):
        """Find the best matching player with improved fuzzy matching"""
        search_term = search_term.strip().lower()
        
        # First try exact match
        for player in self.players:
            player_full = f"{player['name'].lower()} {player['rating']}"
            if player_full == search_term:
                return player, 1.0
        
        # Then try partial matches and fuzzy matching
        best_match = None
        best_score = 0.0
        
        for player in self.players:
            player_full = f"{player['name'].lower()} {player['rating']}"
            player_name_only = player['name'].lower()
            
            # Check if search term contains the player name and rating
            if player_name_only in search_term and str(player['rating']) in search_term:
                score = self.similarity(search_term, player_full)
                if score > best_score:
                    best_match = player
                    best_score = score
            
            # Also check pure similarity
            similarity_score = self.similarity(search_term, player_full)
            if similarity_score > 0.8 and similarity_score > best_score:
                best_match = player
                best_score = similarity_score
        
        return best_match, best_score

    def generate_slug(self, name):
        """Generate a proper URL slug for FUTBIN"""
        # Handle special characters and accents
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        
        # Remove apostrophes, periods, and other special characters
        name = re.sub(r"['\.]", '', name)
        name = re.sub(r'[^\w\s-]', '', name)
        
        # Replace spaces and multiple hyphens with single hyphen
        name = re.sub(r'[-\s]+', '-', name.strip())
        
        return name.lower()

    def format_price(self, price_text):
        """Clean and format price text"""
        if not price_text:
            return "N/A"
        
        # Remove all non-numeric characters except commas and periods
        price_clean = re.sub(r'[^\d,.]', '', price_text)
        
        if not price_clean or price_clean in ['0', '0.0']:
            return "N/A"
        
        try:
            # Handle different number formats
            if '.' in price_clean and ',' in price_clean:
                # Format like 1,234.56 or 1.234,56
                if price_clean.rfind(',') > price_clean.rfind('.'):
                    # European format: 1.234,56
                    price_clean = price_clean.replace('.', '').replace(',', '.')
                else:
                    # US format: 1,234.56
                    price_clean = price_clean.replace(',', '')
            elif ',' in price_clean:
                # Could be thousands separator or decimal
                if len(price_clean.split(',')[-1]) <= 2:
                    # Likely decimal: 123,45
                    price_clean = price_clean.replace(',', '.')
                else:
                    # Likely thousands: 1,234
                    price_clean = price_clean.replace(',', '')
            
            price_num = int(float(price_clean))
            return f"{price_num:,}"
        
        except ValueError:
            return "N/A"

    def extract_price_from_element(self, element):
        """Extract price from a DOM element"""
        if not element:
            return None
        
        # Try different ways to get price text
        price_text = element.get_text(strip=True)
        
        # Also check for data attributes
        if not price_text or price_text == "0":
            price_text = element.get('data-price', '')
        
        if not price_text or price_text == "0":
            # Look for nested elements with price
            price_elem = element.find(['span', 'div'], class_=re.compile(r'price'))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
        
        return self.format_price(price_text) if price_text else None

    def get_price(self, url, platform):
        """Fetch price with multiple fallback strategies"""
        try:
            print(f"[DEBUG] Fetching URL: {url}")
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"[ERROR] HTTP {response.status_code} for URL: {url}")
                return "N/A"
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Strategy 1: Try the original method first
            price = self._try_original_method(soup, platform)
            if price != "N/A":
                print(f"[DEBUG] Original method success: {price}")
                return price
            
            # Strategy 2: Look for price containers with different selectors
            price = self._try_alternative_selectors(soup, platform)
            if price != "N/A":
                print(f"[DEBUG] Alternative selectors success: {price}")
                return price
            
            # Strategy 3: Search for any element containing price-like text
            price = self._try_text_search(soup, platform)
            if price != "N/A":
                print(f"[DEBUG] Text search success: {price}")
                return price
            
            print(f"[WARNING] No price found for {platform} on {url}")
            return "N/A"
            
        except requests.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            return "N/A"
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            return "N/A"

    def _try_original_method(self, soup, platform):
        """Try the original scraping method"""
        try:
            prices_wrapper = soup.find("div", class_="lowest-prices-wrapper")
            if not prices_wrapper:
                return "N/A"

            price_elements = prices_wrapper.find_all("div", class_="lowest-price")
            
            if len(price_elements) < 3:
                # Not enough price elements found
                return "N/A"

            if platform == "console":
                # Try PS first (index 0), then Xbox (index 1)
                ps_price = self.extract_price_from_element(price_elements[0])
                if ps_price and ps_price != "N/A":
                    return ps_price
                
                xbox_price = self.extract_price_from_element(price_elements[1])
                if xbox_price and xbox_price != "N/A":
                    return xbox_price
                    
            elif platform == "pc":
                pc_price = self.extract_price_from_element(price_elements[2])
                if pc_price and pc_price != "N/A":
                    return pc_price
            
            return "N/A"
        except Exception:
            return "N/A"

    def _try_alternative_selectors(self, soup, platform):
        """Try alternative CSS selectors for price elements"""
        selectors = [
            ".price-value",
            "[data-price]",
            ".player-price",
            ".current-price",
            ".bin-price",
            ".price"
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements:
                    price = self.extract_price_from_element(elem)
                    if price and price != "N/A":
                        return price
        
        return "N/A"

    def _try_text_search(self, soup, platform):
        """Search for price-like text patterns in the HTML"""
        try:
            # Look for text that matches price patterns
            text_content = soup.get_text()
            
            # Pattern for prices (numbers with potential commas/periods)
            price_pattern = r'\b(\d{1,3}(?:[,.]\d{3})*(?:[,.]\d{2})?)\b'
            matches = re.findall(price_pattern, text_content)
            
            for match in matches:
                formatted_price = self.format_price(match)
                if formatted_price != "N/A":
                    # Basic validation: price should be reasonable for FIFA cards
                    try:
                        price_num = int(formatted_price.replace(',', ''))
                        if 100 <= price_num <= 50000000:  # Reasonable FIFA price range
                            return formatted_price
                    except ValueError:
                        continue
            
            return "N/A"
        except Exception:
            return "N/A"

    def validate_url(self, url):
        """Validate that the FUTBIN URL exists"""
        try:
            response = self.session.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False

    @app_commands.command(name="pricecheck", description="Check the current FUTBIN price of a player")
    @app_commands.describe(
        player="Enter player name and rating (e.g. Lamine Yamal 97)", 
        platform="Choose platform"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="Console (PS/Xbox)", value="console"),
        app_commands.Choice(name="PC", value="pc")
    ])
    async def pricecheck(self, interaction: discord.Interaction, player: str, platform: app_commands.Choice[str]):
        await interaction.response.defer()

        try:
            # Find matching player with improved algorithm
            matched_player, confidence = self.find_best_match(player)

            if not matched_player or confidence < 0.6:
                embed = discord.Embed(
                    title="❌ Player Not Found",
                    description=f"Could not find '{player}' in the database.\nTry being more specific with name and rating.",
                    color=discord.Color.red()
                )
                
                # Suggest similar players
                suggestions = []
                for p in self.players[:10]:  # Check first 10 for suggestions
                    if any(word in p['name'].lower() for word in player.lower().split()):
                        suggestions.append(f"{p['name']} {p['rating']}")
                
                if suggestions:
                    embed.add_field(
                        name="Similar Players Found:",
                        value="\n".join(suggestions[:5]),
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                return

            player_id = matched_player["id"]
            player_name = matched_player["name"]
            rating = matched_player["rating"]
            
            # Generate proper slug
            slug = self.generate_slug(player_name)
            futbin_url = f"https://www.futbin.com/25/player/{player_id}/{slug}"
            
            print(f"[DEBUG] Matched: {player_name} ({rating}) - Confidence: {confidence:.2f}")
            print(f"[DEBUG] URL: {futbin_url}")

            # Validate URL before scraping
            if not self.validate_url(futbin_url):
                embed = discord.Embed(
                    title="⚠️ Player Page Not Found",
                    description=f"Found {player_name} ({rating}) in database, but FUTBIN page is not accessible.",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return

            # Get price with improved scraping
            price = self.get_price(futbin_url, platform.value)

            # Create response embed
            if confidence < 0.9:
                title = f"🔍 {player_name} ({rating}) - Best Match"
                description = f"**Confidence:** {confidence:.1%}\n**Platform:** {platform.name}\n**Price:** {price} 🪙"
            else:
                title = f"💰 {player_name} ({rating})"
                description = f"**Platform:** {platform.name}\n**Price:** {price} 🪙"

            color = discord.Color.green() if price != "N/A" else discord.Color.orange()
            
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                url=futbin_url
            )
            
            embed.set_footer(text="Data from FUTBIN • Click title to view full page")
            
            if price == "N/A":
                embed.add_field(
                    name="ℹ️ Note",
                    value="Price not available. The player might not have recent market data.",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[ERROR] pricecheck: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="An error occurred while fetching the price. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    @pricecheck.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        if not current:
            # Return top players if no input
            return [
                app_commands.Choice(name=f"{p['name']} {p['rating']}", value=f"{p['name']} {p['rating']}")
                for p in self.players[:25]
            ]
        
        current_lower = current.lower()
        matches = []
        
        # Prioritize exact matches and high-rated players
        for p in self.players:
            player_full = f"{p['name']} {p['rating']}"
            player_name = p['name'].lower()
            
            # Check if current input matches start of name or contains rating
            if (player_name.startswith(current_lower) or 
                current_lower in player_name or 
                str(p['rating']) in current):
                
                matches.append({
                    'choice': app_commands.Choice(name=player_full, value=player_full),
                    'rating': p['rating'],
                    'relevance': self.similarity(current_lower, player_full)
                })
        
        # Sort by relevance and rating (prefer higher rated players)
        matches.sort(key=lambda x: (x['relevance'], x['rating']), reverse=True)
        
        return [match['choice'] for match in matches[:25]]

async def setup(bot):
    await bot.add_cog(PriceCheck(bot))
