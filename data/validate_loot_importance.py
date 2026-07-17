#!/usr/bin/env python3
"""Structural gate for data/loot_importance.json (editorial base tiers). Violations -> exit 1."""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
from osrs_planner.lootfilter.categories import categorize
CAT_ID_TO_FAMILY = {"ores": "ore", "bars": "bar", "runes": "rune", "ammo": "ammo", "gems": "gem",
    "essence": "essence", "herbs": "herb", "logs": "log", "planks": "plank", "food": "food",
    "seeds": "seed", "bones": "bones"}
GRADES = {"SS", "S", "A", "B", "C", "D", "E"}
RANKED = {"herb", "rune", "ore", "bar", "log", "seed", "bones", "ammo", "food", "essence", "gem", "plank"}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(HERE, "loot_importance.json"))
    ap.add_argument("--data", default=HERE)
    ns = ap.parse_args()
    data = json.load(open(ns.file, encoding="utf-8"))
    recs = data["records"]
    idict = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "item_dictionary.json"), encoding="utf-8"))["records"]}
    fam_of = {r["item_id"]: r["family"] for r in json.load(open(os.path.join(ns.data, "loot_families.json"), encoding="utf-8"))["records"]}
    errors, seen = [], set()
    if data.get("_provenance", {}).get("kind") != "editorial":
        errors.append("provenance.kind must be 'editorial'")
    for r in recs:
        iid = r.get("item_id")
        if iid not in idict:
            errors.append(f"{iid}: not in item_dictionary")
        if iid in seen:
            errors.append(f"{iid}: duplicate")
        seen.add(iid)
        if r.get("base_tier") not in GRADES:
            errors.append(f"{iid}: bad base_tier {r.get('base_tier')!r}")
        if r.get("family") not in RANKED:
            errors.append(f"{iid}: family {r.get('family')!r} not a ranked family")
        if not r.get("rationale"):
            errors.append(f"{iid}: missing rationale")
        justified = set()
        if iid in fam_of:
            justified.add(fam_of[iid])
        c = categorize(r.get("name", ""))
        if c and c["id"] in CAT_ID_TO_FAMILY:
            justified.add(CAT_ID_TO_FAMILY[c["id"]])
        if justified and r.get("family") not in justified:
            errors.append(f"{iid}: family {r.get('family')!r} justified by neither loot_families "
                          f"{fam_of.get(iid)!r} nor categorize {(c['id'] if c else None)!r}")
    if errors:
        print(f"LOOT-IMPORTANCE VALIDATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        return 1
    print(f"LOOT-IMPORTANCE VALIDATION PASSED — {len(recs)} items, tiers {sorted(GRADES)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
