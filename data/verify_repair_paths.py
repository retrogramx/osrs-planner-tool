#!/usr/bin/env python3
"""Source-grounding gate for data/repair_paths.json (editorial repair layer).

Checks: every `broken` + `repaired` id resolves in item_dictionary.json and shares
the record's `page` (page_name); broken != repaired; slug unique; source_url +
non-empty source_token. Exits non-zero on any violation. Mirrors
data/verify_degrade_paths.py.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
PATHS = os.path.join(ROOT, "data", "repair_paths.json")


def main() -> int:
    errors: list[str] = []
    with open(DICT, encoding="utf-8") as f:
        id_to_page = {r["item_id"]: r["page_name"] for r in json.load(f)["records"]}
    with open(PATHS, encoding="utf-8") as f:
        doc = json.load(f)
    seen: set[str] = set()
    for rec in doc["records"]:
        slug = rec.get("slug", "")
        if not slug or slug in seen:
            errors.append(f"[slug] missing/duplicate slug {slug!r}")
        seen.add(slug)
        if not rec.get("source_url"):
            errors.append(f"[source] {slug!r} missing source_url")
        if not rec.get("source_token"):
            errors.append(f"[source] {slug!r} missing source_token")
        page = rec.get("page")
        broken, repaired = rec.get("broken"), rec.get("repaired")
        if broken == repaired:
            errors.append(f"[same] {slug!r} broken == repaired ({broken})")
        for label, iid in (("broken", broken), ("repaired", repaired)):
            if iid not in id_to_page:
                errors.append(f"[item] {slug!r} {label} id {iid!r} not in item_dictionary")
            elif id_to_page[iid] != page:
                errors.append(f"[page] {slug!r} {label} id {iid!r} page {id_to_page[iid]!r} != {page!r}")
    if errors:
        print(f"REPAIR-PATHS VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("REPAIR-PATHS VERIFICATION PASSED — all repair paths source-grounded.")
    print(f"  paths: {len(doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
