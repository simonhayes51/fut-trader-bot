# price_fetch_futbin.py
import re, asyncio, aiohttp
from bs4 import BeautifulSoup
from functools import lru_cache

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.2)"}
SEM = asyncio.Semaphore(4)

PLAT_MAP = {"ps": "ps", "playstation": "ps", "console": "ps",
            "xbox": "xbox", "xb": "xbox",
            "pc": "pc"}

def _plat_key(p: str) -> str:
    return PLAT_MAP.get((p or "").lower(), "ps")

def _num(txt: str) -> int:
    if not txt: return 0
    t = txt.lower().replace(",", "").strip()
    if t.endswith("k"):
        try: return int(float(t[:-1]) * 1000)
        except: return 0
    m = re.search(r"\d[\d,]*", txt)
    return int(m.group(0).replace(",", "")) if m else 0

def _parse_platform_price(soup: BeautifulSoup, platform: str) -> int:
    plat = _plat_key(platform)
    box = soup.find("div", class_=re.compile(r"price[- ]?box", re.I))
    if not box:
        box = soup.find("div", class_=re.compile(r"price-box-original-player", re.I)) or soup
    # try platform label near number
    for tag in box.find_all(string=re.compile(rf"\b{plat}\b", re.I)):
        txt = tag.parent.get_text(" ", strip=True)
        m = re.search(r"(\d[\d,\.kK]+)", txt)
        if m: return _num(m.group(1))
    # legacy lowest-price blocks
    for d in box.find_all("div", class_=re.compile(r"lowest-price", re.I)):
        val = _num(d.get_text(" ", strip=True))
        if val: return val
    # last resort: largest number in the block
    nums = re.findall(r"\d[\d,\.kK]+", box.get_text(" ", strip=True))
    return max((_num(x) for x in nums), default=0)

@lru_cache(maxsize=4096)
async def futbin_price_by_id(session: aiohttp.ClientSession, futbin_id: str, platform: str) -> int:
    """Return FUTBIN player price for platform, 0 on error."""
    url = f"https://www.futbin.com/25/player/{futbin_id}"
    try:
        async with SEM:
            async with session.get(url, headers=HEADERS, timeout=25) as r:
                if r.status != 200:
                    return 0
                html = await r.text()
        soup = BeautifulSoup(html, "html.parser")
        return _parse_platform_price(soup, platform)
    except Exception:
        return 0