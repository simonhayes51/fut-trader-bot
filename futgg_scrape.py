# futgg_scrape.py
import re, json, asyncio, aiohttp
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; FUTGG-SBCBot/1.1)"}
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
    async with SEM, session.get(url, headers=UA, timeout=25) as r:
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
            if t and (":" in t or "Rating" in t or "players" in t.lower()):
                out.append(t)
    seen, uniq = set(), []
    for x in out:
        if x in seen: continue
        seen.add(x); uniq.append(x)
    return uniq

def _try_nuxt_json(soup: BeautifulSoup):
    for s in soup.find_all("script"):
        txt = s.string or s.get_text() or ""
        if "__NUXT__" in txt:
            m = re.search(r"__NUXT__\s*=\s*(\{.*\})\s*;?", txt, re.S)
            if not m: continue
            try:
                return json.loads(m.group(1))
            except Exception:
                continue
    return None

def _players_from_nuxt(data) -> list[dict]:
    players = []
    def walk(n):
        if isinstance(n, dict):
            if "players" in n and isinstance(n["players"], list):
                for o in n["players"]:
                    if isinstance(o, dict) and ("name" in o or "fullName" in o):
                        nm = o.get("name") or o.get("fullName")
                        rt = o.get("rating") or o.get("overall") or o.get("ovr") or 0
                        players.append({"name": nm, "rating": int(rt) if str(rt).isdigit() else 0})
            for v in n.values(): walk(v)
        elif isinstance(n, list):
            for v in n: walk(v)
    walk(data)
    seen, out = set(), []
    for p in players:
        nm = (p.get("name") or "").strip()
        if not nm: continue
        k = nm.lower()
        if k in seen: continue
        seen.add(k); out.append(p)
        if len(out) >= 11: break
    return out

def _players_from_dom(soup: BeautifulSoup) -> list[dict]:
    players = []
    for row in soup.select("table tbody tr"):
        tds = row.select("td")
        if len(tds) < 2: continue
        name = tds[1].get_text(" ", strip=True)
        rat  = _num(tds[0].get_text(" ", strip=True))
        if name: players.append({"name": name, "rating": rat})
        if len(players) >= 11: break
    if len(players) >= 11: return players[:11]
    for card in soup.select("[class*='card'], [class*='player']"):
        name = card.get("data-name") or card.get("data-player-name")
        rating = card.get("data-rating") or card.get("data-overall")
        if name:
            try: r = int(rating)
            except: r = 0
            players.append({"name": name, "rating": r})
            if len(players) >= 11: break
    return players[:11]

def _closest_part_container(a):
    # Walk up to find a section that contains a heading & price
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
    """
    Returns: [{"title","cost","requirements","solution_url"}]
    More robust for Player Picks: scans any 'View Solution' link and climbs to its card.
    """
    html = await fetch_html(session, sbc_url)
    soup = BeautifulSoup(html, "html.parser")
    parts = []

    # Strategy A: direct card scan (works on most SBCs)
    cards = soup.select("section,article,div")
    for c in cards:
        title = None
        for hsel in ("h2","h3",".title",".sbc-title",".card-title"):
            h = c.select_one(hsel)
            if h:
                t = h.get_text(" ", strip=True)
                if t and re.search(r"(squad|rated|challenge|pick)", t, re.I):
                    title = t; break
        if not title: continue
        # cost near coin icon / number
        cost = 0
        price_node = c.find(string=re.compile(r"\d[\d,\.]+\s*(fut)?", re.I))
        if price_node:
            cost = _num(str(price_node))
        # requirements
        reqs = _extract_text_list(c)
        # solution link
        sol = None
        a = c.find("a", string=re.compile(r"view\s+solution", re.I)) or c.find("a", href=re.compile(r"/squad-builder/"))
        if a and a.get("href"):
            href = a["href"]
            sol = href if href.startswith("http") else f"https://www.fut.gg{href}"
        if reqs or sol:
            parts.append({"title": title, "cost": cost, "requirements": reqs, "solution_url": sol})

    # Strategy B: links-first (Player Picks)
    for a in soup.find_all("a", href=re.compile(r"/squad-builder/")):
        container, title = _closest_part_container(a)
        if not title:  # fall back to link text if nothing else
            title = a.get_text(" ", strip=True) or "SBC Part"
        cost = 0
        reqs = _extract_text_list(container) if container else []
        href = a["href"]
        sol = href if href.startswith("http") else f"https://www.fut.gg{href}"
        part = {"title": title, "cost": cost, "requirements": reqs, "solution_url": sol}
        if part not in parts:
            parts.append(part)

    # Deduplicate by title
    seen, uniq = set(), []
    for p in parts:
        if p["title"] in seen: continue
        seen.add(p["title"]); uniq.append(p)

    # If still nothing, return a basic single part with raw bullets
    if not uniq:
        raw_reqs = _extract_text_list(soup)
        if raw_reqs:
            uniq = [{"title": "Requirements", "cost": 0, "requirements": raw_reqs, "solution_url": None}]
    return uniq

async def futgg_fetch_solution_players(session: aiohttp.ClientSession, solution_url: str):
    html = await fetch_html(session, solution_url)
    soup = BeautifulSoup(html, "html.parser")
    data = _try_nuxt_json(soup)
    if data:
        pl = _players_from_nuxt(data)
        if pl: return pl[:11]
    return _players_from_dom(soup)[:11]