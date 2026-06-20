# src/osrs_planner/lootfilter/generate.py
"""Assemble the full iron .rs2f (design §3/§5). Generic (account_state=None) omits the
tailoring module and is the committed/byte-stable artifact; tailored is account-specific."""
from __future__ import annotations

import json, os
from osrs_planner.lootfilter import emit
from osrs_planner.lootfilter import tailor

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")

def load_clog_ids(data_dir: str = DATA) -> list[int]:
    recs = json.load(open(os.path.join(data_dir, "collection_log.json"), encoding="utf-8"))["records"]
    return sorted({r["item_id"] for r in recs})

def load_value_index(data_dir: str = DATA) -> dict:
    """item_id -> max(GE high price [skip the int-max sentinel], High-Alch), for the
    tailoring hide-owned high-value guard. Reads committed data only (ge_prices.json),
    no overlay import (boundary). `price` is a {high, low, capturedAt} dict."""
    recs = json.load(open(os.path.join(data_dir, "ge_prices.json"), encoding="utf-8"))["records"]
    out = {}
    for r in recs:
        ge = (r.get("price") or {}).get("high") or 0
        if ge >= 2_000_000_000:
            ge = 0
        out[r["item_id"]] = max(ge, r.get("high_alch") or 0)
    return out

def load_clog_rarity(data_dir: str = DATA) -> dict:
    """item_id -> 'ULTRA' or 'COMMON' rarity tier for the missing-clog beam intensity
    (everything else, incl. unsourced clue/pet/minigame items, defaults to RARE in tailor.py).
    best_rate = max drop_rate over a record AND its variants[]. ULTRA = best rate rarer than
    1/1000 OR any RAID source (drop_rates can't encode raid grind rarity -- a tbow's 1/34 chest
    roll is not its true rarity -- so raid source -> ULTRA without fabricating a number).
    COMMON = sourced and more common than 1/200, non-raid."""
    recs = json.load(open(os.path.join(data_dir, "drop_rates.json"), encoding="utf-8"))["records"]
    best, raid = {}, set()
    for r in recs:
        iid = r["item_id"]
        rates = [r["drop_rate"]] if r.get("drop_rate") is not None else []
        rates += [v["drop_rate"] for v in r.get("variants", []) if v.get("drop_rate") is not None]
        if rates:
            best[iid] = max(best.get(iid, 0.0), max(rates))
        if r.get("source_node_type") == "raid":
            raid.add(iid)
    out = {}
    for iid in set(best) | raid:
        rate = best.get(iid, 0.0)
        n = (1 / rate) if rate else None
        if iid in raid or (n is not None and n >= 1000):
            out[iid] = "ULTRA"
        elif n is not None and n < 200:
            out[iid] = "COMMON"
        # else -> RARE (the tailor default; includes unsourced ids absent from this map)
    return out

def generate_filter(account_state=None, data_dir: str = DATA, title=None, description=None) -> str:
    # default to the generic identity; a tailored build should pass a distinct title so the
    # plugin lists it as its OWN filter (it keys on meta.name -> avoids colliding with generic).
    title = title or "Gilded Tome — Iron"
    description = description or "Generated ironman loot filter. Value tiers + collection-log trophies."
    clog = load_clog_ids(data_dir)
    parts = [
        emit.emit_meta(title, description),
        emit.emit_preamble(),
        emit.emit_settings(),
    ]
    if account_state is not None:  # tailored: thread value (hide-owned guard) + rarity (beam intensity)
        parts.append(tailor.emit_tailoring(account_state, set(clog), value_index=load_value_index(data_dir),
                                           rarity_index=load_clog_rarity(data_dir)))
    parts += [emit.emit_trophies(clog), emit.emit_untradeables(), emit.emit_categories(),
              emit.emit_coins(), emit.emit_fallback()]
    return "\n".join(parts) + "\n"

def write_filter(path: str, account_state=None, data_dir: str = DATA, title=None, description=None) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_filter(account_state, data_dir, title, description))
