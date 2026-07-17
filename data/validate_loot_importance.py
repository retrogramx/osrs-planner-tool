#!/usr/bin/env python3
"""Structural gate for data/loot_importance.json (editorial base tiers). Violations -> exit 1."""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GRADES = {"SS", "S", "A", "B", "C", "D", "E"}
RANKED = {"herb", "rune", "ore", "bar", "log", "seed", "bones", "ammo", "food", "essence", "gem", "plank"}
CATS = {"essence", "gem", "plank"}    # membership is categories-sourced, not in loot_families.json

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
        if r.get("family") not in CATS and iid in fam_of and fam_of[iid] != r.get("family"):
            errors.append(f"{iid}: family {r.get('family')!r} != loot_families {fam_of[iid]!r}")
    if errors:
        print(f"LOOT-IMPORTANCE VALIDATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        return 1
    print(f"LOOT-IMPORTANCE VALIDATION PASSED — {len(recs)} items, tiers {sorted(GRADES)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
