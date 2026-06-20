# src/osrs_planner/account/temple.py
"""TempleOSRS collection-log ingestion (design §5). Public API; live + cached.
Returns the OBTAINED clog item ids; 'missing' is computed by the consumer against
data/collection_log.json. IDs are KG-style 'item:<n>'."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

API = "https://templeosrs.com/api/collection-log/player_collection_log.php"
UA = "GildedTome/0.1 (account-state ingest; contact: retrogramx on github)"

def collection_log_url(player: str) -> str:
    return f"{API}?player={urllib.parse.quote(player)}&categories=all"

def parse_temple_clog(payload: dict) -> dict:
    data = payload.get("data") or {}
    obtained: set[str] = set()
    for _source, items in (data.get("items") or {}).items():
        for it in items or []:
            if (it.get("count") or 0) >= 1:
                obtained.add(f"item:{it['id']}")
    return {"obtained": obtained,
            "finished": data.get("total_collections_finished"),
            "available": data.get("total_collections_available"),
            "game_mode": data.get("game_mode"),
            "last_changed": data.get("last_changed")}

def _urllib_fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_collection_log(player: str, fetcher=_urllib_fetch) -> dict:
    return parse_temple_clog(fetcher(collection_log_url(player)))
