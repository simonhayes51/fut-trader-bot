# futgg_scrape.py
import re, json, asyncio, aiohttp
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; FUTGG-SBCBot/2.0)"}
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
            if t and (":" in t or "rating" in t.lower() or "players" in t.lower()):
                out.append(t)
    # de-dup preserve order
    seen, uniq = set(), []
    for x in out:
        if x in seen: continue
        seen.add(x); uniq.append(x)
    return uniq

def _try_nuxt_json(soup: BeautifulSoup):
    # FUT.GG uses Nuxt; many pages include window.__NUXT__ with server state
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
            # common shape: ... { players: [ { name, rating/overall }, ... ] }
            if "players" in n and isinstance(n["players"], list):
                for o in n["players"]:
                    if isinstance(o, dict) and ("name" in o or "fullName" in o):
                        nm = o.get("name") or o.get("fullName")
                        rt = o.get("rating") or o.get("overall") or o.get("ovr") or 0
                        try: rt = int(rt)
                        except: rt = 0
                        if nm: players.append({"name": nm, "rating": rt})
            for v in n.values(): walk(v)
        elif isinstance(n, list):
            for v in n: walk(v)
    walk(data)
    # unique by name; keep first 11
    seen, out = set(), []
    for p in players:
        nm = (p.get("name") or "").strip()
        if not nm: continue
        key = nm.lower()
        if key in seen: continue
        seen.add(key); out.append(p)
        if len(out) >= 11: break
    return out

def _players_from_dom(soup: BeautifulSoup) -> list[dict]:
    players = []
    # table rows
    for row in soup.select("table tbody tr"):
        tds = row.select("td")
        if len(tds) < 2: continue
        name = tds[1].get_text(" ", strip=True)
        rat  = _num(tds[0].get_text(" ", strip=True))
        if name: players.append({"name": name, "rating": rat})
        if len(players) >= 11: break
    if len(players) >= 11: return players[:11]
    # card-ish
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
    # Walk up a few levels to find a section/card that likely owns this "View Solution"
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
    Robust to Player Picks: if only 'View Solution' links are present, we still build parts around them.
    """
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

    # De-dup by title
    seen, uniq = set(), []
    for p in parts:
        if p["title"] in seen: continue
        seen.add(p["title"]); uniq.append(p)

    # C) last resort: one generic part with any bullets found
    if not uniq:
        raw = _extract_text_list(soup)
        if raw:
            uniq = [{"title": "Requirements", "cost": 0, "requirements": raw, "solution_url": None}]
    return uniq

async def futgg_fetch_solution_players(session: aiohttp.ClientSession, solution_url: str):
    html = await fetch_html(session, solution_url)
    soup = BeautifulSoup(html, "html.parser")
    data = _try_nuxt_json(soup)

    # Look for "squad" or "squads" object in JSON
    if data:
        players = []
        def walk(n):
            if isinstance(n, dict):
                # common keys in squad-builder JSON
                if "squad" in n and isinstance(n["squad"], list):
                    for o in n["squad"]:
                        nm = o.get("name") or o.get("fullName")
                        rt = o.get("rating") or o.get("overall") or o.get("ovr")
                        try: rt = int(rt)
                        except: rt = 0
                        if nm: players.append({"name": nm, "rating": rt})
                if "players" in n and isinstance(n["players"], list):
                    for o in n["players"]:
                        nm = o.get("name") or o.get("fullName")
                        rt = o.get("rating") or o.get("overall") or o.get("ovr")
                        try: rt = int(rt)
                        except: rt = 0
                        if nm: players.append({"name": nm, "rating": rt})
                for v in n.values(): walk(v)
            elif isinstance(n, list):
                for v in n: walk(v)
        walk(data)

        # unique, keep 11 (or fewer if challenge < 11)
        seen, out = set(), []
        for p in players:
            nm = (p.get("name") or "").strip()
            if not nm: continue
            k = nm.lower()
            if k in seen: continue
            seen.add(k); out.append(p)
            if len(out) >= 11: break
        return out

    # fallback: old DOM parser
    return _players_from_dom(soup)[:11]