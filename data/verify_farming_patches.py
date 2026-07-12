#!/usr/bin/env python3
"""Structural source-grounding gate for the farming-patch layer (hard-fail, exit 1 on violation).

Every farming_patch node must: (1) have its (patch_type, source_token) PAIR trace to one real
parsed table row — not two independent set memberships, which would let a "Frankenstein" node
(a real patch_type paired with a different row's location text) pass clean; (2) if located_in,
target a real committed place. Never fabricated. Reuses the committed snapshot + the
deterministic parser.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.farming_tables import parse_patch_tables  # noqa: E402


def find_violations(nodes, edges, rows, place_ids) -> list[str]:
    """Pure check, reused by main() and tests. `rows` = parse_patch_tables() output;
    `place_ids` = the set of committed place: node ids."""
    row_pairs = {(r["patch_type"], r["location_raw"].strip()) for r in rows}
    fp = [n for n in nodes if n["id"].startswith("farming_patch:")]

    violations = []
    for n in fp:
        pt = n["data"].get("patch_type", "")
        tok = n["data"].get("source_token", "").strip()
        if (pt, tok) not in row_pairs:
            violations.append(
                f"[grounding] {n['id']}: (patch_type={pt!r}, source_token={tok!r}) "
                f"does not match any single parsed table row")
    for e in edges:
        if e["type"] == "located_in" and e["src"].startswith("farming_patch:"):
            if e["dst"] not in place_ids:
                violations.append(f"[place] {e['src']}: located_in {e['dst']} is not a committed place")
    return violations


def main() -> int:
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    tables = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_farming_patch_tables.json"),
                            encoding="utf-8"))["tables"]
    rows = parse_patch_tables(tables)
    place_ids = {n["id"] for n in nodes if n["id"].startswith("place:")}
    fp = [n for n in nodes if n["id"].startswith("farming_patch:")]

    violations = find_violations(nodes, edges, rows, place_ids)

    if violations:
        print(f"FARMING VERIFICATION FAILED — {len(violations)} violation(s):")
        for v in violations[:60]:
            print("  " + v)
        return 1
    print(f"FARMING VERIFICATION PASSED — {len(fp)} farming_patch nodes source-grounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
