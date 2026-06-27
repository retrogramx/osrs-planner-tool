#!/usr/bin/env python3
"""Source-grounding gate for the equipment-bonuses layer (data/items_equipment.json).

The dataset has multiple records per item_id (stat-variants + (beta) duplicates). For
each IN-SCOPE item (an equippable item-variant node already in kg/nodes.json), re-run
the selection rule and gate the corruption classes the 2026-06-25 audit found:
  - selected page is canonical (== item_dictionary page) and NOT a (beta) page;
  - exactly one record selected per item;
  - no all-zero stat block on a COMBAT slot (the empty-variant failure mode);
  - structural: 14 stat fields present + numeric; known slot; weapon slot MUST have a weapon block.
Exits non-zero on any violation.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                        # for kg_ingest.* (run standalone: script dir is on path, ROOT is not)
sys.path.insert(0, os.path.join(ROOT, "src"))   # for osrs_planner.* (imported by the builder module)
from kg_ingest.builders.equipment_bonuses import select_bonus_record  # noqa: E402

DICT = os.path.join(ROOT, "data", "item_dictionary.json")
EQUIP = os.path.join(ROOT, "data", "items_equipment.json")
NODES = os.path.join(ROOT, "kg", "nodes.json")
STAT_FIELDS = {"stab_attack_bonus","slash_attack_bonus","crush_attack_bonus","magic_attack_bonus","range_attack_bonus",
               "stab_defence_bonus","slash_defence_bonus","crush_defence_bonus","magic_defence_bonus","range_defence_bonus",
               "strength_bonus","ranged_strength_bonus","prayer_bonus","magic_damage_bonus"}
COMBAT_SLOTS = {"weapon","2h","body","head","legs","shield","hands","feet","cape"}
WEAPON_SLOTS = {"weapon","2h"}
KNOWN_SLOTS = COMBAT_SLOTS | {"ring","neck","ammo"}


def main() -> int:
    errors: list[str] = []
    with open(DICT, encoding="utf-8") as f:
        id2page = {r["item_id"]: r["page_name"] for r in json.load(f)["records"]}
    with open(EQUIP, encoding="utf-8") as f:
        eq = json.load(f)["records"]
    with open(NODES, encoding="utf-8") as f:
        nodes = json.load(f)
    by_id: dict[int, list[dict]] = defaultdict(list)
    for r in eq:
        if r.get("item_id") is not None:
            by_id[r["item_id"]].append(r)
    eq_ids = set(by_id)
    in_scope = sorted({int(n["id"].split(":", 1)[1]) for n in nodes
                       if n["id"].startswith("item:") and n["id"].split(":", 1)[1].isdigit()
                       and int(n["id"].split(":", 1)[1]) in eq_ids})

    for iid in in_scope:
        rec = select_bonus_record(by_id[iid], id2page.get(iid))
        tag = f"item:{iid}"
        if iid not in id2page:
            errors.append(f"[item] {tag} not in item_dictionary")
        if "(beta)" in (rec.get("page_name") or "").lower():
            errors.append(f"[beta] {tag} selected a (beta) page {rec.get('page_name')!r}")
        elif iid in id2page and rec.get("page_name") != id2page[iid]:
            errors.append(f"[page] {tag} selected page {rec.get('page_name')!r} != canonical {id2page[iid]!r}")
        stats = rec.get("stats") or {}
        missing = STAT_FIELDS - set(stats)
        if missing:
            errors.append(f"[stats] {tag} missing stat fields {sorted(missing)}")
        elif any(not isinstance(stats[k], (int, float)) for k in STAT_FIELDS):
            errors.append(f"[stats] {tag} has non-numeric stat value")
        elif (rec.get("slot") in COMBAT_SLOTS
              and all(stats[k] == 0 for k in STAT_FIELDS)
              and any(any((r.get("stats") or {}).get(k, 0) != 0 for k in STAT_FIELDS)
                      for r in by_id[iid])):
            # Only flag zero-stat if a non-zero record EXISTS for this item — that means
            # the selection rule picked the wrong variant (the empty-variant failure mode).
            # Items where ALL records are zero are genuinely cosmetic (aprons, skirts, etc.)
            # and are correctly represented with all-zero stats.
            errors.append(f"[zero] {tag} all-zero stat block on combat slot {rec.get('slot')!r} "
                          f"(non-zero variant exists — selection bug)")
        slot = rec.get("slot")
        if slot not in KNOWN_SLOTS:
            errors.append(f"[slot] {tag} unknown slot {slot!r}")
        # One-directional: weapon slot MUST have a weapon block; non-weapon slots MAY have a
        # spurious weapon block in the raw wiki data (e.g. Ring of recoil item:2550 carries
        # weapon_attack_speed=0 as a wiki artifact — relaxed from iff to avoid false positives).
        if slot in WEAPON_SLOTS and not rec.get("weapon"):
            errors.append(f"[weapon] {tag} slot={slot!r} but weapon block is absent")

    if errors:
        print(f"EQUIPMENT-BONUSES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        return 1
    print("EQUIPMENT-BONUSES VERIFICATION PASSED — all in-scope bonuses source-grounded.")
    print(f"  in-scope equippable items: {len(in_scope)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
