#!/usr/bin/env python3
"""Source-grounding gate for data/item_node_families.json (editorial L2 layer).

Checks: every member `page` resolves in item_dictionary.json; every record has a
source_url + a non-empty source_token; family slugs are unique, end in '-family',
and never collide with a member page's slug. Exits non-zero on any violation.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from kg_ingest.ids import slugify  # noqa: E402

DICT = os.path.join(ROOT, "data", "item_dictionary.json")
FAMILIES = os.path.join(ROOT, "data", "item_node_families.json")


def main() -> int:
    errors: list[str] = []
    pages = {r["page_name"] for r in json.load(open(DICT, encoding="utf-8"))["records"]}
    fam_doc = json.load(open(FAMILIES, encoding="utf-8"))
    seen_slugs: set[str] = set()
    for rec in fam_doc["records"]:
        slug = rec.get("slug", "")
        if not slug.endswith("-family"):
            errors.append(f"[slug] {slug!r} must end with '-family'")
        if slug in seen_slugs:
            errors.append(f"[slug] duplicate family slug {slug!r}")
        seen_slugs.add(slug)
        if not rec.get("source_url") or not rec.get("source_token"):
            errors.append(f"[source] {slug!r} missing source_url/source_token")
        for m in rec.get("members", []):
            if m["page"] not in pages:
                errors.append(f"[page] {slug!r} member page {m['page']!r} not in item_dictionary")
            if slugify(m["page"]) == slug:
                errors.append(f"[collide] family slug {slug!r} collides with member page slug")
    if errors:
        print(f"ITEM-FAMILIES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("ITEM-FAMILIES VERIFICATION PASSED — all family records source-grounded.")
    print(f"  families: {len(fam_doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
