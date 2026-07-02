#!/usr/bin/env python3
"""Seed / maintain data/recipe_slug_registry.json — the committed identity->slug map
that makes roster recipe ids stable across re-derivation (spec 2026-07-01).

  --seed : replay the PRE-REGISTRY slug logic on the committed recipe rows (page-count
           `multi` + `-k` guard + charge-slug reservation), keying each emitted recipe by
           its NEW identity hash. Reproduces the current committed slugs => zero churn.
  (default): mint readable slugs for any recipe whose identity is not yet registered,
           appending to the existing registry (append-only; existing entries untouched).

Run: ./venv/bin/python data/update_recipe_registry.py --seed
"""
from __future__ import annotations

import json, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))

from kg_ingest.ids import slugify                                          # noqa: E402
from kg_ingest.recipe_identity import (                                    # noqa: E402
    resolve_recipe_payload, recipe_identity_hash, mint_slug, _facility_lookup)
from kg_ingest.builders.map_varrock import make_item_resolver             # noqa: E402
import html                                                                # noqa: E402

REGISTRY_PATH = os.path.join(ROOT, "data", "recipe_slug_registry.json")
BUCKET_PATH = os.path.join(ROOT, "data", "raw", "recipe_bucket.json")
ITEMDICT_PATH = os.path.join(ROOT, "data", "item_dictionary.json")
CHARGE_PATH = os.path.join(ROOT, "data", "charge_recipes.json")


def _resolver(item_dict_records):
    r = make_item_resolver(item_dict_records)
    def resolve(name):
        iid = r(html.unescape((name or "").strip()))
        return f"item:{iid}" if iid is not None else None
    return resolve


def _makeable(rows):
    """Rows with a structured output (output.name present) — the pre-registry `makeable`
    set that the `multi` page-count is taken over (mirrors build_recipe_roster @ e60818e)."""
    out = []
    for r in rows:
        try:
            pj = json.loads(r.get("production_json") or "{}")
        except Exception:
            pj = {}
        o = pj.get("output")
        if isinstance(o, dict) and o.get("name"):
            out.append(r)
    return out


def seed_registry(rows, resolve_item, fac_lut, charge_slugs) -> dict:
    """Replay the pre-registry slug scheme on `rows`, keyed by NEW identity hash."""
    makeable = _makeable(rows)
    page_rows = Counter(r.get("page_name") for r in makeable)
    claimed = set(charge_slugs)
    registry: dict = {"recipes": {}}
    for r in makeable:
        payload = resolve_recipe_payload(r, resolve_item, fac_lut)
        if payload is None:
            continue                                          # unresolvable output -> not emitted
        out_name, subtxt = payload["out_name"], payload["subtxt"]
        multi = page_rows[r.get("page_name")] > 1
        base = f"{slugify(out_name)}-{slugify(subtxt)}" if (multi and subtxt) else slugify(out_name)
        slug = base
        if slug in claimed:
            k = 2
            while f"{slug}-{k}" in claimed:
                k += 1
            slug = f"{slug}-{k}"
        claimed.add(slug)
        h = recipe_identity_hash(payload)
        entry = registry["recipes"].setdefault(h, {"slugs": [], "output": out_name})
        entry["slugs"].append(slug)
    return registry


def update_registry(rows, resolve_item, fac_lut, charge_slugs, registry) -> dict:
    """Append readable slugs for unregistered identities (append-only)."""
    reg = {"recipes": {h: {"slugs": list(e["slugs"]), "output": e["output"]}
                       for h, e in registry.get("recipes", {}).items()}}
    claimed = set(charge_slugs) | {s for e in reg["recipes"].values() for s in e["slugs"]}
    # count how many rows already map to each identity (to detect NEW dupes of an existing group)
    seen = Counter()
    for r in _makeable(rows):
        payload = resolve_recipe_payload(r, resolve_item, fac_lut)
        if payload is None:
            continue
        h = recipe_identity_hash(payload)
        entry = reg["recipes"].get(h)
        already = len(entry["slugs"]) if entry else 0
        if seen[h] < already:
            seen[h] += 1
            continue                                          # covered by an existing frozen slug
        # a new identity, or a new duplicate row of an existing identity -> mint + append
        slug = mint_slug(payload["out_name"], payload["subtxt"], claimed)
        if entry is None:
            reg["recipes"][h] = {"slugs": [slug], "output": payload["out_name"]}
        else:
            entry["slugs"].append(slug)
        seen[h] += 1
    return reg


def _write(registry):
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def main(argv):
    rows = json.load(open(BUCKET_PATH, encoding="utf-8"))["bucket"]
    item_dict = json.load(open(ITEMDICT_PATH, encoding="utf-8"))["records"]
    resolve = _resolver(item_dict)
    # facility nodes: read from the committed graph
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    fac_nodes = [type("N", (), {"name": n["name"], "id": n["id"], "data": n.get("data") or {}})
                 for n in nodes if n["id"].startswith("facility:")]
    fac_lut = _facility_lookup(fac_nodes)
    charge = json.load(open(CHARGE_PATH, encoding="utf-8"))
    charge_recs = charge if isinstance(charge, list) else charge.get("records", charge.get("recipes", []))
    charge_slugs = {c["slug"] for c in charge_recs}

    if "--seed" in argv:
        reg = seed_registry(rows, resolve, fac_lut, charge_slugs)
        _write(reg)
        n = sum(len(e["slugs"]) for e in reg["recipes"].values())
        print(f"SEEDED {REGISTRY_PATH}: {len(reg['recipes'])} identities / {n} slugs")
        return 0

    reg = json.load(open(REGISTRY_PATH, encoding="utf-8")) if os.path.exists(REGISTRY_PATH) else {"recipes": {}}
    before = json.dumps(reg, sort_keys=True)
    reg = update_registry(rows, resolve, fac_lut, charge_slugs, reg)
    _write(reg)
    minted = sum(len(e["slugs"]) for e in reg["recipes"].values()) - sum(
        len(e["slugs"]) for e in json.loads(before).get("recipes", {}).values())
    print(f"UPDATED {REGISTRY_PATH}: +{minted} slug(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
