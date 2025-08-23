# futgg_scrape.py
import re, json, asyncio, aiohttp
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; FUTGG-SBCBot/1.0)"}
SEM = asyncio.Semaphore(4)

def _num(txt: str) -> int:
    if not txt:
        return 0
    t = txt.lower().strip()
    t = t.replace(",", "")
    m = re.search(r"(\d[\d,\.]*)", t)
    if not m:
        return 0
    raw = m.group(1)
    if raw.endswith("k"):
        try:
            return int(float(raw[:-1]) * 1000)
        except:
            return 0
    try:
        return int(float(raw))
    except:
        return 0

async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    async with SEM, session.get(url, headers=UA, timeout=25) as r:
        r.raise_for_status()
        return await r.text()

def _extract_text_list(container) -> list[str]:
    out = []
    # bullet <li>
    for li in container.find_all("li"):
        t = li.get_text(" ", strip=True)
        if t:
            out.append(t)
    # fallback: short paragraphs/divs that look like requirements
    if not out:
        for p in container.find_all(["p", "div"]):
            t = p.get_text(" ", strip=True)
            if t and (":" in t or "Rating" in t or "players" in t.lower()):
                out.append(t)
    # unique, preserve order
    seen, uniq = set(), []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq

def _try_nuxt_json(soup: BeautifulSoup):
    """
    FUT.GG is a Nuxt app. Many pages include a JSON blob in a script tag like:
    <script>window.__NUXT__ = {...}</script>
    We attempt to parse it because it usually has the squad/players arrays.
    """
    for s in soup.find_all("script"):
        txt = s.string or s.get_text() or ""
        if "__NUXT__" in txt and "{" in txt:
            # pull the first { ... } after =
            m = re.search(r"__NUXT__\s*=\s*(\{.*\})\s*;?", txt, re.S)
            if not m:
                continue
            try:
                data = json.loads(m.group(1))
                return data
            except Exception:
                continue
    return None

def _players_from_nuxt(data) -> list[dict]:
    """
    Best-effort extraction of players from Nuxt state. We look for arrays with
    objects that have "name" and maybe "rating"/"overall".
    """
    players = []

    def walk(node):
        nonlocal players
        if isinstance(node, dict):
            # common keys
            if "players" in node and isinstance(node["players"], list):
                for obj in node["players"]:
                    if isinstance(obj, dict) and ("name" in obj or "fullName" in obj):
                        nm = obj.get("name") or obj.get("fullName")
                        rt = obj.get("rating") or obj.get("overall") or obj.get("ovr") or 0
                        players.append({"name": nm, "rating": int(rt) if str(rt).isdigit() else 0})
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    # unique by name, keep first
    seen, out = set(), []
    for p in players:
        if not p.get("name"):
            continue
        key = p["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out[:11]

def _players_from_dom(soup: BeautifulSoup) -> list[dict]:
    players = []
    # generic table
    for row in soup.select("table tbody tr"):
        tds = row.select("td")
        if len(tds) < 2:
            continue
        name = tds[1].get_text(" ", strip=True)
        rat = _num(tds[0].get_text(" ", strip=True))
        if name:
            players.append({"name": name, "rating": rat})
        if len(players) >= 11:
            break
    if len(players) >= 11:
        return players[:11]
    # card-like
    for card in soup.select("[class*='card'], [class*='player']"):
        name = card.get("data-name") or card.get("data-player-name")
        rating = card.get("data-rating") or card.get("data-overall")
        if name:
            try:
                r = int(rating)
            except:
                r = 0
            players.append({"name": name, "rating": r})
        if len(players) >= 11:
            break
    if players:
        return players[:11]
    # ultimate fallback: any text that looks like a name with rating near it
    txt = soup.get_text(" ", strip=True)
    possible = re.findall(r"([A-Z][A-Za-z .'-]{2,})\s+(?:\(|\[)?(\d{2,3})(?:\)|\])?", txt)
    for nm, r in possible:
        players.append({"name": nm.strip(), "rating": int(r)})
        if len(players) >= 11:
            break
    return players[:11]

async def futgg_fetch_sbc_parts(session: aiohttp.ClientSession, sbc_url: str):
    """
    Returns a list of parts like:
    [{"title": "...", "cost": 110050, "requirements": [...], "solution_url": "https://www.fut.gg/25/squad-builder/..."}]
    """
    html = await fetch_html(session, sbc_url)
    soup = BeautifulSoup(html, "html.parser")

    parts = []
    # each part card: has a header (title), a cost number, bullets (requirements), and a "View Solution" link
    cards = soup.select("section,article,div")
    for c in cards:
        title = None
        for hsel in ("h2","h3",".title",".sbc-title",".card-title"):
            h = c.select_one(hsel)
            if h:
                t = h.get_text(" ", strip=True)
                if t and re.search(r"\b(squad|challenge|rated)\b", t, re.I):
                    title = t
                    break
        if not title:
            continue

        # Displayed total
        cost = 0
        price_node = c.find(string=re.compile(r"\d[\d,\.]+\s*(fut)?", re.I))
        if price_node:
            cost = _num(str(price_node))

        # Requirements bullets
        reqs = _extract_text_list(c)

        # View Solution link
        sol = None
        a = c.find("a", string=re.compile(r"view\s+solution", re.I))
        if not a:
            a = c.find("a", href=re.compile(r"/squad-builder/"))
        if a and a.get("href"):
            href = a["href"]
            sol = href if href.startswith("http") else f"https://www.fut.gg{href}"

        # Heuristic to ensure we only collect real SBC part cards
        if not reqs and not sol:
            continue

        parts.append({
            "title": title,
            "cost": cost,
            "requirements": reqs,
            "solution_url": sol
        })

    # De-dupe by title
    seen, uniq = set(), []
    for p in parts:
        if p["title"] in seen:
            continue
        seen.add(p["title"])
        uniq.append(p)
    return uniq

async def futgg_fetch_solution_players(session: aiohttp.ClientSession, solution_url: str):
    """
    Returns list of {"name":..., "rating": int} for the XI on the squad-builder page.
    """
    html = await fetch_html(session, solution_url)
    soup = BeautifulSoup(html, "html.parser")

    # 1) Nuxt JSON (best)
    data = _try_nuxt_json(soup)
    if data:
        players = _players_from_nuxt(data)
        if players:
            return players

    # 2) DOM fallback
    return _players_from_dom(soup)