# data/parse_drop_rates.py
"""Build data/drop_rates.json from the committed dropsline raw cache.

Queries are by ITEM (the cache is {item_name: [dropsline rows]}); each row's
drop_json gives the real dropping source ("Dropped from", with an optional
#variant suffix), Rarity, and Rolls. One output record per (item_id, base
source). Source resolution sidesteps the collection log's fake "Slayer" bundle
(spec §5). Never fabricates (spec §2.4)."""
from __future__ import annotations

import json
import os
import sys

# repo root on path so `from data.X import ...` resolves BOTH when run as a script
# (`python data/parse_drop_rates.py` puts data/ on the path, not the root) AND under
# pytest (pyproject pythonpath="."). _toa_drop_rates (Task 5) imports the same way.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data._rarity_grammar import parse_rarity

DATA = os.path.dirname(os.path.abspath(__file__))

def split_source(dropped_from):
    """'Abyssal demon#Wilderness Slayer Cave' -> ('Abyssal demon', 'Wilderness Slayer Cave')."""
    if not dropped_from:
        return ("", None)
    base, _, variant = str(dropped_from).partition("#")
    return (base.strip(), variant.strip() or None)

def _status_for_no_rows(node_type):
    if node_type in ("minigame", "activity"):
        return "null-activity"
    return "null-not-in-bucket"

# Raid reward-chest source labels (dropsline names the CHEST, not the raid).
_RAID_CHESTS = {"Chest (Tombs of Amascut)", "Ancient chest", "Monumental chest"}
# Deterministic canonical pick (N3): prefer the plain/Standard/Regular variant.
_CANON_RANK = {None: 0, "Standard": 1, "Regular": 1, "Normal": 1}

def _is_superior(base):  # M6 — superior slayer monsters are a distinct source
    low = (base or "").lower()
    return low.startswith("greater ") or "superior" in low

def classify_node_type(base, clog_node):
    """Coarse v1 source classification (disclosed simplification): clue if a reward
    casket; raid if a known raid chest; else 'monster' (boss vs monster is not
    distinguished without a curated list -- a documented v1 limitation)."""
    if base.startswith("Reward casket"):
        return "clue"
    if base in _RAID_CHESTS:
        return "raid"
    return "monster"

def _null_record(item_id, item, source, node_type, status):
    return {"item_id": item_id, "item": item, "source": source,
            "source_node_type": node_type, "source_condition": None,
            "drop_rate": None, "drop_rate_raw": "", "rolls": 1,
            "drop_rate_status": status, "variants": []}

def build_records(clog_records, cache):
    """One record per (item_id, base source). NO input row is dropped (M6): every
    non-canonical row of a base -- alternate drop-table slots AND #variants -- lands
    in variants[]. Iterates per item_id, since a name can map to several ids (M5).
    Clue reward-casket sources are DEFERRED to v2 (spec §12): null + reason. Never
    fabricates. ToA canonical/scaling is layered on in Task 5 (apply_toa)."""
    # item_id -> (name, fallback clog node_type); a name may carry several ids (M5)
    by_id = {}
    for c in clog_records:
        by_id.setdefault(c["item_id"], (c["item"], c.get("node_type", "other")))
    out = []
    for item_id, (item_name, clog_node) in by_id.items():
        rows = cache.get(item_name) or []
        by_base = {}
        for row in rows:
            dj = row.get("drop_json") or {}
            base, variant = split_source(dj.get("Dropped from"))
            if base:
                by_base.setdefault(base, []).append((variant, dj))
        if not by_base:
            out.append(_null_record(item_id, item_name, "(unsourced)", clog_node,
                                    _status_for_no_rows(clog_node)))
            continue
        for base, entries in by_base.items():
            node_type = classify_node_type(base, clog_node)
            if base.startswith("Reward casket"):  # N2: clue caskets deferred (spec §12)
                out.append(_null_record(item_id, item_name, base, node_type,
                                        "null-clue-casket-deferred"))
                continue
            # N3: deterministic canonical (prefer plain/Standard/Regular, then name)
            entries = sorted(entries, key=lambda e: (_CANON_RANK.get(e[0], 2), e[0] or ""))
            _pv, dj = entries[0]
            rate, str_rolls, status = parse_rarity(dj.get("Rarity"))
            field_rolls = dj.get("Rolls")
            rolls = int(field_rolls) if isinstance(field_rolls, (int, float)) and field_rolls else str_rolls
            variants = []
            for variant, edj in entries[1:]:  # M6: keep EVERY other row, none dropped
                vrate, _vr, _vs = parse_rarity(edj.get("Rarity"))
                cond = variant if variant else "alternate drop-table slot"
                variants.append({"condition": cond, "drop_rate": vrate,
                                 "drop_rate_raw": str(edj.get("Rarity") or "")})
            out.append({
                "item_id": item_id, "item": item_name, "source": base,
                "source_node_type": node_type,
                "source_condition": "superior" if _is_superior(base) else None,
                "drop_rate": rate,
                "drop_rate_raw": str(dj.get("Rarity")) if status == "sourced" else "",
                "rolls": rolls, "drop_rate_status": status, "variants": variants,
            })
    out.sort(key=lambda r: (r["item_id"], r["source"]))
    return out

def load_clog():
    recs = json.load(open(os.path.join(DATA, "collection_log.json"), encoding="utf-8"))["records"]
    return recs

def write_dataset(records, path):
    sourced = sum(1 for r in records if r["drop_rate_status"] == "sourced")
    envelope = {
        "_provenance": {
            "domain": "drop_rates",
            "source_urls": ["https://oldschool.runescape.wiki/w/Module:DropsLine",
                            "https://oldschool.runescape.wiki/api.php (bucket dropsline)"],
            "license": "OSRS Wiki content CC BY-NC-SA 3.0",
            "accessed_at": "2026-06-19",
            "record_count": len(records),
            "sourced_count": sourced,
            "note": "Per-(item_id, source) rarity for collection-log items via Bucket dropsline. "
                    "Clue caskets + activity/minigame mostly null-by-reason (v1). ToA invocation-canonical.",
        },
        "records": records,
        "_excluded": [],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)

def main():
    clog = load_clog()
    cache = json.load(open(os.path.join(DATA, "raw", "dropsline_full.json"), encoding="utf-8"))
    records = build_records(clog, cache)
    write_dataset(records, os.path.join(DATA, "drop_rates.json"))
    print(f"drop_rates.json: {len(records)} records")

if __name__ == "__main__":
    main()
