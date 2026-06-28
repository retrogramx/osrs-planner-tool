#!/usr/bin/env python3
"""Source-grounding gate for data/map/varrock.json (the connective vertical).

Reuses the builder's item resolver (no drift). STRUCTURAL checks (hard-fail): every
located_in target is a place present in the file OR in the world backbone (world.json)
— backbone places (gielinor/mainland/misthalin/varrock etc.) were moved from varrock.json
to world.json as part of the Task-8 world-skeleton integration; every shop.operator is a
present npc AND reciprocally in that npc's operates[]; slug uniqueness. Exits non-zero on
any structural violation. Sells/gate checks are owned by verify_storeline.py.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "data", "map", "varrock.json")
WORLD = os.path.join(ROOT, "data", "map", "world.json")


def main() -> int:
    errors: list[str] = []
    with open(MAP, encoding="utf-8") as f:
        m = json.load(f)

    place_ids = {p["id"] for p in m["places"]}
    # World backbone places are valid external located_in targets (backbone migrated to world.json).
    if os.path.exists(WORLD):
        with open(WORLD, encoding="utf-8") as f:
            world_data = json.load(f)
        place_ids |= {p["id"] for p in world_data["places"]}
    npc_by_id = {n["id"]: n for n in m["npcs"]}
    shop_ids = {s["id"] for s in m["shops"]}
    seen: set[str] = set()
    for coll in ("places", "npcs", "shops"):
        for x in m[coll]:
            if x["id"] in seen:
                errors.append(f"[slug] duplicate id {x['id']!r}")
            seen.add(x["id"])
            li = x.get("located_in")
            if li is not None and li not in place_ids:
                errors.append(f"[located_in] {x['id']!r} -> {li!r} not a place in the file")

    for sh in m["shops"]:
        op = sh.get("operator")
        if op:
            if op not in npc_by_id:
                errors.append(f"[operator] shop {sh['id']!r} operator {op!r} not an npc in the file")
            elif sh["id"] not in (npc_by_id[op].get("operates") or []):
                errors.append(f"[operates] {op!r} does not reciprocally operate {sh['id']!r}")

    if errors:
        print(f"MAP VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print("MAP VERIFICATION PASSED — Varrock map source-grounded.")
    print(f"  places: {len(place_ids)}  npcs: {len(npc_by_id)}  shops: {len(shop_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
