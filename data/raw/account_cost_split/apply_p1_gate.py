#!/usr/bin/env python3
"""
P1 account-gate + disclosure fix for data/skills_training.json.

- PRESERVES the frozen envelope exactly: {_provenance, records, _excluded};
  payload key "records"; _provenance.record_count == len(records).
- Adds the four canonical account-gate fields to EVERY record (keeps originals):
    audience            : "main" | "ironman" | "f2p" | "all"
    pricing_basis       : "ge" | "high_alch" | "shop" | "store" | "mixed" | "none"
    realization_channel : "ge" | "coins" | "high_alch" | "shop" | "mixed" | "n/a"
    requires_ge         : bool  (true = needs GE buy/sell => NOT iron-viable)
- Mapping is DATA-DRIVEN from the existing cost_basis + account_family. No fabrication.
- Updates _provenance with a short fix note + accessed date.
- Discloses the previously-dropped gold/profit columns in completeness.known_missing.

Run from repo root:  python3 data/raw/account_cost_split/apply_p1_gate.py
"""
import json
import datetime

PATH = "data/skills_training.json"
ACCESSED = "2026-06-17"

# Data-driven mapping derived from the actual (account_family, cost_basis) cross-tab:
#   (main,  ge)             -> GE buy/sell pricing & realization; needs GE.
#   (f2p,   ge)             -> GE buy/sell pricing & realization; needs GE.
#   (ironman, gather/sawmill) -> self-supplied (gathered / sawmill); no GE => iron-viable.
# Keyed on cost_basis (the source of truth already on each record).
COST_BASIS_MAP = {
    # cost_basis value -> (pricing_basis, realization_channel, requires_ge)
    "ge":             ("ge",   "ge",  True),
    "gather/sawmill": ("none", "n/a", False),
}


def main():
    with open(PATH) as f:
        d = json.load(f)

    recs = d["records"]

    # ---- per-record canonical gate fields (originals kept) ----
    unmapped = []
    for r in recs:
        # audience derived from account_family (already equal in source; reassert canonically)
        r["audience"] = r["account_family"]

        cb = r.get("cost_basis")
        if cb not in COST_BASIS_MAP:
            unmapped.append(cb)
            # never fabricate: leave null + (would be) disclosed
            r["pricing_basis"] = None
            r["realization_channel"] = None
            r["requires_ge"] = None
            continue
        pb, rc, rge = COST_BASIS_MAP[cb]
        r["pricing_basis"] = pb
        r["realization_channel"] = rc
        r["requires_ge"] = rge

    if unmapped:
        raise SystemExit(f"Unmapped cost_basis values encountered: {set(unmapped)} "
                         f"-- refusing to fabricate; extend COST_BASIS_MAP from source.")

    # ---- _provenance: fix note + accessed date ----
    prov = d["_provenance"]
    prov["accessed"] = ACCESSED
    fix_note = (
        "2026-06-17 P1 gate + disclosure fix (no re-fetch): added canonical account-gate "
        "fields to every record (audience, pricing_basis, realization_channel, requires_ge) "
        "derived deterministically from existing account_family + cost_basis; originals "
        "(cost_basis, value_basis) retained. Mapping: cost_basis 'ge' (main+f2p) -> "
        "pricing_basis 'ge' / realization_channel 'ge' / requires_ge true; cost_basis "
        "'gather/sawmill' (ironman) -> pricing_basis 'none' / realization_channel 'n/a' / "
        "requires_ge false (methods are self-supplied gathering/skilling, e.g. Barbarian "
        "Fishing, Guardians of the Rift, Wintertodt -- none use high-alch realization, so "
        "the generic 'high_alch' hint was NOT applied to avoid fabrication). Also disclosed "
        "the gold/profit/material source columns dropped at extraction (see "
        "completeness.known_missing[1])."
    )
    notes = prov.get("fix_notes")
    if not isinstance(notes, list):
        notes = []
    notes.append(fix_note)
    prov["fix_notes"] = notes

    # ---- disclosure: previously-dropped gold/profit columns ----
    km = prov["completeness"]["known_missing"]
    dropped_disclosure = {
        "note": (
            "Previously-dropped monetary/material columns: the extractor "
            "(data/raw/parse_html.py) parses ONLY the Level column + XP/h column(s) of each "
            "wiki training table. Every other column in the source tables was intentionally "
            "dropped and is NOT present in any record. Dropped column families include: "
            "GP/h (with/without outfit), GP/XP and Cost/XP, Profit and Profit/h and "
            "Profit/Loss (GE and HA variants), GE/HA prices (Buy/Sell/Diff), material/"
            "ingredient/supply costs, items-made and inputs/outputs counts, volumes, and "
            "per-action breakdowns (XP/cast, XP/bolt, etc.). These are gold-denominated and "
            "price-volatile; they were excluded for the same volatility reason captured in "
            "each record's value_basis. They are recoverable from the cached rendered HTML "
            "in _provenance.raw_files (html_*.html) if a money model is later needed."
        ),
        "dropped_column_families": [
            "GP/h (Gp/Hour, GP/HR, Estimated GP/hr, with/without outfit/blessing)",
            "GP/XP (Gp/Xp, GE Price GP/XP, Cost/XP, Coins Profit Per Exp)",
            "Profit (Profit/h, Profit/Hour, Profit/XP, Profit/Loss, Profit each, "
            "GE & HA variants)",
            "GE/HA prices (Buy, Sell, Diff, Total cost, Money spent, Input cost)",
            "Material/ingredient/supply costs (Material cost(s), Ingredient cost, "
            "Supply cost each, Product/Constructed value)",
            "Counts & throughput (Bars/hr, Planks/hr, Items/hr, # for goal, "
            "Logs needed, Pouches, Ess/lap, inputs/outputs)",
            "Per-action economics (XP/cast, XP/bolt, XP/arrow, Cost/tip, "
            "Profit/bolt, GP/Loop, etc.)",
        ],
        "recoverable_from": "_provenance.raw_files (cached rendered html_*.html)",
        "reason_dropped": (
            "gold-denominated & price-volatile (same rationale as record value_basis); "
            "out of scope for the XP/h-by-level rate domain."
        ),
    }
    km.append(dropped_disclosure)

    # ---- invariants ----
    assert list(d.keys()) == ["_provenance", "records", "_excluded"], list(d.keys())
    assert prov["record_count"] == len(recs), (prov["record_count"], len(recs))
    prov["completeness"]["records_count"] = len(recs)

    with open(PATH, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # ---- report ----
    from collections import Counter
    print("OK. records:", len(recs))
    print("requires_ge:", Counter(r["requires_ge"] for r in recs))
    print("pricing_basis:", Counter(r["pricing_basis"] for r in recs))
    print("realization_channel:", Counter(r["realization_channel"] for r in recs))
    print("audience:", Counter(r["audience"] for r in recs))
    print("known_missing entries now:", len(km))


if __name__ == "__main__":
    main()
