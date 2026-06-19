#!/usr/bin/env python3
"""Cost-layer data validator (iron-gate tradition; design §8.1).

Exits non-zero if any cost-data invariant is violated so it can run in CI /
pre-commit. The committed channel datasets are HAND-CURATED, wiki-verified
source-of-truth covering the golden-set goals + a small representative sample;
BULK WIKI SOURCING IS A DISCLOSED v1 FOLLOW-UP. The item->channels index is
built in-memory at load (no committed derived artifact) so this validator is the
sole gate -- there is no index freshness-guard to run.

Invariants:
  1. Every channel record item_id resolves in item_dictionary.json. The id is
     read from the dataset-SPECIFIC key the loaders require (shop/spawn ->
     item_id; recipes -> output_item_id; gather -> resource_item_id), so a row
     written with the wrong key fails validation here rather than KeyError-ing
     at load.
  2. Every currency ref resolves in currencies.json.
  3. craft/gather input item_ids resolve in item_dictionary.json.
  4. craft/gather output_qty >= 1 (routing divides `total // output_qty`; a 0/
     missing output_qty would be a future ZeroDivisionError).
  5. Gate coherence: no `ge` channel is iron-eligible
     (ge record => requires_ge True AND account_allow == {"main"}).
  6. KG stays cost-free: no price/cost/currency token in kg/*.json.
  7. Shop currency values join to currencies.json.
  8. Envelope consistency: each cost dataset's _provenance.record_count ==
     len(records) and _excluded is a list.

Usage: python3 data/validate_cost.py [--data DATA_DIR] [--kg KG_DIR]
"""
import argparse
import glob
import json
import os
import re
import sys

errors: list[str] = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def item_num(item_id):
    if isinstance(item_id, int):
        return item_id
    if isinstance(item_id, str) and item_id.startswith("item:"):
        try:
            return int(item_id.split(":", 1)[1])
        except ValueError:
            return None
    return None


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=here)
    ap.add_argument("--kg", default=os.path.join(repo, "kg"))
    ns = ap.parse_args()
    data, kg = ns.data, ns.kg

    # --- resolution sets ---
    idict = load(os.path.join(data, "item_dictionary.json"))
    item_ids = {r["item_id"] for r in idict["records"]}
    cur_doc = load(os.path.join(data, "currencies.json"))
    cur_ids = {c["id"] for c in cur_doc["records"]}

    # --- channel datasets (those present; coverage is a disclosed follow-up) ---
    # Each entry: channel -> (filename, id_key). The id_key is the SINGLE key the
    # corresponding loader (channels.load_*) reads for the produced/acquired item
    # id; checking exactly that key catches a row written with the wrong key
    # (which would otherwise KeyError at load) instead of the old loose OR-chain.
    CHANNEL_FILES = {
        "shop": ("shop_prices.json", "item_id"),
        "craft": ("recipes.json", "output_item_id"),
        "gather": ("gather.json", "resource_item_id"),
        "spawn": ("spawns.json", "item_id"),
    }
    PRODUCE = {"craft", "gather"}  # input-bearing channels (output_qty divides)
    n_channel_records = 0
    for channel, (fname, id_key) in CHANNEL_FILES.items():
        fpath = os.path.join(data, fname)
        if not os.path.exists(fpath):
            continue
        doc = load(fpath)
        records = doc["records"]
        # Inv 8: envelope consistency (record_count matches; _excluded is a list).
        prov = doc.get("_provenance", {})
        check(
            prov.get("record_count") == len(records),
            f"[{channel}] _provenance.record_count "
            f"{prov.get('record_count')} != len(records) {len(records)}",
        )
        check(
            isinstance(doc.get("_excluded"), list),
            f"[{channel}] _excluded missing or not a list",
        )
        for rec in records:
            n_channel_records += 1
            iid = rec.get(id_key)
            num = item_num(iid)
            check(
                num in item_ids,
                f"[{channel}] item_id ({id_key}) does not resolve: {iid}",
            )
            cur = rec.get("currency", "currency:coins")
            check(cur in cur_ids, f"[{channel}] currency ref does not resolve: {cur}")
            for inp in (rec.get("inputs") or []):
                in_id = inp["item_id"] if isinstance(inp, dict) else inp[0]
                check(
                    item_num(in_id) in item_ids,
                    f"[{channel}] input item_id does not resolve: {in_id}",
                )
            # Inv 4: a produce row must yield >= 1 (routing's total // output_qty).
            if channel in PRODUCE:
                oq = rec.get("output_qty")
                check(
                    isinstance(oq, int) and oq >= 1,
                    f"[{channel}] output_qty must be >= 1, got {oq!r} for {iid}",
                )
            # Inv 5: ge-gate coherence. DEFENSIVE guard for a FUTURE ge dataset
            # row -- the live ge channel is synthetic (channels.ge_record, built
            # in-memory, never a dataset row), so this never fires on current
            # data. The real ge-is-main-only invariant is tested in
            # tests/cost/test_channels.py.
            if rec.get("channel") == "ge":
                allow = set(rec.get("account_allow") or [])
                check(rec.get("requires_ge") is True, f"[ge] record not requires_ge=True: {iid}")
                check(allow == {"main"}, f"[ge] channel marked iron-eligible: {iid} allow={sorted(allow)}")

    # --- KG stays cost-free ---
    # Conservative substring guard: any "price"/"cost"/"currency" JSON key in a
    # kg/*.json file fails. A future legitimate KG field literally named one of
    # these would be a false positive and require updating this regex.
    COST_TOKENS = re.compile(r'"(price|cost|currency)"', re.I)
    for kgf in sorted(glob.glob(os.path.join(kg, "*.json"))):
        with open(kgf, encoding="utf-8") as f:
            raw = f.read()
        m = COST_TOKENS.search(raw)
        check(m is None, f"[kg] cost token leaked into {os.path.basename(kgf)}: {m.group(0) if m else ''}")

    # --- report ---
    if errors:
        print(f"COST VALIDATION FAILED -- {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1
    print("COST VALIDATION PASSED -- all cost-data invariants hold.")
    print(f"  item_dictionary: {len(item_ids)} resolvable item_ids")
    print(f"  currencies: {len(cur_ids)} ids")
    print(f"  channel records validated: {n_channel_records}")
    print("  NOTE: hand-curated golden-set + sample coverage; bulk wiki sourcing is a v1 follow-up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
