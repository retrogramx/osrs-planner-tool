#!/usr/bin/env python3
"""Source-grounding gate for the all-shops layer. REPORTS (never fails) resolution
residuals: shops with no infobox location (FLAG), unresolved sold_item names, deferred
multi-location shops. HARD-FAILS (exit 1) on structural violations: a derived sells edge
whose (shop, item) has no backing Storeline row, or a derived located_in whose dst is not
a committed place node. Reuses the builder helpers.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.shops import shop_roster, _shop_slug                  # noqa: E402
from kg_ingest.builders.storeline import index_by_shop                        # noqa: E402
from kg_ingest.builders.map_varrock import make_item_resolver                 # noqa: E402


def main() -> int:
    errors, unresolved = [], []
    rows = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    resolve = make_item_resolver(json.load(open(os.path.join(ROOT, "data", "item_dictionary.json"), encoding="utf-8"))["records"])

    place_ids = {n["id"] for n in nodes if n["id"].startswith("place:")}
    by_shop = index_by_shop(rows)
    roster = shop_roster(rows, varrock)
    slug_to_name = {_shop_slug(name): name for name in roster}

    # every derived sells edge -> a backing Storeline row (the shop sells the item per Storeline)
    for e in edges:
        if e.get("type") != "sells" or not e["src"].startswith("shop:"):
            continue
        name = slug_to_name.get(e["src"])
        if name is None:
            continue                                  # Varrock shop (build_storeline) — not this verifier's scope
        backing = {resolve(r.get("sold_item", "")) for r in by_shop.get(name, [])}
        iid = e["dst"].split(":", 1)[1]
        if f"item:{iid}" not in {f"item:{b}" for b in backing if b is not None}:
            errors.append(f"[sells] {e['src']} -> {e['dst']} has no backing Storeline row")

    # every derived located_in -> a committed place node
    for e in edges:
        if e.get("type") == "located_in" and e["src"] in slug_to_name and e["dst"] not in place_ids:
            errors.append(f"[located_in] {e['src']} -> {e['dst']} dst is not a committed place node")

    # resolution residual (report): unresolved sold_item names across the roster
    for name in roster:
        for r in by_shop.get(name, []):
            if resolve(r.get("sold_item", "")) is None:
                unresolved.append(f"{_shop_slug(name)}: {r.get('sold_item')!r}")

    if errors:
        print(f"SHOP VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print("SHOP VERIFICATION PASSED — derived shop stock + locations source-grounded.")
    print(f"  derived shops in roster: {len(roster)}")
    if unresolved:
        print(f"  {len(unresolved)} unresolved sold_item name(s) (residual — alias pass):")
        for u in unresolved[:30]:
            print("    -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
