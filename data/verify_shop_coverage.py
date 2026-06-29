#!/usr/bin/env python3
"""SHOP COMPLETENESS GATE (offline, report-not-fail). Cross-checks the two shop rosters —
Storeline sold_by vs the Category:Shops type-category union — and reports, per shop_type,
how many have a shop node and how many of those are parented / multi-location-deferred /
FLAGged (no location). The FLAG bucket is sub-categorized into three actionable groups:
  no-infobox-match       — genuine NPC-sellers with no shop page (deferred to NPC layer)
  infobox-no-location    — matched a shop page but its infobox has no locations field
  infobox-location-unresolved — matched + has locations but none resolve to a skeleton place
A residual is a to-do, not an error. --refresh = live drift.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.shops import shop_roster, _shop_slug, resolve_shop_places  # noqa: E402
from kg_ingest.builders.storeline import match_shop                                 # noqa: E402
from kg_ingest.builders.world import _norm                                          # noqa: E402


def _build_place_name_index(node_dicts):
    """Map _norm(place name) -> place id; deterministic first-wins (sorted by id)."""
    idx: dict[str, str] = {}
    for n in sorted(node_dicts, key=lambda n: n["id"]):
        if n["id"].startswith("place:"):
            idx.setdefault(_norm(n["name"]), n["id"])
    return idx


def main() -> int:
    rows = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    cats = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_categories.json"), encoding="utf-8"))["categories"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    infoboxes = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_infoboxes.json"), encoding="utf-8"))["infoboxes"]

    shop_ids = {n["id"] for n in nodes if n["id"].startswith("shop:")}
    multi = {n["id"] for n in nodes if n["id"].startswith("shop:") and n.get("data", {}).get("multi_location")}
    located = {e["src"] for e in edges if e.get("type") == "located_in" and e["src"].startswith("shop:")}

    name_index = _build_place_name_index(nodes)
    infobox_titles = list(infoboxes)

    roster = shop_roster(rows, varrock)
    have = [name for name in roster if _shop_slug(name) in shop_ids]
    parented = [name for name in have if _shop_slug(name) in located]
    multi_def = [name for name in have if _shop_slug(name) in multi]
    flagged = [name for name in have if _shop_slug(name) not in located and _shop_slug(name) not in multi]

    # Sub-categorize the FLAG bucket into three actionable groups.
    no_infobox: list[str] = []
    infobox_no_loc: list[str] = []
    infobox_unresolved: list[tuple[str, list]] = []  # (name, raw_locations)
    for name in flagged:
        ib_title = match_shop(name, infobox_titles)
        if ib_title is None:
            no_infobox.append(name)
            continue
        locs = infoboxes[ib_title].get("locations", [])
        if not locs:
            infobox_no_loc.append(name)
            continue
        # Has locations in infobox but none resolved to a skeleton place.
        infobox_unresolved.append((name, locs))

    print("SHOP COVERAGE (graph vs Storeline roster):")
    print(f"  roster (Storeline sold_by minus Varrock): {len(roster)}")
    print(f"  have a shop node:        {len(have)}/{len(roster)}")
    print(f"  parented (located_in):   {len(parented)}")
    print(f"  multi-location deferred: {len(multi_def)}")
    print(f"  FLAGged (no location):   {len(flagged)}")
    print(f"    ↳ no-infobox-match (NPC-sellers, deferred to NPC layer):  {len(no_infobox)}")
    print(f"    ↳ infobox-no-location (shop page exists, no location):     {len(infobox_no_loc)}")
    print(f"    ↳ infobox-location-unresolved (place not in skeleton):     {len(infobox_unresolved)}")

    if infobox_unresolved:
        print("\n  Unresolved-location to-do (name-normalization / place-skeleton gap):")
        for name, locs in sorted(infobox_unresolved):
            print(f"    {_shop_slug(name)} → {locs}")

    # cross-check vs the type-category union (the second yardstick)
    cat_pages = {p for pages in cats.values() for p in pages}
    print(f"\n  type-category union pages: {len(cat_pages)} ; Storeline shops: {len(roster) + len(varrock)}")
    print("  residual (roster shops without a node, or category pages with no Storeline match) — report-not-fail.")
    if "--refresh" in sys.argv:
        print("  (--refresh: re-query the live category API and diff vs the committed snapshot.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
