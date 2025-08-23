# futbin_cheapest.py
import re, aiohttp, asyncio
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.5)"}
SEM = asyncio.Semaphore(4)

def normalize_platform_key(platform: str) -> str:
    """
    Normalises platform strings to one of: ps, xbox, pc
    """
    if not platform:
        return "ps"
    p = platform.lower()
    if p in ("ps", "playstation", "ps5", "ps4"):
        return "ps"
    if p in ("xb", "xbox", "xsx", "xss", "xone"):
        return "xbox"
    if p in ("pc", "origin", "steam", "windows"):
        return "pc"
    return "ps"

def _num(txt: str) -> int:
    if not txt: return 0
    t = txt.lower().replace(",", "").strip()
    if t.endswith("k"):
        try: return int(float(t[:-1]) * 1000)
        except: return 0
    m = re.search(r"\d[\d,]*", t)
    return int(m.group(0).replace(",", "")) if m else 0

def _plat_key(platform: str) -> str:
    return {"ps":"ps_price", "xbox":"xbox_price", "pc":"pc_price"}.get((platform or "ps").lower(), "ps_price")

async def _scrape_players_table(session, url: str, plat_key: str, limit: int):
    async with SEM, session.get(url, headers=HEADERS, timeout=25) as r:
        html = await r.text()
    soup = BeautifulSoup(html, "html.parser")

    # Map header names to indexes
    header_map = {}
    thead = soup.find("thead")
    if thead:
        ths = thead.select("th")
        for i, th in enumerate(ths):
            txt = th.get_text(" ", strip=True).lower()
            header_map[txt] = i

    # Choose platform column by header text
    want = {"ps_price": ("ps", "playstation"), "xbox_price": ("xbox",), "pc_price": ("pc", "computer")}
    plat_candidates = want.get(plat_key, ("ps",))
    plat_idx = None
    for key, idx in header_map.items():
        if any(p in key for p in plat_candidates):
            plat_idx = idx
            break
    if plat_idx is None:
        plat_idx = {"ps_price": 3, "xbox_price": 4, "pc_price": 5}.get(plat_key, 3)

    out = []
    tbody = soup.find("tbody") or soup
    for row in tbody.select("tr"):
        tds = row.select("td")
        if len(tds) <= max(1, plat_idx):
            continue
        name = tds[1].get_text(" ", strip=True)
        price_txt = tds[plat_idx].get_text(" ", strip=True)
        price_val = _num(price_txt)
        if name and price_val > 0:
            out.append({"name": name, "price": price_val})
        if len(out) >= limit:
            break
    return out

async def futbin_cheapest_by_rating(session: aiohttp.ClientSession, rating: int, platform: str, limit: int = 20):
    plat_key = _plat_key(platform)
    url = f"https://www.futbin.com/players?player_rating={rating}-{rating}&sort={plat_key}&order=asc&eUnt=1"
    return await _scrape_players_table(session, url, plat_key, limit)

async def futbin_cheapest_special(session: aiohttp.ClientSession, kind: str, min_rating: int, platform: str, limit: int = 12):
    """
    kind: "totw" or "tots"; best-effort using FUTBIN list filters.
    """
    plat_key = _plat_key(platform)
    version = "totw" if kind.lower() == "totw" else "tots"
    url = (f"https://www.futbin.com/players?version={version}"
           f"&player_rating={min_rating}-99&sort={plat_key}&order=asc&eUnt=1")
    return await _scrape_players_table(session, url, plat_key, limit)
