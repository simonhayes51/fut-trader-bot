import requests
from bs4 import BeautifulSoup

def search_futbin_player(name):
    url = f"https://www.futbin.com/search?year=24&term={name.replace(' ', '%20')}"
    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = soup.find_all("a", class_="player_name_players_table")
        return [{
            "name": r.text.strip(),
            "id": int(r.get("data-playerid")),
            "url": f"https://www.futbin.com/24/player/{r.get('data-playerid')}"
        } for r in results if r.get("data-playerid")][:5]
    except Exception as e:
        print("Search error:", e)
        return []