#!/usr/bin/env python3
"""Source-grounding gate for the operator layer. HARD-FAILS (exit 1) on structural breaches: an `operates` edge
whose (npc, shop) has no backing shop-brick `owner` entry, or a derived npc `located_in` whose dst is not a
committed place node. Otherwise PASSES (exit 0). Resolution residuals (owner links with no {{Infobox NPC}},
unresolved locations) are reported by verify_npc_coverage.py, not here.
"""
from __future__ import annotations
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.npcs import operator_map, _npc_slug, _shop_slug   # noqa: E402

def main() -> int:
    errors = []
    storeline = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    shop_ib = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    place_ids = {n["id"] for n in nodes if n["id"].startswith("place:")}

    varrock_npc_ids = {n["id"] for n in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["npcs"]}
    op_map = operator_map(storeline, shop_ib, varrock)
    # backing set of (npc_id, shop_id) the brick supports
    backing = {(_npc_slug(npc), _shop_slug(shop)) for shop, npcs in op_map.items() for npc in npcs}
    # exclude Varrock NPCs: build_map owns their edges; build_npcs skips varrock_npc_names
    derived_npc_ids = {_npc_slug(npc) for npcs in op_map.values() for npc in npcs} - varrock_npc_ids

    for e in edges:
        if e.get("type") == "operates" and e["src"] in derived_npc_ids:
            if (e["src"], e["dst"]) not in backing:
                errors.append(f"[operates] {e['src']} -> {e['dst']} has no backing shop-brick owner")
        if e.get("type") == "located_in" and e["src"] in derived_npc_ids and e["dst"] not in place_ids:
            errors.append(f"[located_in] {e['src']} -> {e['dst']} dst is not a committed place node")

    if errors:
        print(f"NPC VERIFICATION FAILED — {len(errors)} violation(s):")
        for x in errors[:60]: print("  -", x)
        return 1
    print("NPC VERIFICATION PASSED — operators source-grounded.")
    print(f"  derived operator npcs: {len(derived_npc_ids)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
