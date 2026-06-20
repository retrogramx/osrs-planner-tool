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

def generate_filter(account_state=None, data_dir: str = DATA) -> str:
    clog = load_clog_ids(data_dir)
    parts = [
        emit.emit_meta("Gilded Tome — Iron", "Generated ironman loot filter. Value tiers + collection-log trophies."),
        emit.emit_preamble(),
        emit.emit_settings(),
    ]
    if account_state is not None:  # tailored path: thread the value map so hide-owned spares valuables
        parts.append(tailor.emit_tailoring(account_state, set(clog), value_index=load_value_index(data_dir)))
    parts += [emit.emit_trophies(clog), emit.emit_categories(), emit.emit_fallback()]
    return "\n".join(parts) + "\n"

def write_filter(path: str, account_state=None, data_dir: str = DATA) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_filter(account_state, data_dir))
