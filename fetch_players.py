import os
import json
import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.futbin.com/25/players?page="
PLAYER_SELECTOR = "tr.player-row"
TEMP_FILE = "players_temp.json"

print("🔄 Resumable FUTBIN scraper starting...")

# Load existing players if temp file exists
if os.path.exists(TEMP_FILE):
    with open(TEMP_FILE, "r", encoding="utf-8") as f:
        try:
            players = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Couldn't load temp file — starting fresh.")
            players = []
else:
    players = []

# Build a set of known IDs to avoid duplicates
existing_ids = {p["id"] for p in players}
start_page = (len(players) // 30) + 1
print(f"📄 Resuming from page {start_page} (already have {len(players)} players)")

# Setup undetected Chrome
options = uc.ChromeOptions()
options.headless = True
driver = uc.Chrome(options=options)

try:
    for page_num in range(start_page, 300):  # Adjust upper limit if needed
        print(f"⏳ Scraping page {page_num}...")
        driver.get(BASE_URL + str(page_num))

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, PLAYER_SELECTOR)))
        except Exception:
            print(f"⚠️ Page {page_num} took too long to load. Skipping...")
            continue

        soup = BeautifulSoup(driver.page_source, "html.parser")
        rows = soup.select(PLAYER_SELECTOR)

        if not rows:
            print("⚠️ No player rows found — likely blocked or page structure changed.")
            break

        new_players = 0
        for row in rows:
            link = row.select_one("td.table-name a")
            if not link or "player/" not in link["href"]:
                continue

            player_id = link["href"].split("/")[3]
            if player_id in existing_ids:
                continue

            name = row.select_one("td.table-name .table-player-name")
            rating = row.select_one("td.table-rating .rating-square")
            pos = row.select_one("td.table-pos .table-pos-main")
            club = row.select_one("td .table-player-club img")
            nation = row.select_one("td .table-player-nation img")
            league = row.select_one("td .table-player-league img")
            url = "https://www.futbin.com" + link["href"]

            if not name or not rating:
                continue  # Skip broken/incomplete rows

            player_data = {
                "id": player_id,
                "name": name.text.strip(),
                "rating": rating.text.strip(),
                "position": pos.text.strip() if pos else None,
                "club": club["title"] if club else None,
                "nation": nation["title"] if nation else None,
                "league": league["title"] if league else None,
                "url": url,
                "prices": {
                    "ps": None,
                    "xbox": None
                }
            }

            players.append(player_data)
            existing_ids.add(player_id)
            new_players += 1
            print(f"✅ {player_data['name']} ({player_data['rating']})")

        # Save after every page
        with open(TEMP_FILE, "w", encoding="utf-8") as f:
            json.dump(players, f, indent=2)

        if new_players == 0:
            print("⚠️ No new players found on this page. Might be done.")
            break

        time.sleep(3)

finally:
    driver.quit()
    print(f"✅ Finished. Scraped {len(players)} total players.")
