# futbin_cheapest.py
import re, aiohttp, asyncio
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.4)"}
SEM = asyncio.Semaphore(4)

def _num(txt: str) -> int:
    if not txt: return 0
    t = txt.lower().replace(",", "").strip()
    if t.endswith("k"):
        try: return int(float(t[:-1]) * 1000)
        except: return 0
    m = re.search(r"\d[\d,]*", t)
    return int(m.group(0).replace(",", "")) if m else 0

def _plat_col_idx(plat_key: str) -> int:
    # Typical FUTBIN players table order: Name, Rating, .., PS, Xbox, PC
    return {"ps_price": 3, "xbox_price": 4, "pc_price": 5}.get(plat_key, 3)

async def _scrape_players_table(session, url: str, plat_key: str, limit: int):
    async with SEM, session.get(url, headers=HEADERS, timeout=25) as r:
        html = await r.text()
    soup = BeautifulSoup(html, "html.parser")
    out, col = [], _plat_col_idx(plat_key)
    for row in soup.select("tr"):
        tds = row.select("td")
        if len(tds) <= col: continue
        name = tds[1].get_text(" ", strip=True)
        price_txt = tds[col].get_text(" ", strip=True)
        price_val = _num(price_txt)
        if name and price_val > 0:
            out.append({"name": name, "price": price_val})
        if len(out) >= limit: break
    return out

async def futbin_cheapest_by_rating(session: aiohttp.ClientSession, rating: int, platform: str, limit: int = 20):
    plat_key = {"ps":"ps_price", "xbox":"xbox_price", "pc":"pc_price"}.get((platform or "ps").lower(), "ps_price")
    url = f"https://www.futbin.com/players?player_rating={rating}-{rating}&sort={plat_key}&order=asc&eUnt=1"
    return await _scrape_players_table(session, url, plat_key, limit)

async def futbin_cheapest_special(session: aiohttp.ClientSession, kind: str, min_rating: int, platform: str, limit: int = 12):
    """
    kind: "totw" or "tots"
    Tries FUTBIN filter via 'version' query (works on most pages). Best-effort.
    """
    plat_key = {"ps":"ps_price", "xbox":"xbox_price", "pc":"pc_price"}.get((platform or "ps").lower(), "ps_price")
    version = "totw" if kind.lower() == "totw" else "tots"
    url = (f"https://www.futbin.com/players?version={version}"
           f"&player_rating={min_rating}-99&sort={plat_key}&order=asc&eUnt=1")
    return await _scrape_players_table(session, url, plat_key, limit)
