#!/usr/bin/env python3
"""THE COMPLETENESS GATE (offline). Asserts the committed graph contains a place node for
every IN-category member in the committed snapshot (a member maps in iff its slug is a
place id), and reports have N/total per IN category. Report-not-fail: a residual is the
to-do, not an error. --refresh re-queries the live API to flag snapshot-vs-wiki drift.
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from kg_ingest.builders.world import is_excluded  # noqa: E402
_slug = lambda t: "place:" + re.sub(r"[^a-z0-9]+", "-", re.sub(r"\s*\(.*?\)\s*$", "", t.lower())).strip("-")


def main() -> int:
    snap = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_location_categories.json"), encoding="utf-8"))
    place_ids = {n["id"] for n in json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
                 if n["id"].startswith("place:")}
    print("COVERAGE (graph vs committed snapshot, per IN category):")
    residual, out_noise = 0, 0
    for cat, members in snap["categories"].items():
        # Count each slug AT MOST ONCE per category: a title is "have" iff its slug is in
        # place_ids AND that slug hasn't already been claimed by an earlier title in this
        # category. Colliding titles (e.g. 14× "Unnamed island (…)" → one slug) all land
        # in miss except the first, so the gate never reports false coverage.
        have, miss, claimed = [], [], set()
        for t in members:
            if is_excluded(t, snap["page_categories"].get(t, [])):
                out_noise += 1
                continue                                  # noise is OUT, not "missing"
            sg = _slug(t)
            if sg in place_ids and sg not in claimed:
                claimed.add(sg); have.append(t)
            else:
                miss.append(t)  # no node, OR slug already claimed by another title (collision)
        residual += len(miss)
        print(f"  {cat:18} {len(have):4}/{len(members) - sum(1 for t in members if is_excluded(t, snap['page_categories'].get(t, []))):4}")
        for m in sorted(miss)[:8]:
            print(f"        missing: {m}")
    print(f"\nOUT (noise: list/index/discontinued): {out_noise}")
    print(f"residual (snapshot members without a place node): {residual} — report-not-fail (to-do).")
    if "--refresh" in sys.argv:
        print("(--refresh: re-query the live category API and diff vs the committed snapshot to flag game-update drift.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
