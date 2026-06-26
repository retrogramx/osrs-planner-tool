#!/usr/bin/env python3
"""Source-grounding gate for data/map/varrock.json (the connective vertical).

Reuses the builder's item resolver (no drift). STRUCTURAL checks (hard-fail): every
located_in target is a place present in the file; every shop.operator is a present npc
AND reciprocally in that npc's operates[]; every gated condition has type in
{quest, achievement_diary} + a ref resolving to an existing quest/diary node in the
committed graph + a source_token; slug uniqueness. Exits non-zero on any structural
violation. Unresolved sells.item_name values are a REPORTED residual (owner-authored
category/summary entries) — listed as resolved X/Y, never failing the gate.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                        # for kg_ingest.*
sys.path.insert(0, os.path.join(ROOT, "src"))   # for osrs_planner.* (imported by the builder)
from kg_ingest.builders.map_varrock import make_item_resolver, _condition_atom  # noqa: E402

MAP = os.path.join(ROOT, "data", "map", "varrock.json")
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
NODES = os.path.join(ROOT, "kg", "nodes.json")


def main() -> int:
    errors: list[str] = []
    unresolved: list[str] = []
    total_sells = 0
    with open(MAP, encoding="utf-8") as f:
        m = json.load(f)
    resolve = make_item_resolver(json.load(open(DICT, encoding="utf-8"))["records"])
    graph_ids = {n["id"] for n in json.load(open(NODES, encoding="utf-8"))}

    place_ids = {p["id"] for p in m["places"]}
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
        for offer in sh.get("sells", []):
            name = offer.get("item_name")
            total_sells += 1
            if resolve(name) is None:
                unresolved.append(f"{sh['id']}: {name!r}")
            cond = offer.get("condition")
            if cond:
                if not cond.get("source_token") and not offer.get("source_token"):
                    errors.append(f"[source] gated sell {name!r} in {sh['id']!r} missing source_token")
                atom = _condition_atom(cond)
                if atom is None:
                    errors.append(f"[condition] {name!r} in {sh['id']!r} bad condition type {cond.get('type')!r}")
                elif atom.ref_node not in graph_ids:
                    errors.append(f"[ref] condition ref {atom.ref_node!r} ({name!r}) not a node in the committed graph")

    # Structural violations are hard-fail. Unresolved sells item names are a REPORTED
    # residual (owner-authored category/summary entries the future Storeline/category
    # resolver will cover) — they never fail the gate.
    if errors:
        print(f"MAP VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    resolved = total_sells - len(unresolved)
    print("MAP VERIFICATION PASSED — Varrock map source-grounded.")
    print(f"  places: {len(place_ids)}  npcs: {len(npc_by_id)}  shops: {len(shop_ids)}  "
          f"sells resolved: {resolved}/{total_sells}")
    if unresolved:
        print(f"  {len(unresolved)} unresolved sells item name(s) (residual — to-do for the category resolver):")
        for u in unresolved:
            print("    -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
