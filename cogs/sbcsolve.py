# cogs/sbcsolve.py
import discord, aiohttp, asyncio, json, os, re, difflib, time
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from sbc_core import build_indexes, map_player
from price_fetch_futbin import futbin_price_by_id

PLAYERS_JSON = os.getenv("PLAYERS_JSON", "players_temp.json")
FUTBIN_BASE = "https://www.futbin.com"
SBC_CACHE_TTL = 600  # 10 minutes
UA = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.0)"}

def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"player ?pick", "pp", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

class SBCSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.players = data if isinstance(data, list) else list(data.values())
        self.indexes = build_indexes(self.players)
        self._sbc_cache = {"items": [], "ts": 0.0}

    async def fetch_html(self, session, url: str) -> str:
        async with session.get(url, headers=UA, timeout=25) as r:
            r.raise_for_status()
            return await r.text()

    async def _fetch_futbin_sbc_list(self, session):
        html = await self.fetch_html(session, f"{FUTBIN_BASE}/squad-building-challenges")
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for a in soup.select("a.sbc_title"):
            title = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            url = href if href.startswith("http") else f"{FUTBIN_BASE}{href}"
            if title and href:
                items.append((title, url))
        if not items:
            for a in soup.select("a[href*='/squad-building-challenges/']"):
                title = a.get_text(" ", strip=True)
                href = a.get("href") or ""
                url = href if href.startswith("http") else f"{FUTBIN_BASE}{href}"
                if title and href:
                    items.append((title, url))
        # de-dup and sort A→Z
        seen, out = set(), []
        for t, u in items:
            if (t, u) in seen: continue
            seen.add((t, u)); out.append((t, u))
        out.sort(key=lambda x: x[0].lower())
        return out

    async def get_sbc_list_cached(self, session, force: bool = False):
        now = time.time()
        if not force and self._sbc_cache["items"] and (now - self._sbc_cache["ts"] < SBC_CACHE_TTL):
            return self._sbc_cache["items"]
        items = await self._fetch_futbin_sbc_list(session)
        self._sbc_cache = {"items": items, "ts": now}
        return items

    def fuzzy_pick(self, items, query):
        if not items: return None, []
        norm_map = { _norm(t): (t, u) for t, u in items }
        norm_titles = list(norm_map.keys())
        qn = _norm(query)
        # substring first
        for t, u in items:
            if qn and qn in _norm(t):
                return (t, u), []
        # difflib fallback
        best = difflib.get_close_matches(qn, norm_titles, n=1, cutoff=0.4)
        sugg = difflib.get_close_matches(qn, norm_titles, n=6, cutoff=0.3)
        picked = norm_map[best[0]] if best else None
        suggestions = [norm_map[s][0] for s in sugg if s in norm_map][:5]
        return picked, suggestions

    def parse_solution_from_futbin(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        players = []
        for row in soup.select("table tbody tr"):
            cols = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cols) >= 2:
                name = cols[1]
                rat_m = re.search(r"\b(\d{2,3})\b", cols[0] or "")
                rating = int(rat_m.group(1)) if rat_m else 0
                if name:
                    players.append({"name": name, "rating": rating})
            if len(players) >= 11: break
        if len(players) < 11:
            for card in soup.select("[class*='player'], [class*='squad']"):
                txt = card.get_text(" ", strip=True)
                name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", txt)
                rat_m  = re.search(r"\b(\d{2,3})\b", txt)
                if name_m:
                    players.append({"name": name_m.group(1).strip(), "rating": int(rat_m.group(1)) if rat_m else 0})
                if len(players) >= 11: break
        return players[:11]

    # ---------- AUTOCOMPLETE ----------
    @sbcsolve.autocomplete  # type: ignore  # this decorator is added after definition below
    async def _sbc_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            async with aiohttp.ClientSession() as session:
                items = await self.get_sbc_list_cached(session)
        except Exception:
            return []
        cur = _norm(current)
        # filter by substring (normed), return up to 25 choices
        matches = []
        for t, _ in items:
            if not cur or cur in _norm(t):
                matches.append(t)
            if len(matches) >= 25:
                break
        return [app_commands.Choice(name=name[:100], value=name[:100]) for name in matches]

    # ---------- COMMAND ----------
    @app_commands.command(name="sbcsolve", description="List active SBCs or solve by name")
    @app_commands.describe(sbcname="Start typing to autocomplete SBC name", platform="ps/xbox/pc")
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str | None = None, platform: str = "ps"):
        await interaction.response.defer(thinking=True)
        plat = platform.lower().strip()

        async with aiohttp.ClientSession() as session:
            items = await self.get_sbc_list_cached(session)

            # If no name provided, list
            if not sbcname:
                embed = discord.Embed(title="Current SBCs (FUTBIN)", colour=discord.Colour.green())
                for t, u in items[:15]:
                    embed.add_field(name=t, value=f"[Open]({u})", inline=False)
                await interaction.followup.send(embed=embed)
                return

            pick, suggestions = self.fuzzy_pick(items, sbcname)
            if not pick:
                msg = f"No SBC found matching “{sbcname}”."
                if suggestions:
                    msg += "\nDid you mean:\n• " + "\n• ".join(suggestions)
                await interaction.followup.send(msg)
                return

            title, link = pick
            html = await self.fetch_html(session, link)
            players = self.parse_solution_from_futbin(html)
            if not players:
                await interaction.followup.send(f"Couldn't parse a solution for **{title}**.")
                return

            # Map to your JSON and price via FUTBIN
            price_map = {}
            for p in players:
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

# attach the autocomplete after the command is created (discord.py quirk)
def setup_autocomplete(cog: SBCSolver):
    # bind method to command parameter
    for cmd in cog.bot.tree.get_commands():
        if isinstance(cmd, app_commands.Command) and cmd.name == "sbcsolve":
            param = cmd.parameters.get("sbcname")
            if param:
                param.autocomplete = cog._sbc_autocomplete

async def setup(bot):
    cog = SBCSolver(bot)
    await bot.add_cog(cog)
    # ensure autocomplete is wired after command is registered
    setup_autocomplete(cog)