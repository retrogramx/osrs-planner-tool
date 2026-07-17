"""Source-grounding gate for data/loot_families.json. Structural -> exit 1; coverage -> exit 0."""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
VALID_PREFIX = ("recipe:", "name_suffix:", "equipment_slot:", "equipment_utility", "override")

def main() -> int:
    data = json.load(open(os.path.join(HERE, "loot_families.json"), encoding="utf-8"))
    recs = data["records"]
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    dict_ids = {r["item_id"] for r in dict_recs}
    errors, seen = [], set()
    for r in recs:
        if r["item_id"] not in dict_ids:
            errors.append(f"{r['item_id']}: not in item_dictionary")
        if r["item_id"] in seen:
            errors.append(f"{r['item_id']}: duplicate family assignment")
        seen.add(r["item_id"])
        if not (r.get("source_signal") and r.get("source_token") and r.get("source_url")):
            errors.append(f"{r['item_id']}: missing source_signal/token/url")
        if not any(str(r.get("source_signal","")).startswith(p) for p in VALID_PREFIX):
            errors.append(f"{r['item_id']}: bad source_signal '{r.get('source_signal')}'")
    if errors:
        print(f"LOOT-FAMILIES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    dist = Counter(r["family"] for r in recs)
    pct = 100.0 * len({r["item_id"] for r in recs}) / len(dict_ids)
    print(f"LOOT-FAMILIES VERIFICATION PASSED — {len(recs)} items classified into {len(dist)} families.")
    print(f"  coverage: {pct:.1f}% of the {len(dict_ids)}-item dictionary; families: {dict(dist)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
