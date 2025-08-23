# cogs/sbcsolve.py
import os, re, time, json, difflib
import discord, aiohttp
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from sbc_core import build_indexes
from price_fetch_futbin import futbin_price_by_id
from futbin_cheapest import futbin_cheapest_by_rating

# ------------ Config ------------
PLAYERS_JSON    = os.getenv("PLAYERS_JSON", "players_temp.json")
FUTBIN_BASE     = "https://www.futbin.com"
FUTGG_BASE      = "https://www.fut.gg"
SBC_CACHE_TTL   = 600  # 10 minutes
UA              = {"User-Agent": "Mozilla/5.0 (compatible; SBCSolver/1.2)"}

# ------------ Helpers ------------
def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"player ?pick", "pp", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _clean_title(t: str) -> str:
    # FUT.GG cards sometimes include trailing price (e.g., ", 6,300")
    t = re.sub(r"[,\-–]\s*\d[\d,\.kK]+\s*(coins)?$", "", t.strip(), flags=re.I)
    return t.strip()

def _is_futgg(url: str) -> bool:
    return "fut.gg" in (url or "")

def _first_int(text: str) -> int:
    m = re.search(r"\b(\d{2,3})\b", text or "")
    return int(m.group(1)) if m else 0

# ------------ Cog ------------
class SBCSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # load players json
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
            title = _clean_title(a.get_text(" ", strip=True))
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
        for t,u in items:
            if qn and qn in _norm(t):
                return (t,u), []
        norm_map = { _norm(t): (t,u) for t,u in items }
        norm_titles = list(norm_map.keys())
        best = difflib.get_close_matches(qn, norm_titles, n=1, cutoff=0.4)
        sugg = difflib.get_close_matches(qn, norm_titles, n=6, cutoff=0.3)
        picked = norm_map[best[0]] if best else None
        suggestions = [norm_map[s][0] for s in sugg if s in norm_map][:5]
        return picked, suggestions

    # ----- Solution parsers -----
    def _parse_rows(self, soup):
        players = []
        for row in soup.select("table tbody tr"):
            cols = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cols) >= 2:
                name = cols[1]
                rating = _first_int(cols[0])
                if name:
                    players.append({"name": name, "rating": rating})
            if len(players) >= 11: break
        return players

    def _parse_cards(self, soup):
        players = []
        for card in soup.select("[class*='player'], [class*='card'], [class*='squad']"):
            name = card.get("data-player-name") or card.get("data-name")
            rating = card.get("data-rating") or card.get("data-overall")
            if name:
                players.append({"name": name.strip(), "rating": int(rating) if rating and str(rating).isdigit() else 0})
                if len(players) >= 11: break
                continue
            img = card.find("img", alt=True)
            if img and img.get("alt"):
                alt = img["alt"]
                name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", alt)
                rating = _first_int(alt)
                if name_m:
                    players.append({"name": name_m.group(1).strip(), "rating": rating})
                    if len(players) >= 11: break
                    continue
            txt = card.get_text(" ", strip=True)
            name_m = re.search(r"([A-Za-z][A-Za-z .'-]{2,})", txt)
            rating = _first_int(txt)
            if name_m:
                players.append({"name": name_m.group(1).strip(), "rating": rating})
                if len(players) >= 11: break
        return players

    def _parse_solution_from_futgg(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        players = self._parse_rows(soup)
        if len(players) < 11:
            players = self._parse_cards(soup)
        return players[:11]

    def _parse_solution_from_futbin(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        players = self._parse_rows(soup)
        if len(players) < 11:
            players = self._parse_cards(soup)
        return players[:11]

    # ----- FUTBIN requirements (group SBCs) -----
    def _parse_futbin_requirements(self, html: str):
        """
        Gather sub-challenges and their bullet requirements from group SBC pages
        like /25/squad-building-challenge/<id>.
        """
        soup = BeautifulSoup(html, "html.parser")
        parts = []

        containers = []
        containers += soup.select("section:has(h2), div.sbc_challenge, div.sbc_set, div.card")
        if not containers:
            containers = soup.select("div")

        seen = set()
        for box in containers:
            # Title guess
            title = None
            for sel in ["h2", "h3", "header h2", ".title", ".sbc-title", ".card-title"]:
                h = box.select_one(sel)
                if h:
                    t = h.get_text(" ", strip=True)
                    if t and len(t) > 2 and not t.lower().startswith("requirements"):
                        title = t
                        break
            if not title:
                sb = box.find(["strong", "b"])
                if sb:
                    title = sb.get_text(" ", strip=True)
            if not title:
                continue

            # Find requirements near a label
            reqs = []
            req_head = None
            for tag in box.find_all(["h3","h4","strong","b","p","div"], string=True):
                txt = tag.get_text(" ", strip=True)
                if re.search(r"requirements", txt, re.I):
                    req_head = tag
                    break
            if req_head:
                container = req_head.find_next()
                steps = 0
                while container and steps < 8:
                    steps += 1
                    for li in container.find_all("li"):
                        line = li.get_text(" ", strip=True)
                        if line: reqs.append(line)
                    for p in container.find_all(["p","div"]):
                        line = p.get_text(" ", strip=True)
                        if line and any(sym in line for sym in ["•","★","–","- "]) and len(line) > 3:
                            reqs.append(line.lstrip("•★–- ").strip())
                    container = container.find_next_sibling()
            if not reqs:
                for li in box.select("li"):
                    line = li.get_text(" ", strip=True)
                    if line and len(line) > 3: reqs.append(line)
                if not reqs:
                    for p in box.select("p"):
                        line = p.get_text(" ", strip=True)
                        if line and ("Squad Rating" in line or "players" in line or ":" in line):
                            reqs.append(line)

            if not reqs: 
                continue
            key = (title, tuple(reqs))
            if key in seen: 
                continue
            seen.add(key)
            parts.append({"title": title, "requirements": reqs})

        # de-dup by title
        final, seen_titles = [], set()
        for p in parts:
            if p["title"] in seen_titles: 
                continue
            seen_titles.add(p["title"])
            final.append(p)
        return final

    # ----- Build cheapest XI from requirements (rating-only for now) -----
    async def _build_xi_for_part(self, session, platform: str, reqs: list[str]):
        """
        Reads a list of requirement lines, detects min squad rating and returns
        a cheapest XI list: [{"name","pid","rating","price"}...]
        using FUTBIN cheapest-by-rating pages + your JSON mapping.
        """
        # detect min rating
        min_rating = 0
        for line in reqs:
            m = re.search(r"rating[: ]+min[^\d]*(\d{2,3})", line, re.I)
            if m:
                try: min_rating = int(m.group(1)); break
                except: pass
        if min_rating == 0:
            min_rating = 84  # sane default

        # pull cheapest list for that rating
        cheap = await futbin_cheapest_by_rating(session, min_rating, platform, limit=20)
        if not cheap:
            return []

        # pick first 11 distinct names, map to your JSON for IDs, fetch live price
        xi = []
        used = set()
        for entry in cheap:
            nm = entry["name"]
            if nm.lower() in used: 
                continue
            used.add(nm.lower())

            cands = self.indexes["by_name"].get(nm.lower(), [])
            if not cands:
                # surname fallback
                surname = nm.split()[-1].lower()
                keys = [k for k in self.indexes["by_name"].keys() if surname in k]
                cands = sum((self.indexes["by_name"][k] for k in keys), [])

            if not cands:
                xi.append({"name": nm, "pid": None, "rating": min_rating, "price": entry["price"]})
            else:
                pid = cands[0]["pid"]
                live = await futbin_price_by_id(session, str(pid), platform)
                xi.append({"name": nm, "pid": pid, "rating": min_rating, "price": live or entry["price"]})

            if len(xi) >= 11:
                break

        return xi

    # ----- Command -----
    @app_commands.command(name="sbcsolve", description="List active SBCs or solve by name (optionally a sub-part)")
    @app_commands.describe(
        sbcname="Start typing to autocomplete SBC name",
        part="Optional: sub-challenge title (e.g., '94-Rated Squad')",
        platform="ps/xbox/pc"
    )
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str | None = None, part: str | None = None, platform: str = "ps"):
        await interaction.response.defer(thinking=True)
        plat = (platform or "ps").lower().strip()

        async with aiohttp.ClientSession() as session:
            items = await self.get_sbc_list_cached(session)

            # List mode
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

            # Try to parse a ready-made solution XI
            if _is_futgg(link):
                players = self._parse_solution_from_futgg(html)
            else:
                players = self._parse_solution_from_futbin(html)

            # If no XI, try group requirements (FUTBIN pages)
            if not players and not _is_futgg(link):
                parts = self._parse_futbin_requirements(html)
                if parts:
                    # If user provided `part`, try to build a quick XI for that sub-challenge
                    if part:
                        # find the requested sub-part
                        pick_part = None
                        for p in parts:
                            if _norm(part) in _norm(p["title"]):
                                pick_part = p; break
                        if not pick_part:
                            # show available parts
                            embed = discord.Embed(
                                title=f"SBC Requirements: {title}",
                                description="Pick one of the parts shown below (use the `part:` option).",
                                colour=discord.Colour.blurple()
                            )
                            for p in parts[:6]:
                                embed.add_field(name=p["title"], value="\n".join(f"• {r}" for r in p["requirements"])[:1024], inline=False)
                            await interaction.followup.send(embed=embed)
                            return

                        # Build XI for that part (rating-only for now)
                        xi = await self._build_xi_for_part(session, plat, pick_part["requirements"])
                        if not xi:
                            await interaction.followup.send(f"Found part **{pick_part['title']}**, but couldn't build a XI.")
                            return

                        total = sum(x["price"] or 0 for x in xi)
                        embed = discord.Embed(
                            title=f"SBC: {title} — {pick_part['title']}",
                            description=f"Platform: {plat.upper()}  •  (rating-only auto XI)",
                            colour=discord.Colour.green()
                        )
                        req_text = "\n".join(f"• {r}" for r in pick_part["requirements"])[:1024]
                        embed.add_field(name="Requirements", value=req_text or "—", inline=False)

                        lines = []
                        for x in xi:
                            lines.append(f"{x['rating']:>2} — {x['name']} • {x['price']:,}" if x.get("price") else f"{x['rating']:>2} — {x['name']}")
                        embed.add_field(name="XI (auto-built)", value="\n".join(lines)[:1024] or "—", inline=False)
                        embed.add_field(name="Estimated Total", value=f"{total:,} coins", inline=True)
                        embed.set_footer(text="Note: extra constraints (league/nation/club) not enforced yet.")
                        await interaction.followup.send(embed=embed)
                        return

                    # no part requested → show requirements list
                    embed = discord.Embed(
                        title=f"SBC Requirements: {title}",
                        description="Parsed from FUTBIN (INFO view).",
                        colour=discord.Colour.blurple()
                    )
                    for p in parts[:6]:
                        req_text = "\n".join(f"• {r}" for r in p["requirements"])[:1024] or "—"
                        embed.add_field(name=p["title"], value=req_text, inline=False)
                    embed.set_footer(text="Tip: rerun with the `part:` option to generate a cheapest XI.")
                    await interaction.followup.send(embed=embed)
                    return

            # If we did find players (community/AI solution), map to IDs and price
            if players:
                price_map = {}
                for p in players:
                    cands = self.indexes["by_name"].get(p["name"].lower(), [])
                    if not cands:
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
                await interaction.followup.send(embed=embed)
                return

            # Fallback: nothing parsed
            await interaction.followup.send(f"Couldn't parse a solution for **{title}**.")
            return

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