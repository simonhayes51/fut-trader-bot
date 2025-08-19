import requests

def get_player_price(player_id):
    url = f"https://www.futbin.com/24/playerPrices?player={player_id}"
    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get(str(player_id), {}).get("prices", {})
    except Exception as e:
        print("Price fetch error:", e)
    return {}