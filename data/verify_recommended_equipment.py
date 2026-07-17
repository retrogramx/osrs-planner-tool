#!/usr/bin/env python3
"""Source-grounding gate for data/recommended_equipment.json. Structural -> exit 1; coverage -> exit 0."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def main() -> int:
    data = json.load(open(os.path.join(HERE, "recommended_equipment.json"), encoding="utf-8"))
    recs = data["records"]
    dict_ids = {r["item_id"] for r in json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]}
    clog_ids = {r["item_id"] for r in json.load(open(os.path.join(HERE, "collection_log.json"), encoding="utf-8"))["records"]}
    errors = []
    for r in recs:
        if r["item_id"] not in dict_ids:
            errors.append(f"{r['item_name']} ({r['item_id']}) not in item_dictionary")
        if not r.get("source_token") or not r.get("source_url"):
            errors.append(f"{r['item_name']}: missing source_token/source_url")
    if errors:
        print(f"RECOMMENDED-EQUIPMENT VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    distinct = {r["item_id"] for r in recs}
    non_clog = distinct - clog_ids
    print(f"RECOMMENDED-EQUIPMENT VERIFICATION PASSED — {len(recs)} records / {len(distinct)} distinct items source-grounded.")
    print(f"  coverage: {len(non_clog)} distinct items NOT in the collection log (the complementary gap); "
          f"{len(data.get('_unresolved', []))} unresolved names disclosed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
