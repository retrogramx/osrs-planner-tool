#!/usr/bin/env python3
"""Coverage gate for the facility taxonomy layer. REPORTS (never fails, exit 0): of the distinct
uses_facility values, how many became facilities vs were deferred (npc/shop) vs are AMBIGUOUS
(the owner review queue), plus override-forced/excluded and redirect-dedup disclosure.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.facilities import (  # noqa: E402
    classify_infobox, facility_roster, build_facilities, _canonical_page,
)


def main() -> int:
    raw = os.path.join(ROOT, "data", "raw")
    rows = json.load(open(os.path.join(raw, "recipe_facility_bucket.json"), encoding="utf-8"))["bucket"]
    ibs = json.load(open(os.path.join(raw, "wiki_facility_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    ov = json.load(open(os.path.join(ROOT, "data", "map", "facility_overrides.json"), encoding="utf-8"))
    force_fac = {o["value"] for o in ov.get("force_facility", [])}
    force_exc = {o["value"] for o in ov.get("force_exclude", [])}

    values = facility_roster(rows)
    buckets = {"facility": [], "npc": [], "shop": [], "ambiguous": []}
    for v in values:
        if v in force_exc:
            continue
        if v in force_fac:
            buckets["facility"].append(v); continue
        buckets[classify_infobox((ibs.get(v) or {}).get("infoboxes", []))].append(v)

    facility_value_count = len(buckets["facility"])

    # Build to get the actual post-dedup node count
    fac_nodes, _, _ = build_facilities(rows, ibs, ov)
    node_count = len(fac_nodes)
    collapsed = facility_value_count - node_count

    total = len(values)
    print("FACILITY COVERAGE (report-not-fail):")
    print(f"  distinct uses_facility values: {total}")
    print(f"  facilities (built):     {facility_value_count}  (incl. {len(force_fac)} force_facility)")
    print(f"  facility nodes (after redirect-dedup): {node_count}  ({facility_value_count} facility-values, {collapsed} collapsed)")
    print(f"  deferred service-via-npc:  {len(buckets['npc'])}")
    print(f"  deferred service-via-shop: {len(buckets['shop'])}")
    print(f"  force_exclude:             {len(force_exc & set(values))}")
    print(f"  AMBIGUOUS (review queue):  {len(buckets['ambiguous'])}")
    for v in buckets["ambiguous"]:
        print(f"     - {v}  {(ibs.get(v) or {}).get('infoboxes', [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
