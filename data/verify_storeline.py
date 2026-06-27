#!/usr/bin/env python3
"""Source-grounding gate for the Storeline shop-stock layer (slice 7).

REPORTS (never fails) resolution/coverage residuals: shops with no Storeline match
(dialogue-shops -> owner fallback) and sold_item names that don't resolve. HARD-FAILS
(exit 1) on structural violations: a malformed owner gate (bad type / ref not in the
committed graph / missing source_token) and the ownership rule (no shop->item with BOTH
a gated and an ungated sells edge in the committed graph). Reuses the builder helpers.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.map_varrock import make_item_resolver, _condition_atom  # noqa: E402
from kg_ingest.builders.storeline import index_by_shop, match_shop              # noqa: E402

MAP = os.path.join(ROOT, "data", "map", "varrock.json")
RAW = os.path.join(ROOT, "data", "raw", "storeline_bucket.json")
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
NODES = os.path.join(ROOT, "kg", "nodes.json")
EDGES = os.path.join(ROOT, "kg", "edges.json")


def main() -> int:
    errors, unresolved = [], []
    m = json.load(open(MAP, encoding="utf-8"))
    records = json.load(open(RAW, encoding="utf-8"))["bucket"]
    resolve = make_item_resolver(json.load(open(DICT, encoding="utf-8"))["records"])
    graph_ids = {n["id"] for n in json.load(open(NODES, encoding="utf-8"))}
    edges = json.load(open(EDGES, encoding="utf-8"))

    by_shop = index_by_shop(records)
    soldby = list(by_shop)

    covered, uncovered = [], []
    total = resolved = 0
    for sh in m["shops"]:
        matched = match_shop(sh["name"], soldby)
        if matched is None:
            uncovered.append(sh["id"]); continue
        covered.append(sh["id"])
        for row in by_shop[matched]:
            total += 1
            if resolve(row.get("sold_item", "")) is None:
                unresolved.append(f"{sh['id']}: {row.get('sold_item')!r}")
            else:
                resolved += 1

    # HARD-FAIL: owner gate conditions well-formed + resolve + have a source_token
    for sh in m["shops"]:
        for offer in sh.get("sells", []):
            cond = offer.get("condition")
            if not cond:
                continue
            if not offer.get("source_token"):
                errors.append(f"[source] gated sell {offer.get('item_name')!r} in {sh['id']!r} missing source_token")
            atom = _condition_atom(cond)
            if atom is None:
                errors.append(f"[condition] {offer.get('item_name')!r} in {sh['id']!r} bad type {cond.get('type')!r}")
            elif atom.ref_node not in graph_ids:
                errors.append(f"[ref] {atom.ref_node!r} ({offer.get('item_name')!r}) not in the committed graph")

    # HARD-FAIL: ownership rule — no (shop -> item) with BOTH a gated and an ungated sells edge
    pairs: dict[tuple, set] = {}
    for e in edges:
        if e.get("type") == "sells":
            pairs.setdefault((e["src"], e["dst"]), set()).add(e.get("cond_group") is not None)
    for (src, dst), kinds in sorted(pairs.items()):
        if kinds == {True, False}:
            errors.append(f"[ownership] {src} -> {dst} has BOTH a gated and an ungated sells edge")

    if errors:
        print(f"STORELINE VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print("STORELINE VERIFICATION PASSED — Varrock shop stock source-grounded.")
    print(f"  shops covered by Storeline: {len(covered)}/{len(m['shops'])} ; "
          f"dialogue-shops (owner-sells fallback): {sorted(uncovered)}")
    print(f"  storeline rows resolved: {resolved}/{total}")
    if unresolved:
        print(f"  {len(unresolved)} unresolved sold_item name(s) (residual — alias pass):")
        for u in unresolved[:40]:
            print("    -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
