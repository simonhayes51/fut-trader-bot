# futbin_cheapest.py
import re, aiohttp, asyncio
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.2)"}
SEM = asyncio.Semaphore(4)

def _num(txt: str) -> int:
    if not txt: return 0
    t = txt.lower().replace(",", "").strip()
    if t.endswith("k"):
        try: return int(float(t[:-1]) * 1000)
        except: return 0
    m = re.search(r"\d[\d,]*", t)
    return int(m.group(0).replace(",", "")) if m else 0

async def futbin_cheapest_by_rating(session: aiohttp.ClientSession, rating: int, platform: str, limit: int = 20):
    """
    Returns a list like [{"name": "...", "price": 12345}, ...] (filtered to >0 price),
    sorted by FUTBIN's per-platform cheapest list.
    """
    plat = {"ps":"ps_price", "xbox":"xbox_price", "pc":"pc_price"}.get(platform.lower(), "ps_price")
    url = f"https://www.futbin.com/players?player_rating={rating}-{rating}&sort={plat}&order=asc&eUnt=1"
    async with SEM, session.get(url, headers=HEADERS, timeout=25) as r:
        html = await r.text()
    soup = BeautifulSoup(html, "html.parser")
    out = []
    # table often has PS/Xbox/PC columns; we’ll try to locate the platform column by index/heading
    for row in soup.select("tr"):
        tds = row.select("td")
        if len(tds) < 4:
            continue
        name = tds[1].get_text(" ", strip=True)
        cols = [td.get_text(" ", strip=True) for td in tds]
        # heuristic: PS at idx 3, Xbox 4, PC 5 (typical layout). Try by label fallback.
        price_txt = None
        if plat == "ps_price" and len(cols) > 3: price_txt = cols[3]
        elif plat == "xbox_price" and len(cols) > 4: price_txt = cols[4]
        elif plat == "pc_price" and len(cols) > 5: price_txt = cols[5]
        if not price_txt:
            merged = row.get_text(" ", strip=True)
            m = re.search(r"(\d[\d,\.kK]+)", merged)
            price_txt = m.group(1) if m else ""
        price_val = _num(price_txt)
        if name and price_val > 0:
            out.append({"name": name, "price": price_val})
        if len(out) >= limit:
            break
    return out