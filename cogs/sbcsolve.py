import discord, aiohttp, asyncio, json, os, re, difflib
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from sbc_core import build_indexes, map_player
from price_fetch_futbin import futbin_price_by_id

PLAYERS_JSON = os.getenv("PLAYERS_JSON", "players_temp.json")
FUTBIN_BASE = "https://www.futbin.com"

def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"player ?pick", "pp", s)  # common alias
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

    async def fetch_html(self, session, url: str) -> str:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25) as r:
            r.raise_for_status()
            return await r.text()

    async def get_futbin_sbc_list(self, session):
        html = await self.fetch_html(session, f"{FUTBIN_BASE}/squad-building-challenges")
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # Primary selector (works on FUTBIN today)
        for a in soup.select("a.sbc_title"):
            title = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            url = href if href.startswith("http") else f"{FUTBIN_BASE}{href}"
            if title and href:
                items.append((title, url))

        # Fallback (in case FUTBIN tweaks classes)
        if not items:
            for a in soup.select("a[href*='/squad-building-challenges/']"):
                title = a.get_text(" ", strip=True)
                href = a.get("href") or ""
                url = href if href.startswith("http") else f"{FUTBIN_BASE}{href}"
                if title and href:
                    items.append((title, url))

        # De-dup
        seen, out = set(), []
        for t, u in items:
            if (t, u) in seen: continue
            seen.add((t, u)); out.append((t, u))
        return out

    def fuzzy_pick(self, items, query):
        """Return best (title,url) and up to 5 suggestion titles."""
        if not items: return None, []
        titles = [t for t, _ in items]
        norm_map = { _norm(t): (t, u) for t, u in items }
        norm_titles = list(norm_map.keys())
        qn = _norm(query)

        # Prefer substring matches first
        for t, u in items:
            if qn and qn in _norm(t):
                return (t, u), []

        # Fuzzy fallback
        best = difflib.get_close_matches(qn, norm_titles, n=1, cutoff=0.4)
        sugg = difflib.get_close_matches(qn, norm_titles, n=6, cutoff=0.3)
        picked = norm_map[best[0]] if best else None
        suggestions = [norm_map[s][0] for s in sugg if s in norm_map][:5]
        return picked, suggestions

    def parse_solution_from_futbin(self, html: str):
        """Try to read the first community/AI solution XI."""
        soup = BeautifulSoup(html, "html.parser")
        players = []

        # Most common: table rows
        for row in soup.select("table tbody tr"):
            cols = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cols) >= 2:
                name = cols[1]
                rat_m = re.search(r"\b(\d{2,3})\b", cols[0] or "")
                rating = int(rat_m.group(1)) if rat_m else 0
                if name:
                    players.append({"name": name, "rating": rating})
            if len(players) >= 11: break

        # Fallback: any card-like blocks with rating + name
        if len(players) < 11:
            for card in soup.select("[class*='player'], [class*='squad']"):
                txt = card.get_text(" ", strip=True)
                name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", txt)
                rat_m  = re.search(r"\b(\d{2,3})\b", txt)
                if name_m:
                    players.append({"name": name_m.group(1).strip(), "rating": int(rat_m.group(1)) if rat_m else 0})
                if len(players) >= 11: break

        return players[:11]

    @app_commands.command(name="sbcsolve", description="List active SBCs or solve by name")
    @app_commands.describe(sbcname="SBC name (leave blank to list current SBCs)", platform="ps/xbox/pc")
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str | None = None, platform: str = "ps"):
        await interaction.response.defer(thinking=True)
        plat = platform.lower().strip()

        async with aiohttp.ClientSession() as session:
            sbc_list = await self.get_futbin_sbc_list(session)

            # If no name provided, list current SBCs
            if not sbcname:
                embed = discord.Embed(title="Current SBCs (FUTBIN)", colour=discord.Colour.green())
                for t, u in sbc_list[:15]:
                    embed.add_field(name=t, value=f"[Open]({u})", inline=False)
                await interaction.followup.send(embed=embed)
                return

            pick, suggestions = self.fuzzy_pick(sbc_list, sbcname)
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
                msg = f"Couldn't parse a solution for **{title}**. Try another SBC."
                await interaction.followup.send(msg)
                return

            # Map names to your JSON (FUTBIN IDs) and fetch live prices
            price_map = {}
            for p in players:
                cands = self.indexes["by_name"].get(p["name"].lower(), [])
                if not cands:
                    # surname fallback
                    surname = p["name"].split()[-1].lower()
                    keys = [k for k in self.indexes["by_name"].keys() if surname in k]
                    cands = sum((self.indexes["by_name"][k] for k in keys), [])
                if cands:
                    best = cands[0]
                    p["pid"] = best["pid"]
                else:
                    p["pid"] = None

            for p in players:
                if not p.get("pid"): continue
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

async def setup(bot):
    await bot.add_cog(SBCSolver(bot))
