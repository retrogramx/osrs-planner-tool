#!/usr/bin/env python3
"""Coverage gate for the facility taxonomy layer. REPORTS (never fails, exit 0): of the distinct
uses_facility values, how many became facilities vs were deferred (npc/shop) vs are AMBIGUOUS
(the owner review queue), plus override-forced/excluded. The ambiguous list is itemized for triage.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.facilities import classify_infobox, facility_roster  # noqa: E402


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

    total = len(values)
    print("FACILITY COVERAGE (report-not-fail):")
    print(f"  distinct uses_facility values: {total}")
    print(f"  facilities (built):     {len(buckets['facility'])}  (incl. {len(force_fac)} force_facility)")
    print(f"  deferred service-via-npc:  {len(buckets['npc'])}")
    print(f"  deferred service-via-shop: {len(buckets['shop'])}")
    print(f"  force_exclude:             {len(force_exc)}")
    print(f"  AMBIGUOUS (review queue):  {len(buckets['ambiguous'])}")
    for v in buckets["ambiguous"]:
        print(f"     - {v}  {(ibs.get(v) or {}).get('infoboxes', [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
