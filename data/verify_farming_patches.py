#!/usr/bin/env python3
"""Structural source-grounding gate for the farming-patch layer (hard-fail, exit 1 on violation).

Every farming_patch node must: (1) have a patch_type in the closed vocab; (2) trace its
source_token to a real parsed table row; (3) if located_in, target a real committed place.
Never fabricated. Reuses the committed snapshot + the deterministic parser.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.farming_tables import parse_patch_tables  # noqa: E402

CORE = {"herb", "allotment", "flower", "bush", "hops", "tree", "fruit_tree", "spirit_tree", "coral"}


def main() -> int:
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    tables = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_farming_patch_tables.json"),
                            encoding="utf-8"))["tables"]
    rows = parse_patch_tables(tables)
    row_types = {r["patch_type"] for r in rows}
    row_tokens = {r["location_raw"].strip() for r in rows}
    place_ids = {n["id"] for n in nodes if n["id"].startswith("place:")}
    fp = [n for n in nodes if n["id"].startswith("farming_patch:")]

    violations = []
    for n in fp:
        pt = n["data"].get("patch_type", "")
        if pt not in row_types and pt not in CORE:
            violations.append(f"[type] {n['id']}: patch_type {pt!r} not a parsed table type")
        if n["data"].get("source_token", "").strip() not in row_tokens:
            violations.append(f"[grounding] {n['id']}: source_token not traceable to a table row")
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    for e in edges:
        if e["type"] == "located_in" and e["src"].startswith("farming_patch:"):
            if e["dst"] not in place_ids:
                violations.append(f"[place] {e['src']}: located_in {e['dst']} is not a committed place")

    if violations:
        print(f"FARMING VERIFICATION FAILED — {len(violations)} violation(s):")
        for v in violations[:60]:
            print("  " + v)
        return 1
    print(f"FARMING VERIFICATION PASSED — {len(fp)} farming_patch nodes source-grounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
