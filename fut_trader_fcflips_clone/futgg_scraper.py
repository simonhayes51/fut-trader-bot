import json
import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

def scrape_futgg_players():
    base_url = "https://www.fut.gg/players/"
    players_data = []
    page = 1

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(options=options)

    try:
        while True:
            print(f"🔎 Scraping page {page}...")
            driver.get(f"{base_url}?page={page}")
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards = soup.select("a[href^='/players/']")

            if not cards:
                break

            for card in cards:
                try:
                    img = card.select_one("img")
                    alt_text = img["alt"] if img and "alt" in img.attrs else None
                    if not alt_text:
                        continue

                    parts = [part.strip() for part in alt_text.split(" - ")]
                    if len(parts) < 3:
                        continue

                    name = parts[0]
                    rating = parts[1]
                    card_type = parts[2]
                    full_url = "https://www.fut.gg" + card["href"]

                    players_data.append({
                        "name": name,
                        "rating": rating,
                        "card_type": card_type,
                        "url": full_url
                    })
                except Exception as e:
                    print(f"❌ Error parsing player: {e}")
                    continue

            page += 1
            time.sleep(1)

    finally:
        driver.quit()

    with open("futgg_players.json", "w", encoding="utf-8") as f:
        json.dump(players_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Scraped {len(players_data)} players.")

if __name__ == "__main__":
    scrape_futgg_players()
