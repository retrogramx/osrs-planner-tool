#!/usr/bin/env python3
"""Source-grounding gate for data/degrade_paths.json (editorial degradation layer).

Checks: every sequence[] + terminal_item id resolves in item_dictionary.json;
sequence non-empty and all its ids share page_name (== record's page); terminal in
{destroyed, reverts_to, broken}; reverts_to/broken carry a terminal_item sharing the
page_name; destroyed carries NO terminal_item; trigger in {per_use, per_hit}; slug
unique; source_url + non-empty source_token. Exits non-zero on any violation.
Mirrors data/verify_charge_recipes.py.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
PATHS = os.path.join(ROOT, "data", "degrade_paths.json")
_TERMINALS = {"destroyed", "reverts_to", "broken"}
_TRIGGERS = {"per_use", "per_hit"}


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
        if rec.get("trigger") not in _TRIGGERS:
            errors.append(f"[trigger] {slug!r} bad trigger {rec.get('trigger')!r}")
        page = rec.get("page")
        seq = rec.get("sequence") or []
        if not seq:
            errors.append(f"[sequence] {slug!r} empty sequence")
        for iid in seq:
            if iid not in id_to_page:
                errors.append(f"[item] {slug!r} sequence id {iid!r} not in item_dictionary")
            elif id_to_page[iid] != page:
                errors.append(f"[page] {slug!r} sequence id {iid!r} page {id_to_page[iid]!r} != {page!r}")
        terminal = rec.get("terminal")
        if terminal not in _TERMINALS:
            errors.append(f"[terminal] {slug!r} bad terminal {terminal!r}")
        if terminal == "destroyed":
            if "terminal_item" in rec:
                errors.append(f"[terminal] {slug!r} destroyed must NOT carry a terminal_item")
        elif terminal in ("reverts_to", "broken"):
            ti = rec.get("terminal_item")
            if ti not in id_to_page:
                errors.append(f"[item] {slug!r} terminal_item {ti!r} not in item_dictionary")
            elif id_to_page[ti] != page:
                errors.append(f"[page] {slug!r} terminal_item page {id_to_page[ti]!r} != {page!r}")
    if errors:
        print(f"DEGRADE-PATHS VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("DEGRADE-PATHS VERIFICATION PASSED — all degrade paths source-grounded.")
    print(f"  paths: {len(doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
