# cogs/sbcsolve.py
import os, re, time, json, difflib
import discord, aiohttp
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from futgg_scrape import futgg_fetch_sbc_parts, futgg_fetch_solution_players

PLAYERS_JSON   = os.getenv("PLAYERS_JSON", "players_temp.json")  # kept in case you expand later
FUTGG_BASE     = "https://www.fut.gg"
SBC_CACHE_TTL  = 600
UA             = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/FUTGG-Only 1.0)"}

def _norm(s: str) -> str:
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"player ?pick", "pp", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _clean_title(t: str) -> str:
    return re.sub(r"[,\-–]\s*\d[\d,\.kK]+\s*(coins)?$", "", t.strip(), flags=re.I)

class SBCSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # (players file not strictly needed now; leaving for future enhancements)
        try:
            with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.players = data if isinstance(data, list) else list(data.values())
        except Exception:
            self.players = []
        self._sbc_cache = {"items": [], "ts": 0.0}

    # ---------------- HTTP ----------------
    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(url, headers=UA, timeout=25) as r:
            r.raise_for_status()
            return await r.text()

    # ---------------- LIST (FUT.GG) ----------------
    async def _fetch_futgg_sbc_list(self, session):
        html = await self.fetch_html(session, f"{FUTGG_BASE}/sbc/")
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.select('a[href^="/sbc/"]'):
            title = _clean_title(a.get_text(" ", strip=True))
            href = a.get("href") or ""
            if not title or href == "/sbc/":
                continue
            url = href if href.startswith("http") else f"{FUTGG_BASE}{href}"
            out.append((title, url))
        # de-dup/sort
        seen, uniq = set(), []
        for t, u in out:
            if (t, u) in seen: continue
            seen.add((t, u)); uniq.append((t, u))
        uniq.sort(key=lambda x: x[0].lower())
        return uniq

    async def get_sbc_list_cached(self, session, force: bool = False):
        now = time.time()
        if (not force) and self._sbc_cache["items"] and (now - self._sbc_cache["ts"] < SBC_CACHE_TTL):
            return self._sbc_cache["items"]
        try:
            items = await self._fetch_futgg_sbc_list(session)
        except Exception:
            items = []
        self._sbc_cache = {"items": items, "ts": now}
        return items

    # ---------------- MATCH ----------------
    def fuzzy_pick(self, items, query):
        if not items: return None, []
        qn = _norm(query)
        for t, u in items:
            if qn and qn in _norm(t): return (t, u), []
        norm_map = { _norm(t): (t, u) for t, u in items }
        best = difflib.get_close_matches(qn, list(norm_map.keys()), n=1, cutoff=0.4)
        sugg = difflib.get_close_matches(qn, list(norm_map.keys()), n=6, cutoff=0.3)
        picked = norm_map[best[0]] if best else None
        suggestions = [norm_map[s][0] for s in sugg if s in norm_map][:5]
        return picked, suggestions

    # ---------------- Command ----------------
    @app_commands.command(name="sbcsolve", description="Find SBC on FUT.GG and show requirements + XI from the View Solution")
    @app_commands.describe(sbcname="Start typing to autocomplete SBC name")
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str | None = None):
        await interaction.response.defer(thinking=True)

        async with aiohttp.ClientSession() as session:
            items = await self.get_sbc_list_cached(session)

            if not sbcname:
                embed = discord.Embed(title="Current SBCs (FUT.GG)", colour=discord.Colour.green())
                for t, u in items[:15]:
                    embed.add_field(name=t, value=f"[Open]({u})", inline=False)
                await interaction.followup.send(embed=embed)
                return

            pick, suggestions = self.fuzzy_pick(items, sbcname)
            if not pick:
                msg = f"No SBC found matching “{sbcname}”."
                if suggestions: msg += "\nDid you mean:\n• " + "\n• ".join(suggestions)
                await interaction.followup.send(msg); return

            title, link = pick
            parts = await futgg_fetch_sbc_parts(session, link)
            if not parts:
                await interaction.followup.send(f"Couldn't read details for **{title}**.")
                return

            embeds = []
            for part in parts[:3]:  # keep output tidy
                xi = []
                if part.get("solution_url"):
                    try:
                        xi = await futgg_fetch_solution_players(session, part["solution_url"])
                    except Exception:
                        xi = []

                e = discord.Embed(
                    title=f"{title} — {part['title']}",
                    description="Source: FUT.GG",
                    colour=discord.Colour.green() if xi else discord.Colour.blurple()
                )
                req_text = "\n".join(f"• {r}" for r in (part.get("requirements") or []))[:1024]
                if req_text:
                    e.add_field(name="Requirements", value=req_text, inline=False)

                total_txt = f"{part['cost']:,} coins" if part.get("cost") else "—"
                e.add_field(name="Estimated Total", value=total_txt, inline=False)

                if xi:
                    lines = [f"{p.get('rating',0):>2} — {p['name']}" for p in xi]
                    e.add_field(name="XI", value="\n".join(lines)[:1024] or "—", inline=False)
                else:
                    e.add_field(name="XI", value="— (couldn't read solution XI)", inline=False)

                if part.get("solution_url"):
                    e.set_footer(text="View Solution on FUT.GG")
                    e.url = part["solution_url"]

                embeds.append(e)

            await interaction.followup.send(embeds=embeds)

    # ---------- Autocomplete (10-min cache) ----------
    @sbcsolve.autocomplete("sbcname")
    async def _sbcname_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            async with aiohttp.ClientSession() as session:
                items = await self.get_sbc_list_cached(session)
        except Exception:
            return []
        cur = _norm(current); out = []
        for t, _ in items:
            if not cur or cur in _norm(t):
                out.append(t)
            if len(out) >= 25: break
        return [app_commands.Choice(name=s[:100], value=s[:100]) for s in out]

async def setup(bot):
    await bot.add_cog(SBCSolver(bot))