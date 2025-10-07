# cogs/trending.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import asyncio
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fut.gg/",
}
MOMENTUM_BASE = "https://www.fut.gg/players/momentum"

# ====== robust id + percent parsing ======
RE_SEG = re.compile(r"/players/[^?#]*/26-(\d+)(?:[/?#]|$)", re.I)
RE_LAST = re.compile(r"/players/[^?#]*?(\d+)(?:[/?#]|$)", re.I)
RE_PCT = re.compile(r"([+\-]?\s?\d+(?:\.\d+)?)\s*%")

def _card_id(href: str):
    if "/players/" not in href:
        return None
    m = RE_SEG.search(href) or RE_LAST.search(href)
    if not m:
        return None
    try:
        return int(m.group(1))
    except:
        return None

def _nearest_pct(node):
    cur = node
    for _ in range(5):
        if cur is None:
            break
        txt = cur.get_text(" ", strip=True) if hasattr(cur, "get_text") else ""
        m = RE_PCT.search(txt or "")
        if m:
            try:
                return float(m.group(1).replace(" ", ""))
            except:
                pass
        cur = getattr(cur, "parent", None)
    p = getattr(node, "parent", None)
    if p:
        for sib in getattr(p, "children", []):
            try:
                txt = sib.get_text(" ", strip=True)
                m = RE_PCT.search(txt or "")
                if m:
                    return float(m.group(1).replace(" ", ""))
            except:
                pass
    return None

async def _fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as r:
        r.raise_for_status()
        return await r.text()

async def _momentum_page(session: aiohttp.ClientSession, tf: str, page: int) -> str:
    # tf is "6" or "24"
    url = f"{MOMENTUM_BASE}/{tf}/?page={page}"
    return await _fetch_html(session, url)

def _parse_last_page_num(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    last = 1
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if "page=" in href:
            try:
                n = int(href.split("page=", 1)[1].split("&", 1)[0])
                last = max(last, n)
            except:
                pass
        else:
            t = (a.text or "").strip()
            if t.isdigit():
                last = max(last, int(t))
    return last

def _extract_items(html: str):
    soup = BeautifulSoup(html, "html.parser")
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        cid = _card_id(href)
        if not cid or cid in seen:
            continue
        pct = _nearest_pct(a)
        if pct is None:
            continue
        # try to get a readable name
        alt_tag = a.find("img", alt=True)
        name = None
        if alt_tag and isinstance(alt_tag.get("alt"), str):
            name = alt_tag["alt"].split(" - ", 1)[0].strip()
        # fallback from slug
        if not name or name.lower() in {"momentum", "none", "null", "n/a"}:
            try:
                seg = href.split("/players/", 1)[1].split("/", 1)[0]
                if "-" in seg:
                    name = " ".join(s.capitalize() for s in seg.split("-", 1)[1].split("-"))
            except:
                name = None
        if not name or name.lower() in {"momentum", "none"}:
            continue  # drop nameless/placeholder rows
        items.append({"card_id": cid, "name": name, "percent": pct})
        seen.add(cid)
    return items

# ====== robust Console price fetcher (multi-schema) ======
async def _get_console_price(session: aiohttp.ClientSession, card_id: int):
    endpoints = [
        f"https://www.fut.gg/api/fut/player-prices/26/{card_id}",
        # some cards resolve here without the season segment:
        f"https://www.fut.gg/api/fut/player-prices/{card_id}",
    ]
    for url in endpoints:
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    continue
                data = await r.json()
        except Exception:
            continue

        # Try schema A: { prices: { ps: { price|lowestBin|LCPrice } } }
        try:
            ps = (data or {}).get("prices", {}).get("ps", {}) or {}
            val = ps.get("price") or ps.get("lowestBin") or ps.get("LCPrice")
            if isinstance(val, (int, float)) and val > 0:
                return int(val)
        except Exception:
            pass

        # Try schema B: { data: { currentPrice: { price } } } (seen on some responses)
        try:
            val = (data or {}).get("data", {}).get("currentPrice", {}).get("price")
            if isinstance(val, (int, float)) and val > 0:
                return int(val)
        except Exception:
            pass

    return None

class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def _fetch_trending(self, kind: str, tf: str, limit: int = 10):
        # tf: "6" or "24", kind: "risers"|"fallers"
        first_html = await _momentum_page(self.session, tf, 1)
        last_page = _parse_last_page_num(first_html)

        if kind == "fallers":
            base = _extract_items(first_html)
            base.sort(key=lambda x: x["percent"])
            out = base[:limit]
            if len(out) < limit and last_page > 1:
                tail = _extract_items(await _momentum_page(self.session, tf, last_page))
                tail.sort(key=lambda x: x["percent"])
                out = (base + tail)[:limit]
        else:  # risers
            last = _extract_items(await _momentum_page(self.session, tf, last_page))
            last.sort(key=lambda x: x["percent"], reverse=True)
            out = last[:limit]
            if len(out) < limit and last_page > 1:
                head = _extract_items(first_html)
                head.sort(key=lambda x: x["percent"], reverse=True)
                out = (last + head)[:limit]

        # fetch prices concurrently
        async def attach(it):
            it["price"] = await _get_console_price(self.session, int(it["card_id"]))
            return it

        out = out[:limit]
        out = await asyncio.gather(*(attach(i) for i in out))
        return out

    @app_commands.command(name="trending", description="Show top risers/fallers from FUT.GG Momentum")
    @app_commands.choices(
        trend_type=[
            app_commands.Choice(name="📈 Risers", value="risers"),
            app_commands.Choice(name="📉 Fallers", value="fallers"),
        ],
        timeframe=[
            app_commands.Choice(name="🕕 6h", value="6h"),
            app_commands.Choice(name="📅 24h", value="24h"),
        ],
    )
    async def trending(
        self,
        interaction: discord.Interaction,
        trend_type: app_commands.Choice[str],
        timeframe: app_commands.Choice[str],
    ):
        await interaction.response.defer(thinking=True)

        tf_num = "6" if timeframe.value.startswith("6") else "24"
        data = await self._fetch_trending(kind=trend_type.value, tf=tf_num, limit=10)

        emoji = "📉" if trend_type.value == "fallers" else "📈"
        clock = "🕕" if tf_num == "6" else "📅"
        embed = discord.Embed(
            title=f"{emoji} Top 10 {trend_type.name.split()[-1]} – {clock} {timeframe.value}",
            colour=discord.Colour.red() if trend_type.value == "fallers" else discord.Colour.green(),
        )

        if not data:
            embed.description = "No data found."
        else:
            num = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
            lines = []
            for i, it in enumerate(data[:10]):
                price_txt = f"{it['price']:,} 🪙" if it.get("price") else "N/A"
                lines.append(
                    f"{num[i]} **{it['name']}**\n💰 {price_txt}\n{emoji} {it['percent']:+.2f}%"
                )
            embed.description = "\n\n".join(lines)

        embed.set_footer(text=f"Data & Prices: FUT.GG • Created by www.futhub.co.uk • Updated: {datetime.utcnow().isoformat()}Z")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Trending(bot))