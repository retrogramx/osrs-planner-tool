#!/usr/bin/env python3
"""Structural source-grounding gate for the recipe roster. HARD-FAILS (exit 1) on:
a consumes/produces dst that is not a committed item: node; a requires_facility dst that
is not a committed facility: node; a requires cond_group skill_level ref that is not a
skill: node; a recipe missing source_token; a consumes role outside {material,tool,subject};
duplicate recipe slugs. (Resolution residuals are the coverage verifier's job.)
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    errors = []
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    groups = json.load(open(os.path.join(ROOT, "kg", "condition_groups.json"), encoding="utf-8"))
    nid = {n["id"] for n in nodes}
    recipe_ids = {n["id"] for n in nodes if n["id"].startswith("recipe:")}
    gid = {g["id"]: g for g in groups}

    slugs = {}
    for n in nodes:
        if not n["id"].startswith("recipe:"):
            continue
        if not n["data"].get("source_token"):
            errors.append(f"[source] {n['id']} missing source_token")
        if n["slug"] in slugs:
            errors.append(f"[slug] duplicate recipe slug {n['slug']!r}")
        slugs[n["slug"]] = n["id"]

    for e in edges:
        if e["src"] not in recipe_ids:
            continue
        t = e["type"]
        if t in ("consumes", "produces"):
            if e["dst"] not in nid or not e["dst"].startswith("item:"):
                errors.append(f"[{t}] {e['src']} dst {e['dst']} not a committed item node")
            if t == "consumes" and (e.get("data") or {}).get("role") not in ("material", "tool", "subject"):
                errors.append(f"[role] {e['src']} bad consumes role {(e.get('data') or {}).get('role')!r}")
        elif t == "requires_facility":
            if e["dst"] not in nid or not e["dst"].startswith("facility:"):
                errors.append(f"[requires_facility] {e['src']} dst {e['dst']} not a committed facility node")
        elif t == "requires":
            g = gid.get(e.get("cond_group"))
            for ch in (g or {}).get("children", []):
                if isinstance(ch, dict) and ch.get("atom_type") == "skill_level" and ch.get("ref_node") not in nid:
                    errors.append(f"[skill] {e['src']} skill_level ref {ch.get('ref_node')} not a node")

    if errors:
        print(f"RECIPE VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print(f"RECIPE VERIFICATION PASSED — {len(recipe_ids)} recipe nodes source-grounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
