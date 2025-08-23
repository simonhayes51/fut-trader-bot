# cogs/sbcsolve.py
import os, re, time, json, difflib
import discord, aiohttp
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from sbc_core import build_indexes
from price_fetch_futbin import futbin_price_by_id
from futbin_cheapest import futbin_cheapest_by_rating, futbin_cheapest_special, normalize_platform_key
from futgg_scrape import futgg_fetch_sbc_parts, futgg_fetch_solution_players

PLAYERS_JSON   = os.getenv("PLAYERS_JSON", "players_temp.json")
FUTBIN_BASE    = "https://www.futbin.com"
FUTGG_BASE     = "https://www.fut.gg"
SBC_CACHE_TTL  = 600
UA             = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/2.0)"}

def _norm(s: str) -> str:
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"player ?pick", "pp", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _clean_title(t: str) -> str:
    return re.sub(r"[,\-–]\s*\d[\d,\.kK]+\s*(coins)?$", "", t.strip(), flags=re.I)

def _first_int(text: str) -> int:
    m = re.search(r"\b(\d{2,3})\b", text or "")
    return int(m.group(1)) if m else 0

class SBCSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.players = data if isinstance(data, list) else list(data.values())
        self.indexes = build_indexes(self.players)
        self._sbc_cache = {"items": [], "ts": 0.0}

    # ---------------- HTTP ----------------
    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(url, headers=UA, timeout=25) as r:
            r.raise_for_status()
            return await r.text()

    # ---------------- LIST SOURCES ----------------
    async def _fetch_futgg_sbc_list(self, session):
        html = await self.fetch_html(session, f"{FUTGG_BASE}/sbc/")
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.select('a[href^="/sbc/"]'):
            title = _clean_title(a.get_text(" ", strip=True))
            href = a.get("href") or ""
            if not title or href == "/sbc/": continue
            url = href if href.startswith("http") else f"{FUTGG_BASE}{href}"
            out.append((title, url))
        # de-dup/sort
        seen, uniq = set(), []
        for t,u in out:
            if (t,u) in seen: continue
            seen.add((t,u)); uniq.append((t,u))
        uniq.sort(key=lambda x: x[0].lower())
        return uniq

    async def _fetch_futbin_sbc_list(self, session):
        html = await self.fetch_html(session, f"{FUTBIN_BASE}/squad-building-challenges")
        soup = BeautifulSoup(html, "html.parser")
        out = []
        main = soup.select_one("#content") or soup
        for a in main.select("a[href*='/squad-building-challenges/']"):
            title = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            if not title or not href: continue
            if "?" in href: continue
            slug = href.split("/squad-building-challenges/")[-1].strip("/")
            if not slug: continue
            blocked = {
                "upgrades","players","icons","foundations","challenges","mode-mastery",
                "community-sbc-solutions","cheapest-player-by-rating","sbc-rating-combinations",
                "best-value-sbcs"
            }
            if slug.lower() in blocked: continue
            if not re.search(r"[-\d]", slug): continue
            url = href if href.startswith("http") else f"{FUTBIN_BASE}{href}"
            out.append((title, url))
        seen, uniq = set(), []
        for t,u in out:
            if (t,u) in seen: continue
            seen.add((t,u)); uniq.append((t,u))
        uniq.sort(key=lambda x: x[0].lower())
        return uniq

    async def get_sbc_list_cached(self, session, force: bool = False):
        now = time.time()
        if (not force) and self._sbc_cache["items"] and (now - self._sbc_cache["ts"] < SBC_CACHE_TTL):
            return self._sbc_cache["items"]
        items = []
        try: items = await self._fetch_futgg_sbc_list(session)
        except: items = []
        if not items:
            try: items = await self._fetch_futbin_sbc_list(session)
            except: items = []
        self._sbc_cache = {"items": items, "ts": now}
        return items

    # ---------------- MATCH ----------------
    def fuzzy_pick(self, items, query):
        if not items: return None, []
        qn = _norm(query)
        for t,u in items:
            if qn and qn in _norm(t): return (t,u), []
        norm_map = { _norm(t): (t,u) for t,u in items }
        best = difflib.get_close_matches(qn, list(norm_map.keys()), n=1, cutoff=0.4)
        sugg = difflib.get_close_matches(qn, list(norm_map.keys()), n=6, cutoff=0.3)
        picked = norm_map[best[0]] if best else None
        suggestions = [norm_map[s][0] for s in sugg if s in norm_map][:5]
        return picked, suggestions

    # ---------------- PARSE: ready-made XI on page (fallback for non-FUT.GG) ----------------
    def _parse_solution_from_url(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        # table first
        players = []
        for row in soup.select("table tbody tr"):
            tds = row.select("td")
            if len(tds) < 2: continue
            name = tds[1].get_text(" ", strip=True)
            rating = _first_int(tds[0].get_text(" ", strip=True))
            if name: players.append({"name": name, "rating": rating})
            if len(players) >= 11: break
        if len(players) >= 11:
            return players[:11]
        # card-ish
        for card in soup.select("[class*='player'], [class*='card'], [class*='squad']"):
            name = card.get("data-player-name") or card.get("data-name")
            rating = card.get("data-rating") or card.get("data-overall")
            if name:
                try: rating = int(rating)
                except: rating = 0
                players.append({"name": name.strip(), "rating": rating})
                if len(players) >= 11: break
        return players[:11]

    # ---------------- Build XI by basic requirement (rating + specials) ----------------
    async def _build_xi_rating_specials(self, session, platform: str, reqs: list[str]):
        """
        Minimal fallback builder: uses FUTBIN cheapest list(s).
        """
        # rating
        R = 0
        N = 11
        need_totw = 0
        need_tots = 0
        for line in reqs:
            m = (
                re.search(r"\b(min\.?|minimum)\s*(team\s*)?rating[: ]*\s*(\d{2,3})", line, re.I)
                or re.search(r"\bteam\s*rating[: ]*\s*(min\.?|minimum)?\s*(\d{2,3})", line, re.I)
                or re.search(r"\bsquad\s*rating[: ]*\s*(min\.?|minimum)?\s*(\d{2,3})", line, re.I)
                or re.search(r"\brating[: ]*\s*(min\.?|minimum)?\s*(\d{2,3})", line, re.I)
            )
            if m: R = max(R, int(m.group(m.lastindex)))
            m = re.search(r"(?:number\s*of\s*players|#\s*of\s*players\s*in\s*squad)\s*:\s*(\d+)", line, re.I)
            if m: N = int(m.group(1))
            if re.search(r"(totw|team\s*of\s*the\s*week)", line, re.I):
                mm = re.search(r"\bmin(?:imum)?\s*(\d+)", line, re.I)
                need_totw = max(need_totw, int(mm.group(1)) if mm else 1)
            if re.search(r"(tots|team\s*of\s*the\s*season|honourable\s*mentions|highlights)", line, re.I):
                mm = re.search(r"\bmin(?:imum)?\s*(\d+)", line, re.I)
                need_tots = max(need_tots, int(mm.group(1)) if mm else 1)

        if R == 0: R = 84
        platform = normalize_platform_key(platform)

        async def _map_price(name, default_rating):
            cands = self.indexes["by_name"].get(name.lower(), [])
            if not cands:
                surname = name.split()[-1].lower()
                keys = [k for k in self.indexes["by_name"].keys() if surname in k]
                cands = sum((self.indexes["by_name"][k] for k in keys), [])
            if cands:
                pid = cands[0]["pid"]
                price = await futbin_price_by_id(session, str(pid), platform)
                return {"name": name, "pid": pid, "rating": default_rating, "price": price}
            return {"name": name, "pid": None, "rating": default_rating, "price": 0}

        xi = []
        # specials first
        if need_totw:
            pool = await futbin_cheapest_special(session, "totw", min_rating=R, platform=platform, limit=max(need_totw*4, 8))
            for e in pool[:need_totw]:
                xi.append(await _map_price(e["name"], R))
        if need_tots:
            pool = await futbin_cheapest_special(session, "tots", min_rating=R, platform=platform, limit=max(need_tots*4, 8))
            for e in pool[:need_tots]:
                xi.append(await _map_price(e["name"], max(R, e.get("rating", R))))

        # fill
        remaining = max(0, N - len(xi))
        if remaining:
            cheap = await futbin_cheapest_by_rating(session, R, platform, limit=max(remaining*4, 20))
            seen = set(p["name"].lower() for p in xi)
            for e in cheap:
                if e["name"].lower() in seen: continue
                xi.append(await _map_price(e["name"], R))
                if len(xi) >= N: break

        while len(xi) < N and xi:
            xi.append({**xi[-1], "pid": None})

        total = sum(p.get("price", 0) or 0 for p in xi[:N])
        return xi[:N], total

    # ---------------- Command ----------------
    @app_commands.command(name="sbcsolve", description="Find SBC on FUT.GG, pull solution or build cheapest XI automatically")
    @app_commands.describe(sbcname="Start typing to autocomplete SBC name", platform="ps/xbox/pc")
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str | None = None, platform: str = "ps"):
        await interaction.response.defer(thinking=True)
        plat = normalize_platform_key(platform)

        async with aiohttp.ClientSession() as session:
            items = await self.get_sbc_list_cached(session)

            if not sbcname:
                embed = discord.Embed(title="Current SBCs", colour=discord.Colour.green())
                for t,u in items[:15]:
                    embed.add_field(name=t, value=f"[Open]({u})", inline=False)
                await interaction.followup.send(embed=embed)
                return

            pick, suggestions = self.fuzzy_pick(items, sbcname)
            if not pick:
                msg = f"No SBC found matching “{sbcname}”."
                if suggestions: msg += "\nDid you mean:\n• " + "\n• ".join(suggestions)
                await interaction.followup.send(msg); return

            title, link = pick

            # ---------------- FUT.GG primary path ----------------
            if "fut.gg" in link:
                parts = await futgg_fetch_sbc_parts(session, link)
                if parts:
                    embeds = []
                    for part in parts[:3]:   # keep output tidy
                        xi = []
                        # Try their solution first
                        if part.get("solution_url"):
                            try:
                                xi = await futgg_fetch_solution_players(session, part["solution_url"])
                            except Exception:
                                xi = []
                        if xi:
                            # optional: live price per player via futbin (can be heavy). We’ll show FUT.GG total instead.
                            total_txt = f"{part['cost']:,} coins" if part.get("cost") else "–"
                            e = discord.Embed(
                                title=f"{title} — {part['title']}",
                                description=f"Platform: {plat.upper()} • Source: FUT.GG solution",
                                colour=discord.Colour.green()
                            )
                            req_text = "\n".join(f"• {r}" for r in (part.get("requirements") or []))[:1024]
                            if req_text:
                                e.add_field(name="Requirements", value=req_text, inline=False)
                            e.add_field(name="Estimated Total", value=total_txt, inline=False)
                            lines = [f"{p.get('rating',0):>2} — {p['name']}" for p in xi]
                            e.add_field(name="XI", value="\n".join(lines)[:1024] or "—", inline=False)
                            if part.get("solution_url"):
                                e.set_footer(text="View Solution on FUT.GG")
                                e.url = part["solution_url"]
                            embeds.append(e)
                        else:
                            # Fallback: build basic XI from rating + specials
                            built_xi, total = await self._build_xi_rating_specials(session, plat, part.get("requirements") or [])
                            e = discord.Embed(
                                title=f"{title} — {part['title']}",
                                description=f"Platform: {plat.upper()} • Source: auto-build (rating & specials)",
                                colour=discord.Colour.blurple()
                            )
                            req_text = "\n".join(f"• {r}" for r in (part.get("requirements") or []))[:1024]
                            if req_text:
                                e.add_field(name="Requirements", value=req_text, inline=False)
                            e.add_field(name="Estimated Total", value=f"{(part.get('cost') or total):,} coins", inline=False)
                            lines = [f"{p.get('rating',0):>2} — {p['name']} • {p.get('price',0):,}" for p in built_xi]
                            e.add_field(name="Cheapest XI", value="\n".join(lines)[:1024] or "—", inline=False)
                            if part.get("solution_url"):
                                e.set_footer(text="No parsed XI; showed auto-build. View Solution on FUT.GG")
                                e.url = part["solution_url"]
                            embeds.append(e)

                    await interaction.followup.send(embeds=embeds)
                    return

            # ---------------- FUTBIN fallback path ----------------
            html = await self.fetch_html(session, link)
            players = self._parse_solution_from_url(html)
            if players:
                price_map = {}
                for p in players:
                    cands = self.indexes["by_name"].get(p["name"].lower(), [])
                    if not cands:
                        surname = p["name"].split()[-1].lower()
                        keys = [k for k in self.indexes["by_name"].keys() if surname in k]
                        cands = sum((self.indexes["by_name"][k] for k in keys), [])
                    p["pid"] = cands[0]["pid"] if cands else None
                    if p["pid"]:
                        price_map[p["pid"]] = await futbin_price_by_id(session, str(p["pid"]), plat)
                total = sum(price_map.get(p.get("pid"), 0) for p in players if p.get("pid"))
                embed = discord.Embed(title=f"SBC: {title}", description=f"Platform: {plat.upper()} (community XI)", colour=discord.Colour.green())
                embed.add_field(name="Estimated Total", value=f"{total:,} coins", inline=False)
                lines = []
                for p in players:
                    if p.get("pid"):
                        lines.append(f"{p.get('rating',0):>2} — {p['name']} • {price_map.get(p['pid'],0):,}")
                    else:
                        lines.append(f"{p.get('rating',0):>2} — {p['name']} • N/A")
                embed.add_field(name="XI", value="\n".join(lines)[:1024] or "—", inline=False)
                await interaction.followup.send(embed=embed)
                return

            await interaction.followup.send(f"Couldn't parse a solution or requirements for **{title}**.")
            return

    # ---------- Autocomplete (10-min cache) ----------
    @sbcsolve.autocomplete("sbcname")
    async def _sbcname_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            async with aiohttp.ClientSession() as session:
                items = await self.get_sbc_list_cached(session)
        except Exception:
            return []
        cur = _norm(current); out = []
        for t,_ in items:
            if not cur or cur in _norm(t):
                out.append(t)
            if len(out) >= 25: break
        return [app_commands.Choice(name=s[:100], value=s[:100]) for s in out]

async def setup(bot):
    await bot.add_cog(SBCSolver(bot))