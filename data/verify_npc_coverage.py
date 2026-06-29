#!/usr/bin/env python3
"""Operator COMPLETENESS gate (offline, report-not-fail). Of the derived shops with an owner, how many got >=1
operator npc; residual categorized {owner-not-an-npc (no {{Infobox NPC}}), npc-no-location, npc-location-unresolved}.
"""
from __future__ import annotations
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.npcs import operator_map, operator_roster, _npc_slug   # noqa: E402
from kg_ingest.builders.shops import resolve_shop_places, build_place_name_index   # noqa: E402
from osrs_planner.engine.kg.model import Node, NodeKind   # noqa: E402

def main() -> int:
    storeline = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    shop_ib = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    npc_ib = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_npc_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    place_nodes = [Node(id=n["id"], kind=NodeKind.PLACE, name=n["name"], slug=n["id"].split(":",1)[1], data={})
                   for n in nodes if n["id"].startswith("place:")]
    name_index = build_place_name_index(place_nodes)

    op_map = operator_map(storeline, shop_ib, varrock)
    roster = operator_roster(storeline, shop_ib, varrock)
    not_npc = [n for n in roster if not (npc_ib.get(n) or {}).get("is_npc")]
    npcs = [n for n in roster if (npc_ib.get(n) or {}).get("is_npc")]
    no_loc, unresolved, parented = [], [], []
    for n in npcs:
        locs = npc_ib[n]["locations"]
        if not locs: no_loc.append(n)
        elif resolve_shop_places(locs, name_index): parented.append(n)
        else: unresolved.append((n, locs))
    print("NPC COVERAGE (operators of the derived shops):")
    print(f"  shops with an owner: {len(op_map)} ; distinct operator names: {len(roster)}")
    print(f"  -> real npcs (have {{Infobox NPC}}): {len(npcs)}  | owner-not-an-npc (quest/item links): {len(not_npc)}")
    print(f"  npcs parented: {len(parented)} | no-location: {len(no_loc)} | location-unresolved: {len(unresolved)}")
    for n, locs in sorted(unresolved)[:20]:
        print(f"        location-unresolved: {n} -> {locs}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
