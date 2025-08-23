# futgg_scrape.py
import re, json, asyncio, aiohttp
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; FUTGG-SBCBot/2.5)"}
SEM = asyncio.Semaphore(4)

def _num(txt: str) -> int:
    if not txt: return 0
    t = txt.lower().replace(",", "").strip()
    m = re.search(r"\d[\d\.kK]*", t)
    if not m: return 0
    raw = m.group(0)
    if raw.endswith(("k","K")):
        try: return int(float(raw[:-1]) * 1000)
        except: return 0
    try: return int(float(raw))
    except: return 0

async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    async with SEM, session.get(url, headers=UA, timeout=30) as r:
        r.raise_for_status()
        return await r.text()

def _extract_text_list(node) -> list[str]:
    out = []
    for li in node.find_all("li"):
        t = li.get_text(" ", strip=True)
        if t: out.append(t)
    if not out:
        for p in node.find_all(["p","div","span"]):
            t = p.get_text(" ", strip=True)
            if t and (":" in t or "rating" in t.lower() or "players" in t.lower()):
                out.append(t)
    seen, uniq = set(), []
    for x in out:
        if x in seen: continue
        seen.add(x); uniq.append(x)
    return uniq

# =============== JSON scraping helpers ===============

def _script_json_blobs(soup: BeautifulSoup) -> list[dict]:
    blobs = []

    # A) window.__NUXT__ = { ... }
    for s in soup.find_all("script"):
        txt = s.string or s.get_text() or ""
        if "__NUXT__" in txt:
            m = re.search(r"__NUXT__\s*=\s*(\{.*?\})\s*;?\s*$", txt, re.S)
            if not m:
                # sometimes followed by more code; grab the first balanced-ish {}
                m = re.search(r"__NUXT__\s*=\s*(\{.*\})", txt, re.S)
            if m:
                raw = m.group(1)
                # crude attempt to trim trailing semicolons
                raw = re.sub(r";\s*$", "", raw)
                try:
                    blobs.append(json.loads(raw))
                except Exception:
                    pass

    # B) <script type="application/json">...</script>
    for s in soup.find_all("script", attrs={"type": re.compile("json", re.I)}):
        txt = (s.string or s.get_text() or "").strip()
        if not txt: continue
        try:
            blobs.append(json.loads(txt))
        except Exception:
            pass

    # C) Last-ditch: any large {...} in scripts
    for s in soup.find_all("script"):
        txt = s.string or s.get_text() or ""
        if not txt or "{" not in txt: continue
        m = re.search(r"(\{.*\})", txt, re.S)
        if not m: continue
        candidate = m.group(1)
        candidate = re.sub(r";\s*$", "", candidate)
        try:
            blobs.append(json.loads(candidate))
        except Exception:
            # try just the innermost braces
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    blobs.append(json.loads(candidate[start:end+1]))
                except Exception:
                    pass
    return blobs

def _coerce_int(x):
    try: return int(x)
    except: return 0

def _append_unique(players, name: str, rating: int, ps=0, xbox=0, pc=0):
    if not name: return
    key = name.strip().lower()
    if any(p["name"].strip().lower() == key for p in players):
        return
    players.append({"name": name.strip(), "rating": rating, "ps": ps, "xbox": xbox, "pc": pc})

def _walk_for_players(node, out):
    """
    Collect players from:
      - {"player": {...}, "price"/"prices": {...}}
      - {"players": [...]}
      - {"squad": [...] or {"players": [...]}}
      - flat objects with {"name","rating/overall/ovr"}
    """
    if isinstance(node, dict):
        # explicit player + price
        if "player" in node and isinstance(node["player"], dict):
            pl = node["player"]
            nm = pl.get("name") or pl.get("fullName") or pl.get("shortName")
            rt = pl.get("rating") or pl.get("overall") or pl.get("ovr") or 0
            pr = node.get("price") or node.get("prices") or {}
            ps = pr.get("ps") or pr.get("ps5") or pr.get("ps4") or 0
            xb = pr.get("xbox") or pr.get("xb") or 0
            pc = pr.get("pc") or pr.get("computer") or 0
            if nm:
                _append_unique(out, nm, _coerce_int(rt), _coerce_int(ps), _coerce_int(xb), _coerce_int(pc))

        # players list
        if "players" in node and isinstance(node["players"], list):
            for obj in node["players"]:
                if isinstance(obj, dict):
                    if "player" in obj and isinstance(obj["player"], dict):
                        pl = obj["player"]
                        nm = pl.get("name") or pl.get("fullName") or pl.get("shortName")
                        rt = pl.get("rating") or pl.get("overall") or pl.get("ovr") or 0
                        pr = obj.get("price") or obj.get("prices") or {}
                        ps = pr.get("ps") or pr.get("ps5") or pr.get("ps4") or 0
                        xb = pr.get("xbox") or pr.get("xb") or 0
                        pc = pr.get("pc") or pr.get("computer") or 0
                        if nm:
                            _append_unique(out, nm, _coerce_int(rt), _coerce_int(ps), _coerce_int(xb), _coerce_int(pc))
                    else:
                        nm = obj.get("name") or obj.get("fullName") or obj.get("shortName")
                        rt = obj.get("rating") or obj.get("overall") or obj.get("ovr") or 0
                        if nm:
                            _append_unique(out, nm, _coerce_int(rt))

        # squad container
        if "squad" in node:
            sq = node["squad"]
            if isinstance(sq, list):
                for obj in sq: _walk_for_players(obj, out)
            elif isinstance(sq, dict):
                _walk_for_players(sq, out)

        # flat object with name+rating
        if "name" in node and any(k in node for k in ("rating","overall","ovr")):
            nm = node.get("name") or node.get("fullName") or node.get("shortName")
            rt = node.get("rating") or node.get("overall") or node.get("ovr") or 0
            if nm:
                _append_unique(out, nm, _coerce_int(rt))

        for v in node.values():
            _walk_for_players(v, out)

    elif isinstance(node, list):
        for v in node:
            _walk_for_players(v, out)

