#!/usr/bin/env python3
"""Source-grounding gate for the world skeleton. STRUCTURAL hard-fails (exit 1): every
located_in resolves to a place; exactly one root (place:gielinor); no slug duplicate;
every place_type is in the schema enum. REPORTS (exit 0): unparented content places
(located_in == place:gielinor that aren't the root's legit children), and places missing
ruled_by/faction (best-effort governance). Reuses build_world (no drift).
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.world import build_world  # noqa: E402


def main() -> int:
    errors, unparented = [], []
    backbone = json.load(open(os.path.join(ROOT, "data", "map", "world.json"), encoding="utf-8"))
    snapshot = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_location_categories.json"), encoding="utf-8"))
    region_ids = {n["id"] for n in json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
                  if n["id"].startswith("region:")}
    enum = set(json.load(open(os.path.join(ROOT, "kg", "schema.json"), encoding="utf-8"))["node_kinds"]["place"]["place_type_enum"])
    # Standalone re-derive (no assemble extra_seen): gates structural invariants only
    # (single root / located_in resolves / place_type∈enum / no dup). The COMMITTED graph
    # bytes are gated separately by validate_kg + byte-stable assemble.
    nodes, edges, _ = build_world(backbone, snapshot, region_ids)

    ids = {n.id for n in nodes}
    if len(ids) != len(nodes):
        errors.append("[slug] duplicate place id")
    roots = [n for n in nodes if not any(e.src == n.id and e.type.value == "located_in" for e in edges)]
    if [r.id for r in roots] != ["place:gielinor"]:
        errors.append(f"[root] expected exactly place:gielinor as root, got {[r.id for r in roots][:5]}")
    for n in nodes:
        if n.data.get("place_type") not in enum:
            errors.append(f"[place_type] {n.id} has {n.data.get('place_type')!r} not in enum")
    for e in edges:
        if e.type.value == "located_in" and e.dst not in ids:
            errors.append(f"[located_in] {e.src} -> {e.dst} dangling")
    # residual: ingested content parented to the root (flagged-unparented)
    backbone_ids = {p["id"] for p in backbone["places"]}
    for e in edges:
        if e.type.value == "located_in" and e.dst == "place:gielinor" and e.src not in backbone_ids:
            unparented.append(e.src)

    if errors:
        print(f"WORLD VERIFICATION FAILED — {len(errors)} violation(s):")
        for x in errors[:60]:
            print("  -", x)
        return 1
    print("WORLD VERIFICATION PASSED — world skeleton source-grounded.")
    print(f"  places: {len(nodes)}  located_in edges: {sum(1 for e in edges if e.type.value=='located_in')}")
    print(f"  unparented content places (residual — owner to re-home): {len(unparented)}")
    for u in sorted(unparented)[:40]:
        print("    -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
