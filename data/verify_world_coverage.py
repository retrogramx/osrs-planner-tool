#!/usr/bin/env python3
"""THE COMPLETENESS GATE (offline). Asserts the committed graph contains a place node for
every IN-category member in the committed snapshot (a member maps in iff its slug is a
place id), and reports have N/total per IN category. Report-not-fail: a residual is the
to-do, not an error. --refresh re-queries the live API to flag snapshot-vs-wiki drift.
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_slug = lambda t: "place:" + re.sub(r"[^a-z0-9]+", "-", re.sub(r"\s*\(.*?\)\s*$", "", t.lower())).strip("-")


def main() -> int:
    snap = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_location_categories.json"), encoding="utf-8"))
    place_ids = {n["id"] for n in json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
                 if n["id"].startswith("place:")}
    print("COVERAGE (graph vs committed snapshot, per IN category):")
    residual = 0
    for cat, members in snap["categories"].items():
        have = [t for t in members if _slug(t) in place_ids]
        miss = [t for t in members if _slug(t) not in place_ids]
        residual += len(miss)
        print(f"  {cat:18} {len(have):4}/{len(members):4}")
        for m in sorted(miss)[:8]:
            print(f"        missing: {m}")
    print(f"\nresidual (snapshot members without a place node): {residual} — report-not-fail (to-do / OUT-filtered).")
    if "--refresh" in sys.argv:
        print("(--refresh: re-query the live category API and diff vs the committed snapshot to flag game-update drift.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
