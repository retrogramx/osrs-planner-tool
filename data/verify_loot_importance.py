#!/usr/bin/env python3
"""Coverage report for data/loot_importance.json: per family, have N / family-total M.
Editorial data -> no source-grounding; reports gaps but never fails (exit 0)."""
import json, os, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))

def main() -> int:
    recs = json.load(open(os.path.join(HERE, "loot_importance.json"), encoding="utf-8"))["records"]
    fams = json.load(open(os.path.join(HERE, "loot_families.json"), encoding="utf-8"))["records"]
    LOOT_FAM = {"herb", "rune", "ore", "bar", "log", "seed", "bones", "ammo", "food"}
    fam_total = Counter(r["family"] for r in fams if r["family"] in LOOT_FAM)
    ranked = defaultdict(set)
    for r in recs:
        ranked[r["family"]].add(r["item_id"])
    ranked_ids = {r["item_id"] for r in recs}
    tier_dist = Counter(r["base_tier"] for r in recs)
    print(f"LOOT-IMPORTANCE COVERAGE — {len(recs)} items ranked; base-tier dist {dict(tier_dist)}")
    for fam in sorted(LOOT_FAM):
        have, tot = len(ranked.get(fam, ())), fam_total.get(fam, 0)
        missing = [r["item_id"] for r in fams if r["family"] == fam and r["item_id"] not in ranked_ids]
        print(f"  {fam:8} have {have}/{tot}" + (f"  (missing {len(missing)})" if missing else ""))
    for fam in ("essence", "gem", "plank"):
        print(f"  {fam:8} have {len(ranked.get(fam, ()))} (categories-sourced)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
