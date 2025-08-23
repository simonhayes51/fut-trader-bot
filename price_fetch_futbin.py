import re, asyncio, aiohttp
from bs4 import BeautifulSoup
from functools import lru_cache

HEADERS = {"User-Agent": "Mozilla/5.0 (educational bot)"}
SEM = asyncio.Semaphore(4)

def _num(txt: str) -> int:
    if not txt: return 0
    t = txt.lower().replace(",", "").strip()
    if t.endswith("k"):
        try: return int(float(t[:-1]) * 1000)
        except: return 0
    m = re.search(r"\d[\d,]*", t)
    return int(m.group(0).replace(",", "")) if m else 0

def _parse_platform_price(soup: BeautifulSoup, platform: str) -> int:
    plat = {"ps":"ps", "xbox":"xbox", "pc":"pc"}[platform]
    # Tight scope to price boxes if present
    box = soup.find("div", class_=re.compile(r"price[- ]?box", re.I))
    if not box:
        box = soup.find("div", class_=re.compile(r"price-box-original-player", re.I)) or soup

    # Look for platform label near a number
    for tag in box.find_all(string=re.compile(rf"\b{plat}\b", re.I)):
        txt = tag.parent.get_text(" ", strip=True)
        m = re.search(r"(\d[\d,\.kK]+)", txt)
        if m: return _num(m.group(1))

    # Fallback: historical lowest-price blocks
    for d in box.find_all("div", class_=re.compile(r"lowest-price", re.I)):
        txt = d.get_text(" ", strip=True)
        val = _num(txt)
        if val: return val

    # Last resort: largest number in the box
    txt = box.get_text(" ", strip=True)
    nums = re.findall(r"\d[\d,\.kK]+", txt)
    if nums:
        return max(_num(x) for x in nums)
    return 0

@lru_cache(maxsize=4096)
async def futbin_price_by_id(session: aiohttp.ClientSession, futbin_id: str, platform: str) -> int:
    url = f"https://www.futbin.com/25/player/{futbin_id}"
    async with SEM, session.get(url, headers=HEADERS, timeout=25) as r:
        html = await r.text()
    soup = BeautifulSoup(html, "html.parser")
    return _parse_platform_price(soup, platform)
