#!/usr/bin/env python3
"""Source-grounding gate for data/charge_recipes.json (editorial charge layer).

Checks: every produces/subject/material item_id resolves in item_dictionary.json;
every record has source_url + a non-empty source_token; slugs are unique; every
qty / charge_yield / charge_capacity is a positive int; and produces & subject
share a page_name in item_dictionary (wrong-pairing guard). Exits non-zero on any
violation. Mirrors data/verify_item_families.py.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
CHARGES = os.path.join(ROOT, "data", "charge_recipes.json")


def _pos_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def main() -> int:
    errors: list[str] = []
    with open(DICT, encoding="utf-8") as f:
        id_to_page = {r["item_id"]: r["page_name"] for r in json.load(f)["records"]}
    with open(CHARGES, encoding="utf-8") as f:
        doc = json.load(f)
    seen: set[str] = set()
    for rec in doc["records"]:
        slug = rec.get("slug", "")
        if not slug:
            errors.append("[slug] record missing slug")
        if slug in seen:
            errors.append(f"[slug] duplicate recipe slug {slug!r}")
        seen.add(slug)
        if not rec.get("source_url"):
            errors.append(f"[source] {slug!r} missing source_url")
        if not rec.get("source_token"):
            errors.append(f"[source] {slug!r} missing source_token")
        prod, subj = rec.get("produces", {}), rec.get("subject", {})
        refs = [prod, subj] + list(rec.get("materials", []))
        for ref in refs:
            iid = ref.get("item_id")
            if iid not in id_to_page:
                errors.append(f"[item] {slug!r} item_id {iid!r} not in item_dictionary")
            if not _pos_int(ref.get("qty")):
                errors.append(f"[qty] {slug!r} item_id {iid!r} qty not a positive int: {ref.get('qty')!r}")
        for key in ("charge_yield", "charge_capacity"):
            if not _pos_int(rec.get(key)):
                errors.append(f"[charge] {slug!r} {key} not a positive int: {rec.get(key)!r}")
        # wrong-pairing guard: produces & subject must be the same item-family (page_name)
        pp, sp = id_to_page.get(prod.get("item_id")), id_to_page.get(subj.get("item_id"))
        if pp is not None and sp is not None and pp != sp:
            errors.append(f"[pair] {slug!r} produces page {pp!r} != subject page {sp!r}")
    if errors:
        print(f"CHARGE-RECIPES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("CHARGE-RECIPES VERIFICATION PASSED — all charge recipes source-grounded.")
    print(f"  recipes: {len(doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
