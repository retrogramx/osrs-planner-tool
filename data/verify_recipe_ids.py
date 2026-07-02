#!/usr/bin/env python3
"""Report (exit 0) for recipe-id stability: registry size, committed roster count,
any committed roster slug missing from the registry (should be 0), and the
true-duplicate identity groups. Structural enforcement is validate_kg's job."""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    reg = json.load(open(os.path.join(ROOT, "data", "recipe_slug_registry.json"), encoding="utf-8"))["recipes"]
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    reg_slugs = {s for e in reg.values() for s in e["slugs"]}
    roster = [n for n in nodes if n["id"].startswith("recipe:") and "charge_capacity" not in (n.get("data") or {})]
    roster_slugs = {n["slug"] for n in roster}
    unregistered = sorted(n["slug"] for n in roster if n["slug"] not in reg_slugs)
    orphans = sorted(reg_slugs - roster_slugs)
    dupes = {h: e for h, e in reg.items() if len(e["slugs"]) > 1}
    slug_to_node = {n["slug"]: n for n in nodes if n["id"].startswith("recipe:")}

    print("RECIPE-ID STABILITY (report-not-fail):")
    print(f"  registry identities: {len(reg)}  (slugs: {len(reg_slugs)})")
    print(f"  committed roster recipes: {len(roster)}")
    print(f"  roster slugs NOT in registry: {len(unregistered)}")
    for s in unregistered[:20]:
        print("     -", s)
    print(f"  registry slugs NOT in roster (orphans): {len(orphans)}")
    for s in orphans[:20]:
        print("     -", s)
    print(f"  true-duplicate identity groups: {len(dupes)}")
    for _, e in sorted(dupes.items(), key=lambda kv: kv[1]["output"]):
        urls = {slug_to_node[s].get("data", {}).get("source_url")
                for s in e["slugs"] if s in slug_to_node}
        urls.discard(None)
        page_count = len(urls)
        label = "genuine duplicate" if page_count <= 1 else "same payload, different-source"
        print(f"     - {e['output']}: {e['slugs']}  ({page_count} source page{'s' if page_count != 1 else ''} — {label})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
