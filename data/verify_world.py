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
from kg_ingest.builders.world import build_world, resolve_parents  # noqa: E402


def _opt_infoboxes():
    p = os.path.join(ROOT, "data", "raw", "wiki_location_infoboxes.json")
    if not os.path.exists(p):
        return None
    from kg_ingest.builders.world import parse_infobox_links  # Task 4+
    raw = json.load(open(p, encoding="utf-8"))["infoboxes"]
    return {t: parse_infobox_links(r.get("location", "")) for t, r in raw.items()}


def _opt_overrides():
    p = os.path.join(ROOT, "data", "map", "world_parenting.json")
    return json.load(open(p, encoding="utf-8"))["overrides"] if os.path.exists(p) else None


def _unreachable_places(nodes, edges):
    """Place ids that cannot reach place:gielinor (cycle/dangling). Empty == acyclic single-root."""
    par = {e.src: e.dst for e in edges if e.type.value == "located_in"}
    out = []
    for n in nodes:
        if n.id == "place:gielinor":
            continue
        seen, cur = set(), n.id
        while cur != "place:gielinor":
            if cur is None or cur in seen:
                out.append(n.id); break
            seen.add(cur); cur = par.get(cur)
    return out


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
    _ibx, _ovr = _opt_infoboxes(), _opt_overrides()
    nodes, edges, _ = build_world(backbone, snapshot, region_ids, infoboxes=_ibx, overrides=_ovr)

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
    # reachability: every place must reach place:gielinor (acyclic, single-root)
    for pid in _unreachable_places(nodes, edges):
        errors.append(f"[reachable] {pid} does not reach place:gielinor (cycle/dangling)")
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
    # per-signal breakdown (DRY — same core the build used, same inputs)
    from collections import Counter
    _kept, _pmap, signal_map = resolve_parents(backbone, snapshot, infoboxes=_ibx, overrides=_ovr)
    by = Counter(signal_map.values())
    print("  re-homed by signal: " + ", ".join(f"{k}={by[k]}" for k in
          ("override", "category", "name-suffix", "infobox") if by.get(k)))
    print(f"  re-homed {sum(v for k, v in by.items() if k != 'FLAG')}/{len(signal_map)} content places "
          f"· residual (FLAG): {by.get('FLAG', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
