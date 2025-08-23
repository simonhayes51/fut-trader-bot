# cogs/sbcsolve.py
import os, re, time, json, difflib
import discord, aiohttp
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from sbc_core import build_indexes
from price_fetch_futbin import futbin_price_by_id

# ------------ Config ------------
PLAYERS_JSON = os.getenv("PLAYERS_JSON", "players_temp.json")
FUTBIN_BASE  = "https://www.futbin.com"
FUTGG_BASE   = "https://www.fut.gg"
SBC_CACHE_TTL = 600  # 10 minutes
UA = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.0)"}

# ------------ Utils ------------
def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"player ?pick", "pp", s)   # common alias normalization
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _is_futgg(url: str) -> bool:
    return "fut.gg" in (url or "")

def _is_futbin(url: str) -> bool:
    return "futbin.com" in (url or "")

# ------------ Cog ------------
class SBCSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.players = data if isinstance(data, list) else list(data.values())
        self.indexes = build_indexes(self.players)
        self._sbc_cache = {"items": [], "ts": 0.0}

    # ----- HTTP -----
    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(url, headers=UA, timeout=25) as r:
            r.raise_for_status()
            return await r.text()

    # ----- List sources -----
    async def _fetch_futgg_sbc_list(self, session):
        """Primary: FUT.GG – clean SBC cards."""
        html = await self.fetch_html(session, f"{FUTGG_BASE}/sbc/")
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.select('a[href^="/sbc/"]'):
            title = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            if not title or href == "/sbc/":
                continue
            url = href if href.startswith("http") else f"{FUTGG_BASE}{href}"
            out.append((title, url))
        # de-dup & sort
        seen, uniq = set(), []
        for t,u in out:
            if (t,u) in seen: continue
            seen.add((t,u)); uniq.append((t,u))
        uniq.sort(key=lambda x: x[0].lower())
        return uniq

    async def _fetch_futbin_sbc_list(self, session):
        """Fallback: FUTBIN – filter out sidebar/category links."""
        html = await self.fetch_html(session, f"{FUTBIN_BASE}/squad-building-challenges")
        soup = BeautifulSoup(html, "html.parser")
        out = []

        main = soup.select_one("#content") or soup  # resilient scope
        for a in main.select("a[href*='/squad-building-challenges/']"):
            title = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            if not title or not href:
                continue
            if "?" in href:  # skip menu/category filters
                continue
            slug = href.split("/squad-building-challenges/")[-1].strip("/")
            if not slug:
                continue
            # obvious categories to skip
            blocked = {
                "upgrades", "players", "icons", "foundations", "challenges", "mode-mastery",
                "community-sbc-solutions", "cheapest-player-by-rating", "sbc-rating-combinations",
                "best-value-sbcs"
            }
            if slug.lower() in blocked:
                continue
            if not re.search(r"[-\d]", slug):  # real SBCs usually have dashes/numbers
                continue
            url = href if href.startswith("http") else f"{FUTBIN_BASE}{href}"
            out.append((title, url))

        seen, uniq = set(), []
        for t,u in out:
            if (t,u) in seen: continue
            seen.add((t,u)); uniq.append((t,u))
        uniq.sort(key=lambda x: x[0].lower())
        return uniq

    async def get_sbc_list_cached(self, session, force: bool = False):
        """Try FUT.GG first, FUTBIN fallback. Cache for 10 minutes."""
        now = time.time()
        if (not force) and self._sbc_cache["items"] and (now - self._sbc_cache["ts"] < SBC_CACHE_TTL):
            return self._sbc_cache["items"]

        items = []
        try:
            items = await self._fetch_futgg_sbc_list(session)
        except Exception:
            items = []
        if not items:
            try:
                items = await self._fetch_futbin_sbc_list(session)
            except Exception:
                items = []

        self._sbc_cache = {"items": items, "ts": now}
        return items

    # ----- Matching -----
    def fuzzy_pick(self, items, query):
        if not items:
            return None, []
        qn = _norm(query)

        # Prefer direct substring match
        for t,u in items:
            if qn and qn in _norm(t):
                return (t,u), []

        # Fuzzy fallback
        norm_map = { _norm(t): (t,u) for t,u in items }
        norm_titles = list(norm_map.keys())
        best = difflib.get_close_matches(qn, norm_titles, n=1, cutoff=0.4)
        sugg = difflib.get_close_matches(qn, norm_titles, n=6, cutoff=0.3)
        picked = norm_map[best[0]] if best else None
        suggestions = [norm_map[s][0] for s in sugg if s in norm_map][:5]
        return picked, suggestions

    # ----- Solution parsers -----
    def _parse_solution_from_futgg(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        players = []
        # table rows first
        for row in soup.select("table tbody tr"):
            cols = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cols) >= 2:
                name = cols[1]
                rat_m = re.search(r"\b(\d{2,3})\b", cols[0] or "")
                rating = int(rat_m.group(1)) if rat_m else 0
                if name:
                    players.append({"name": name, "rating": rating})
            if len(players) >= 11:
                break
        # fallback: card tiles
        if len(players) < 11:
            for card in soup.select("[class*='player']"):
                txt = card.get_text(" ", strip=True)
                name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", txt)
                rat_m  = re.search(r"\b(\d{2,3})\b", txt)
                if name_m:
                    players.append({"name": name_m.group(1).strip(),
                                    "rating": int(rat_m.group(1)) if rat_m else 0})
                if len(players) >= 11:
                    break
        return players[:11]

    def _parse_solution_from_futbin(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        players = []
        # community/AI solution table rows
        for row in soup.select("table tbody tr"):
            cols = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cols) >= 2:
                name = cols[1]
                rat_m = re.search(r"\b(\d{2,3})\b", cols[0] or "")
                rating = int(rat_m.group(1)) if rat_m else 0
                if name:
                    players.append({"name": name, "rating": rating})
            if len(players) >= 11:
                break
        # fallback: any card-like block
        if len(players) < 11:
            for card in soup.select("[class*='player'], [class*='squad']"):
                txt = card.get_text(" ", strip=True)
                name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", txt)
                rat_m  = re.search(r"\b(\d{2,3})\b", txt)
                if name_m:
                    players.append({"name": name_m.group(1).strip(),
                                    "rating": int(rat_m.group(1)) if rat_m else 0})
                if len(players) >= 11:
                    break
        return players[:11]

    # ----- Command -----
    @app_commands.command(name="sbcsolve", description="List active SBCs or solve by name")
    @app_commands.describe(sbcname="Start typing to autocomplete SBC name", platform="ps/xbox/pc")
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str | None = None, platform: str = "ps"):
        await interaction.response.defer(thinking=True)
        plat = (platform or "ps").lower().strip()

        async with aiohttp.ClientSession() as session:
            items = await self.get_sbc_list_cached(session)

            # List mode (no name)
            if not sbcname:
                embed = discord.Embed(title="Current SBCs", colour=discord.Colour.green())
                for t,u in items[:15]:
                    embed.add_field(name=t, value=f"[Open]({u})", inline=False)
                await interaction.followup.send(embed=embed)
                return

            # Solve mode
            pick, suggestions = self.fuzzy_pick(items, sbcname)
            if not pick:
                msg = f"No SBC found matching “{sbcname}”."
                if suggestions:
                    msg += "\nDid you mean:\n• " + "\n• ".join(suggestions)
                await interaction.followup.send(msg)
                return

            title, link = pick
            html = await self.fetch_html(session, link)
            if _is_futgg(link):
                players = self._parse_solution_from_futgg(html)
            else:
                players = self._parse_solution_from_futbin(html)

            if not players:
                await interaction.followup.send(f"Couldn't parse a solution for **{title}**.")
                return

            # Map names -> your JSON (FUTBIN IDs), then fetch live FUTBIN prices
            price_map = {}
            for p in players:
                # exact name first
                cands = self.indexes["by_name"].get(p["name"].lower(), [])
                if not cands:
                    # surname fallback
                    surname = p["name"].split()[-1].lower()
                    keys = [k for k in self.indexes["by_name"].keys() if surname in k]
                    cands = sum((self.indexes["by_name"][k] for k in keys), [])
                p["pid"] = cands[0]["pid"] if cands else None

            for p in players:
                if p.get("pid"):
                    price_map[p["pid"]] = await futbin_price_by_id(session, str(p["pid"]), plat)

        total = sum(price_map.get(p.get("pid"), 0) for p in players if p.get("pid"))

        embed = discord.Embed(
            title=f"SBC: {title}",
            description=f"Platform: {plat.upper()}",
            colour=discord.Colour.green()
        )
        embed.add_field(name="Estimated Total", value=f"{total:,} coins", inline=False)
        lines = []
        for p in players:
            if p.get("pid"):
                price = price_map.get(p["pid"], 0)
                lines.append(f"{p.get('rating', 0):>2} — {p['name']} • {price:,}")
            else:
                lines.append(f"{p.get('rating', 0):>2} — {p['name']} • N/A")
        embed.add_field(name="XI", value="\n".join(lines)[:1024] or "—", inline=False)
        embed.set_footer(text=f"Matched: {title}")
        await interaction.followup.send(embed=embed)

    # ----- Autocomplete (uses the 10-min cache) -----
    @sbcsolve.autocomplete("sbcname")
    async def _sbcname_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            async with aiohttp.ClientSession() as session:
                items = await self.get_sbc_list_cached(session)
        except Exception:
            return []
        cur = _norm(current)
        out = []
        for t,_ in items:
            if not cur or cur in _norm(t):
                out.append(t)
            if len(out) >= 25:
                break
        return [app_commands.Choice(name=s[:100], value=s[:100]) for s in out]

async def setup(bot):
    await bot.add_cog(SBCSolver(bot))
