# src/osrs_planner/lootfilter/generate.py
"""Assemble the full iron .rs2f (design §3/§5). Generic (account_state=None) omits the
tailoring module and is the committed/byte-stable artifact; tailored is account-specific."""
from __future__ import annotations

import json, os, sys
from osrs_planner.lootfilter import emit
from osrs_planner.lootfilter import tailor

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")
ROOT = os.path.dirname(DATA)   # repo root -- for the lazy kg_ingest import in load_gear_records

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

def load_recommended_ids(data_dir: str = DATA) -> list[int]:
    recs = json.load(open(os.path.join(data_dir, "recommended_equipment.json"), encoding="utf-8"))["records"]
    return sorted({r["item_id"] for r in recs})

def load_rare_ids(data_dir: str = DATA, floor: float = 1 / 512) -> list[int]:
    recs = json.load(open(os.path.join(data_dir, "drop_rates.json"), encoding="utf-8"))["records"]
    rare = set()
    for r in recs:
        rate = r.get("drop_rate")
        if rate is not None and rate <= floor:
            rare.add(r["item_id"])
    return sorted(rare)

def load_gear_records(data_dir: str = DATA) -> list[dict]:
    """One deduped {item_id, slot, stats} record per gear-family item_id (controller amendment 2).

    items_equipment.json carries MULTIPLE records per item_id (stat-variant / (beta)-page trap --
    the same selection trap documented for build_loot_families.py's equipment_families()). A naive
    "include every eq record whose item_id is a gear-family member" would put the SAME item_id into
    MULTIPLE emit_gear slot/tier buckets (once per variant record). Select ONE canonical record via
    select_bonus_record -- the same selector build_equipment_bonuses/equipment_families use --
    instead of re-deriving that logic."""
    from collections import defaultdict
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)   # kg_ingest isn't packaged with osrs_planner (src-only wheel)
    from kg_ingest.builders.equipment_bonuses import select_bonus_record
    from osrs_planner.lootfilter import categories
    fams = categories.families_by_id(data_dir)
    eq = json.load(open(os.path.join(data_dir, "items_equipment.json"), encoding="utf-8"))["records"]
    dict_recs = json.load(open(os.path.join(data_dir, "item_dictionary.json"), encoding="utf-8"))["records"]
    canonical_pages = {r["item_id"]: r["page_name"] for r in dict_recs}
    by_id = defaultdict(list)
    for r in eq:
        iid = r.get("item_id")
        if iid is not None and fams.get(iid) == "gear":
            by_id[iid].append(r)
    out = []
    for iid in sorted(by_id):
        rec = select_bonus_record(by_id[iid], canonical_pages.get(iid))
        out.append({"item_id": iid, "slot": rec["slot"], "stats": rec["stats"]})
    return out

def load_family_ids(data_dir: str = DATA) -> dict:
    from collections import defaultdict
    from osrs_planner.lootfilter import categories
    out = defaultdict(list)
    for iid, fam in categories.families_by_id(data_dir).items():
        out[fam].append(iid)
    return dict(out)

def generate_filter(account_state=None, data_dir: str = DATA, title=None, description=None) -> str:
    # default to the generic identity; a tailored build should pass a distinct title so the
    # plugin lists it as its OWN filter (it keys on meta.name -> avoids colliding with generic).
    title = title or "Gilded Tome — Iron"
    description = description or "Generated ironman loot filter. Value tiers + collection-log trophies."
    clog = load_clog_ids(data_dir)
    # FilterScape/loot-filters-ui requires the FIRST token to be a module declaration, so settings
    # leads and the meta{} block goes LAST (the parser regex-scans meta from anywhere in the file).
    # module order (§8, controller amendment 1 -- categories stays, right after families): settings
    # -> custom -> [tailoring if account_state] -> notable -> trophies -> gear -> families ->
    # categories -> untradeables -> coins -> fallback -> meta.
    parts = [emit.emit_settings(), emit.emit_custom_highlights()]
    if account_state is not None:  # tailored: thread value (hide-owned guard) + rarity (beam intensity)
        parts.append(tailor.emit_tailoring(account_state, set(clog), value_index=load_value_index(data_dir),
                                           rarity_index=load_clog_rarity(data_dir)))
    parts += [emit.emit_notable(load_recommended_ids(data_dir), load_rare_ids(data_dir)),
              emit.emit_trophies(clog),
              emit.emit_gear(load_gear_records(data_dir)),
              emit.emit_families(load_family_ids(data_dir)),
              emit.emit_categories(),      # KEEP: hand-authored name-glob families (potion sub-liquids,
                                           # teleport, charged_jewellery, essence, planks) -- no data signal
              emit.emit_untradeables(), emit.emit_coins(), emit.emit_fallback(),
              emit.emit_meta(title, description)]
    return "\n".join(parts) + "\n"

def write_filter(path: str, account_state=None, data_dir: str = DATA, title=None, description=None) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_filter(account_state, data_dir, title, description))
