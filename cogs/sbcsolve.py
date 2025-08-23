# cogs/sbcsolve.py
import os, re, time, json, difflib
import discord, aiohttp
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from sbc_core import build_indexes
from price_fetch_futbin import futbin_price_by_id
from futbin_cheapest import futbin_cheapest_by_rating, futbin_cheapest_special

PLAYERS_JSON   = os.getenv("PLAYERS_JSON", "players_temp.json")
FUTBIN_BASE    = "https://www.futbin.com"
FUTGG_BASE     = "https://www.fut.gg"
SBC_CACHE_TTL  = 600
UA             = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.5)"}

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

    # ---------------- LIST (FUT.GG primary, FUTBIN fallback) ----------------
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

    # ---------------- PARSE: XI (when available) ----------------
    def _parse_solution_rows(self, soup):
        players = []
        for row in soup.select("table tbody tr"):
            cols = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cols) >= 2:
                name = cols[1]; rating = _first_int(cols[0])
                if name: players.append({"name": name, "rating": rating})
            if len(players) >= 11: break
        return players

    def _parse_solution_cards(self, soup):
        players = []
        for card in soup.select("[class*='player'], [class*='card'], [class*='squad']"):
            name = card.get("data-player-name") or card.get("data-name")
            rating = card.get("data-rating") or card.get("data-overall")
            if name:
                players.append({"name": name.strip(), "rating": int(rating) if str(rating).isdigit() else 0})
                if len(players) >= 11: break
                continue
            img = card.find("img", alt=True)
            if img and img.get("alt"):
                alt = img["alt"]; name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", alt)
                rating = _first_int(alt)
                if name_m:
                    players.append({"name": name_m.group(1).strip(), "rating": rating})
                    if len(players) >= 11: break
                    continue
            txt = card.get_text(" ", strip=True)
            name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", txt); rating = _first_int(txt)
            if name_m:
                players.append({"name": name_m.group(1).strip(), "rating": rating})
                if len(players) >= 11: break
        return players

    def _parse_solution_from_url(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        players = self._parse_solution_rows(soup)
        if len(players) < 11:
            players = self._parse_solution_cards(soup)
        return players[:11]

    # ---------------- PARSE: requirements (FUTBIN group/PP pages) ----------------
    def _parse_futbin_requirements(self, html: str):
        """
        Return [{"title": "...", "requirements": [lines...]}] for sub-challenges.
        Handles INFO bullets and Player Pick pages (plain <ul><li>).
        """
        soup = BeautifulSoup(html, "html.parser")
        parts = []
        containers = soup.select("section:has(h2), div.sbc_challenge, div.sbc_set, div.card") or soup.select("div")
        seen = set()
        for box in containers:
            # title
            title = None
            for sel in ["h2","h3","header h2",".title",".sbc-title",".card-title"]:
                h = box.select_one(sel)
                if h:
                    t = h.get_text(" ", strip=True)
                    if t and len(t) > 2 and not t.lower().startswith("requirements"):
                        title = t; break
            if not title:
                h = box.find(["strong","b"])
                if h: title = h.get_text(" ", strip=True)
            if not title: continue

            # requirements
            reqs = []
            head = None
            for tag in box.find_all(["h3","h4","strong","b","p","div"], string=True):
                if re.search(r"requirements", tag.get_text(" ", strip=True), re.I):
                    head = tag; break
            if head:
                cur = head.find_next()
                steps = 0
                while cur and steps < 8:
                    steps += 1
                    for li in cur.find_all("li"):
                        line = li.get_text(" ", strip=True)
                        if line: reqs.append(line)
                    for p in cur.find_all(["p","div"]):
                        line = p.get_text(" ", strip=True)
                        if line and any(sym in line for sym in ["•","★","–","- "]) and len(line) > 3:
                            reqs.append(line.lstrip("•★–- ").strip())
                    cur = cur.find_next_sibling()
            if not reqs:
                # Player Pick style: plain list
                for li in box.find_all("li"):
                    line = li.get_text(" ", strip=True)
                    if line and len(line) > 3: reqs.append(line)

            if not reqs: continue
            key = (title, tuple(reqs))
            if key in seen: continue
            seen.add(key)
            parts.append({"title": title, "requirements": reqs})

        # dedup by title
        final, seen_titles = [], set()
        for p in parts:
            if p["title"] in seen_titles: continue
            seen_titles.add(p["title"]); final.append(p)
        return final

    # ---------------- Build XI from requirements ----------------
    async def _build_xi_from_requirements(self, session, platform: str, req_lines: list[str]):
        """
        Enforces:
          - Squad Rating: Min R
          - # of players in squad: N (default 11)
          - Min TOTW / TOTS (best-effort via FUTBIN filters)
        Strategy:
          1) Take specials first (TOTW/TOTS) at rating ≥ R
          2) Fill remaining with cheapest R-rated players
          3) Always output N players
        """
        # --- parse requirements numbers (robust patterns) ---
        R = 0
        N = 11
        need_totw = 0
        need_tots = 0

        for line in req_lines:
            # rating (accepts: "Min. Team Rating: 85", "Team Rating: Min 85", "Squad Rating: 85", etc.)
            m = (
                re.search(r"\b(min\.?|minimum)\s*(team\s*)?rating[: ]*\s*(\d{2,3})", line, re.I)
                or re.search(r"\bteam\s*rating[: ]*\s*(min\.?|minimum)?\s*(\d{2,3})", line, re.I)
                or re.search(r"\bsquad\s*rating[: ]*\s*(min\.?|minimum)?\s*(\d{2,3})", line, re.I)
                or re.search(r"\brating[: ]*\s*(min\.?|minimum)?\s*(\d{2,3})", line, re.I)
            )
            if m:
                R = max(R, int(m.group(m.lastindex)))

            # squad size
            m = re.search(r"#\s*of\s*players\s*in\s*squad\s*:\s*(\d+)", line, re.I)
            if m:
                N = int(m.group(1))

            # TOTW/TOTS
            if re.search(r"(totw|team\s*of\s*the\s*week)", line, re.I):
                mm = re.search(r"\bmin(?:imum)?\s*(\d+)", line, re.I)
                need_totw = max(need_totw, int(mm.group(1)) if mm else 1)
            if re.search(r"(tots|team\s*of\s*the\s*season)", line, re.I):
                mm = re.search(r"\bmin(?:imum)?\s*(\d+)", line, re.I)
                need_tots = max(need_tots, int(mm.group(1)) if mm else 1)

        if R == 0: R = 84
        if N <= 0: N = 11

        async def map_with_live(entry, default_rating):
            nm = entry["name"]
            cands = self.indexes["by_name"].get(nm.lower(), [])
            if not cands:
                surname = nm.split()[-1].lower()
                keys = [k for k in self.indexes["by_name"].keys() if surname in k]
                cands = sum((self.indexes["by_name"][k] for k in keys), [])
            if cands:
                pid = cands[0]["pid"]
                live = await futbin_price_by_id(session, str(pid), platform)
                return {"name": nm, "pid": pid, "rating": entry.get("rating", default_rating), "price": live or entry.get("price", 0)}
            return {"name": nm, "pid": None, "rating": entry.get("rating", default_rating), "price": entry.get("price", 0)}

        xi = []
        # 1) specials first
        if need_totw:
            pool = await futbin_cheapest_special(session, "totw", min_rating=R, platform=platform, limit=max(need_totw*4, 8))
            for e in pool:
                xi.append(await map_with_live(e, R))
                if len(xi) >= need_totw: break

        if need_tots:
            pool = await futbin_cheapest_special(session, "tots", min_rating=R, platform=platform, limit=max(need_tots*4, 8))
            for e in pool:
                xi.append(await map_with_live(e, max(R, e.get("rating", R))))
                if len([p for p in xi if p]) >= need_totw + need_tots: break

        # 2) fill rest with cheapest at rating R
        remaining = max(0, N - len(xi))
        if remaining:
            cheap = await futbin_cheapest_by_rating(session, R, platform, limit=max(remaining*4, 15))
            seen = set(p["name"].lower() for p in xi)
            for e in cheap:
                if e["name"].lower() in seen: continue
                xi.append(await map_with_live(e, R))
                seen.add(e["name"].lower())
                if len(xi) >= N: break

        # 3) ensure N players exist (belt-and-braces)
        while len(xi) < N and xi:
            xi.append({**xi[-1], "pid": None})

        total = sum(p.get("price", 0) or 0 for p in xi)
        return xi[:N], total, {"min_rating": R, "players": N, "totw": need_totw, "tots": need_tots}

    # ---------------- Command ----------------
    @app_commands.command(name="sbcsolve", description="Find SBC, parse requirements, and post a cheapest valid XI")
    @app_commands.describe(sbcname="Start typing to autocomplete SBC name", platform="ps/xbox/pc")
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str | None = None, platform: str = "ps"):
        await interaction.response.defer(thinking=True)
        plat = (platform or "ps").lower().strip()

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
            html = await self.fetch_html(session, link)

            # 1) fast path: ready-made XI table on the page
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

            # 2) otherwise: parse requirements (FUTBIN group/PP pages) and auto-build XI
            parts = self._parse_futbin_requirements(html)
            if not parts:
                await interaction.followup.send(f"Couldn't parse a solution or requirements for **{title}**."); return

            # Build up to 3 parts to keep output tidy
            embeds = []
            for part in parts[:3]:
                xi, total, meta = await self._build_xi_from_requirements(session, plat, part["requirements"])
                e = discord.Embed(
                    title=f"{title} — {part['title']}",
                    description=f"Platform: {plat.upper()} • Min Rating {meta['min_rating']} • Players {meta['players']} • TOTW {meta['totw']} • TOTS {meta['tots']}",
                    colour=discord.Colour.green()
                )
                e.add_field(name="Requirements", value="\n".join(f"• {r}" for r in part["requirements"])[:1024] or "—", inline=False)
                e.add_field(name="Estimated Total", value=f"{total:,} coins", inline=False)
                lines = [f"{p['rating']:>2} — {p['name']} • {p.get('price',0):,}" for p in xi]
                e.add_field(name="Cheapest XI", value="\n".join(lines)[:1024] or "—", inline=False)
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
        for t,_ in items:
            if not cur or cur in _norm(t):
                out.append(t)
            if len(out) >= 25: break
        return [app_commands.Choice(name=s[:100], value=s[:100]) for s in out]

async def setup(bot):
    await bot.add_cog(SBCSolver(bot))