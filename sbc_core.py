from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple

def map_player(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pid": p.get("pid") or p.get("id") or p.get("defId"),
        "name": p.get("name") or p.get("Name"),
        "rating": int(p.get("rating") or p.get("ovr") or p.get("overall") or 0),
        "positions": p.get("positions") or p.get("basePossiblePositions") or p.get("Positions") or [],
        "nationId": p.get("nationId") or p.get("nation") or p.get("NATION_ID"),
        "leagueId": p.get("leagueId") or p.get("league") or p.get("LEAGUE_ID"),
        "clubId": p.get("clubId") or p.get("club") or p.get("CLUB_ID"),
        "rarity": (p.get("rarity") or p.get("PLAYER_RARITY") or "").upper(),
        "firstOwner": bool(p.get("firstOwner") or p.get("firstOwned")),
        "tradeable": bool(p.get("tradeable", True)) and not bool(p.get("untradeable", False)),
    }

def build_indexes(players: List[Dict[str, Any]]):
    by_id, by_name, by_rating = {}, defaultdict(list), defaultdict(list)
    for raw in players:
        pl = map_player(raw)
        if not pl["pid"]: continue
        by_id[pl["pid"]] = pl
        by_name[(pl["name"] or "").lower()].append(pl)
        by_rating[pl["rating"]].append(pl)
    return {"by_id": by_id, "by_name": by_name, "by_rating": by_rating}

def squad_chemistry(players: List[Dict[str, Any]]) -> Tuple[int, List[int]]:
    club = Counter(p["clubId"] for p in players if p)
    lig  = Counter(p["leagueId"] for p in players if p)
    nat  = Counter(p["nationId"] for p in players if p)
    per, total = [], 0
    for p in players:
        if not p: per.append(0); continue
        pts = 0
        for c in (club[p["clubId"]], lig[p["leagueId"]], nat[p["nationId"]]):
            if c >= 8: pts += 3
            elif c >= 5: pts += 2
            elif c >= 2: pts += 1
        pts = min(3, pts)
        per.append(pts); total += pts
    return total, per

def passes_requirement(players: List[Dict[str, Any]], req: Dict[str, Any]) -> bool:
    squad = [p for p in players if p]
    if req.get("min_players") and len(squad) < req["min_players"]: return False
    if req.get("min_rating"):
        avg = sum(p["rating"] for p in squad)/len(squad) if squad else 0
        if avg < req["min_rating"] - 2: return False
    if req.get("min_team_chem"):
        team_chem, _ = squad_chemistry(squad)
        if team_chem < req["min_team_chem"]: return False
    if req.get("min_nations") and len(set(p["nationId"] for p in squad)) < req["min_nations"]: return False
    if req.get("min_leagues") and len(set(p["leagueId"] for p in squad)) < req["min_leagues"]: return False
    if req.get("min_clubs")   and len(set(p["clubId"] for p in squad))   < req["min_clubs"]:   return False
    if req.get("min_rarity"):
        need = set(r.upper() for r in req["min_rarity"])
        have = sum(1 for p in squad if p["rarity"] in need)
        if have < req.get("rarity_count", 1): return False
    if req.get("first_owner_min"):
        if sum(1 for p in squad if p["firstOwner"]) < req["first_owner_min"]: return False
    if not req.get("allow_untradeable", True):
        if any(not p["tradeable"] for p in squad): return False
    if req.get("min_exact_positions"):
        need = req["min_exact_positions"][:]
        for p in squad:
            placed = False
            for i, pos in enumerate(need):
                if pos in (p["positions"] or []):
                    need.pop(i); placed = True; break
        if need: return False
    return True
