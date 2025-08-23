# sbc_core.py
from collections import defaultdict
from typing import List, Dict, Any

def map_player(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pid": p.get("pid") or p.get("id") or p.get("defId"),
        "name": p.get("name") or p.get("Name"),
        "rating": int(p.get("rating") or p.get("ovr") or p.get("overall") or 0),
        # Optional pretty names if your JSON includes them (used later if you expand constraints)
        "league_name": (p.get("leagueName") or p.get("league_name") or p.get("league") or ""),
        "nation_name": (p.get("nationName") or p.get("nation_name") or p.get("nation") or ""),
        "club_name":   (p.get("clubName")   or p.get("club_name")   or p.get("club")   or ""),
    }

def build_indexes(players: List[Dict[str, Any]]):
    by_name = defaultdict(list)
    for raw in players:
        pl = map_player(raw)
        if not pl["pid"] or not pl["name"]: continue
        by_name[(pl["name"] or "").lower()].append(pl)
    return {"by_name": by_name}