def _players_from_json_blobs(blobs: list[dict]) -> list[dict]:
    players = []
    for b in blobs:
        _walk_for_players(b, players)
        if len(players) >= 11: break
    return players[:11]

# last-ditch DOM parser
def _players_from_dom(soup: BeautifulSoup) -> list[dict]:
    players = []
    # tables
    for row in soup.select("table tbody tr"):
        tds = row.select("td")
        if len(tds) < 2: continue
        name = tds[1].get_text(" ", strip=True)
        rat  = _num(tds[0].get_text(" ", strip=True))
        if name: _append_unique(players, name, rat)
        if len(players) >= 11: break
    if players: return players[:11]
    # cards
    for card in soup.select("[class*='card'], [class*='player']"):
        name = card.get("data-name") or card.get("data-player-name")
        rating = card.get("data-rating") or card.get("data-overall")
        if name:
            _append_unique(players, name, _coerce_int(rating))
            if len(players) >= 11: break
    return players[:11]

# raw HTML regex fallback for minified JSON
def _players_from_raw_regex(html: str) -> list[dict]:
    """
    Find patterns like: "name":"Toni Kroos"...(<=150 chars)..."rating":90 (or "overall"/"ovr")
    """
    players = []
    # allow up to 150 chars between name and rating
    pattern = re.compile(
        r'"name"\s*:\s*"([^"]{2,})"[^}{]{0,150}?"(?:rating|overall|ovr)"\s*:\s*(\d{2,3})',
        re.I | re.S
    )
    for m in pattern.finditer(html):
        nm = m.group(1).strip()
        rt = _coerce_int(m.group(2))
        if not nm: continue
        _append_unique(players, nm, rt)
        if len(players) >= 11: break
    return players

# =============== Public API ===============

def _closest_part_container(a):
    cur = a
    for _ in range(6):
        cur = cur.parent
        if not cur: break
        title = None
        for sel in ("h2","h3",".title",".sbc-title",".card-title"):
            h = cur.select_one(sel)
            if h:
                t = h.get_text(" ", strip=True)
                if t and len(t) > 2:
                    title = t; break
        if title:
            return cur, title
    return None, None

async def futgg_fetch_sbc_parts(session: aiohttp.ClientSession, sbc_url: str):
    html = await fetch_html(session, sbc_url)
    soup = BeautifulSoup(html, "html.parser")
    parts = []

    # A) normal cards
    for c in soup.select("section,article,div"):
        title = None
        for hsel in ("h2","h3",".title",".sbc-title",".card-title"):
            h = c.select_one(hsel)
            if h:
                t = h.get_text(" ", strip=True)
                if t and re.search(r"(squad|rated|challenge|pick)", t, re.I):
                    title = t; break
        if not title: continue
        cost = 0
        price_node = c.find(string=re.compile(r"\d[\d,\.]+\s*(fut)?", re.I))
        if price_node: cost = _num(str(price_node))
        reqs = _extract_text_list(c)
        sol = None
        a = c.find("a", string=re.compile(r"view\s+solution", re.I)) or c.find("a", href=re.compile(r"/squad-builder/"))
        if a and a.get("href"):
            href = a["href"]; sol = href if href.startswith("http") else f"https://www.fut.gg{href}"
        if reqs or sol:
            parts.append({"title": title, "cost": cost, "requirements": reqs, "solution_url": sol})

    # B) links-first (helps Player Picks)
    for a in soup.find_all("a", href=re.compile(r"/squad-builder/")):
        container, title = _closest_part_container(a)
        if not title: title = a.get_text(" ", strip=True) or "SBC Part"
        cost = 0
        reqs = _extract_text_list(container) if container else []
        href = a["href"]
        sol = href if href.startswith("http") else f"https://www.fut.gg{href}"
        part = {"title": title, "cost": cost, "requirements": reqs, "solution_url": sol}
        if part not in parts:
            parts.append(part)

    seen, uniq = set(), []
    for p in parts:
        if p["title"] in seen: continue
        seen.add(p["title"]); uniq.append(p)

    if not uniq:
        raw = _extract_text_list(soup)
        if raw:
            uniq = [{"title": "Requirements", "cost": 0, "requirements": raw, "solution_url": None}]
    return uniq

async def futgg_fetch_solution_players(session: aiohttp.ClientSession, solution_url: str):
    html = await fetch_html(session, solution_url)
    soup = BeautifulSoup(html, "html.parser")

    # 1) Any JSON blobs we can find
    blobs = _script_json_blobs(soup)
    players = _players_from_json_blobs(blobs)
    if players:
        return players[:11]

    # 2) Raw HTML regex (minified JSON inline)
    players = _players_from_raw_regex(html)
    if players:
        return players[:11]

    # 3) DOM fallback (rare)
    return _players_from_dom(soup)[:11]