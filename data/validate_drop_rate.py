#!/usr/bin/env python3
"""Drop-rate dataset validator (iron-gate tradition; design §9). Exits non-zero
on any violation. Re-parses every numeric rate from its raw string to prove no
fabrication. Prints a coverage report (by node_type + status; slayer-resolution
line; ToA-canonical disclosure)."""
from __future__ import annotations

import argparse, json, math, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from data._rarity_grammar import parse_rarity  # noqa: E402

errors: list[str] = []
def check(cond, msg):
    if not cond: errors.append(msg)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "drop_rates.json"))
    ap.add_argument("--data", default=HERE)
    ns = ap.parse_args()
    doc = json.load(open(ns.dataset, encoding="utf-8"))
    records = doc["records"]
    idict = json.load(open(os.path.join(ns.data, "item_dictionary.json"), encoding="utf-8"))
    item_ids = {r["item_id"] for r in idict["records"]}
    clog_ids = {r["item_id"] for r in
                json.load(open(os.path.join(ns.data, "collection_log.json"), encoding="utf-8"))["records"]}

    for r in records:
        rate = r.get("drop_rate"); status = r.get("drop_rate_status"); raw = r.get("drop_rate_raw")
        # Inv 1: rate null or in (0,1]
        check(rate is None or (isinstance(rate, (int, float)) and 0 < rate <= 1),
              f"drop_rate out of range: {r['item']}@{r['source']} = {rate}")
        # Inv 2: no fabrication — numeric rate must re-parse from raw to the same value
        if rate is not None:
            check(bool(raw), f"fabricated rate (no raw): {r['item']}@{r['source']}")
            if raw:
                rp, _rolls, _st = parse_rarity(raw)
                check(rp is not None and math.isclose(rp, rate, rel_tol=1e-6),
                      f"raw does not re-parse to rate (fabricated?): {r['item']}@{r['source']} raw={raw!r} rate={rate}")
        # Inv 3: null rate -> a real reason (status != sourced)
        if rate is None:
            check(status and status != "sourced",
                  f"null rate with status 'sourced': {r['item']}@{r['source']}")
        # Inv 4: rolls int >= 1
        check(isinstance(r.get("rolls"), int) and r["rolls"] >= 1,
              f"rolls must be int>=1: {r['item']}@{r['source']} = {r.get('rolls')}")
        # Inv 5: item_id is a REAL, in-scope id. The id-reality guarantee is met by
        # resolving in item_dictionary.json OR being a genuine collection-log id
        # (collection_log.json is itself the wiki-sourced clog-scope source of truth).
        # 19 clog items (Unsired, Dossier, Tea flask, satchels, ...) carry real
        # in-game ids that the infobox_item-built dictionary snapshot simply lacks;
        # those ids are NOT fabricated and stay in clog scope, so they pass. An id
        # that is neither in the dictionary NOR in the clog would be fabricated/out
        # of scope and still fails -- the anti-fabrication/scope guarantee is intact.
        check(r["item_id"] in clog_ids, f"item_id outside collection-log scope: {r['item_id']}")
        check(r["item_id"] in item_ids or r["item_id"] in clog_ids,
              f"item_id neither in dictionary nor collection-log: {r['item_id']}")
        # Inv 6: variants well-formed AND never-fabricated. The alt-rarity work added
        # numeric variant rates, so the Inv-2 re-parse guard must apply here too: a
        # numeric variant rate must have a raw string that re-parses to it.
        for v in r.get("variants", []):
            check("condition" in v, f"variant missing condition: {r['item']}@{r['source']}")
            vr = v.get("drop_rate")
            check(vr is None or (isinstance(vr, (int, float)) and 0 < vr <= 1),
                  f"variant rate out of range: {r['item']}@{r['source']} {v}")
            if vr is not None:
                vraw = v.get("drop_rate_raw")
                check(bool(vraw), f"fabricated variant rate (no raw): {r['item']}@{r['source']} {v}")
                if vraw:
                    vrp, _vr2, _vs2 = parse_rarity(vraw)
                    check(vrp is not None and math.isclose(vrp, vr, rel_tol=1e-6),
                          f"variant raw does not re-parse to rate (fabricated?): "
                          f"{r['item']}@{r['source']} raw={vraw!r} rate={vr}")

    # Inv 7: envelope consistency
    check(doc.get("_provenance", {}).get("record_count") == len(records),
          "record_count != len(records)")
    check(isinstance(doc.get("_excluded"), list), "_excluded missing/not a list")

    if errors:
        print(f"DROP-RATE VALIDATION FAILED -- {len(errors)} violation(s):")
        for e in errors[:50]: print("  -", e)
        return 1
    # coverage report (informational; spec §9.8)
    by_status = Counter(r["drop_rate_status"] for r in records)
    by_node = Counter(r["source_node_type"] for r in records)
    clog = json.load(open(os.path.join(ns.data, "collection_log.json"), encoding="utf-8"))["records"]
    slayer_ids = {c["item_id"] for c in clog if c.get("source") == "Slayer"}
    resolved_ids = {r["item_id"] for r in records if r["drop_rate_status"] == "sourced"}
    slayer_resolved = len(slayer_ids & resolved_ids)
    toa = sum(1 for r in records if r["source"] == "Chest (Tombs of Amascut)")
    # Disclosed residual (spec coverage §8): clog items whose real in-game id is
    # absent from the infobox_item-built dictionary snapshot (e.g. Unsired, Dossier).
    dict_gap = sorted({r["item_id"] for r in records if r["item_id"] not in item_ids})
    print("DROP-RATE VALIDATION PASSED -- all invariants hold.")
    print(f"  records: {len(records)} | sourced: {by_status.get('sourced', 0)}")
    print(f"  by status: {dict(by_status)}")
    print(f"  by source_node_type: {dict(by_node)}")
    print(f"  slayer-bundle uniques resolved to a real monster rate: {slayer_resolved}/{len(slayer_ids)}")
    print(f"  ToA records (invocation-canonical, scaling disclosed in variants): {toa}")
    print(f"  clog ids not in item_dictionary snapshot (real, in-scope; disclosed residual): "
          f"{len(dict_gap)} {dict_gap}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
