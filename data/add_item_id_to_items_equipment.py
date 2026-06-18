#!/usr/bin/env python3
"""
P1 fix: add a numeric `item_id` join key to every record in items_equipment.json.

Match each record's item name (case-insensitive, exact) against ge_prices.json,
which is the canonical item_id<->name source. Unresolved names get item_id=null
and are disclosed in _provenance.completeness.known_missing (no fabrication).

Preserves the frozen envelope exactly: {_provenance, records, _excluded};
payload key "records"; record_count == len(records).
"""
import json
import os
from collections import Counter
from datetime import datetime, timezone

DATA = os.path.dirname(os.path.abspath(__file__))
ITEMS_PATH = os.path.join(DATA, "items_equipment.json")
GE_PATH = os.path.join(DATA, "ge_prices.json")
ACCESSED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with open(GE_PATH) as f:
    ge = json.load(f)
with open(ITEMS_PATH) as f:
    items = json.load(f)

# Canonical case-insensitive name -> item_id lookup (ge_prices names are
# case-insensitively unique; verified 0 collisions, 0 missing ids/names).
lookup = {r["name"].lower(): r["item_id"] for r in ge["records"]}

records = items["records"]
matched = 0
unmatched_tradeable = []
unmatched_other = 0
for r in records:
    name = r.get("item")
    item_id = lookup.get(name.lower()) if isinstance(name, str) else None
    if item_id is not None:
        matched += 1
    else:
        if r.get("tradeable") is True:
            unmatched_tradeable.append(name)
        else:
            unmatched_other += 1
    # Rebuild record with item_id first so the join key is prominent, but
    # otherwise preserve key order and all existing values byte-for-byte.
    new_r = {"item_id": item_id}
    for k, v in r.items():
        if k != "item_id":
            new_r[k] = v
    r.clear()
    r.update(new_r)

unmatched_total = len(records) - matched
assert unmatched_total == len(unmatched_tradeable) + unmatched_other

# Distinct tradeable names that failed to resolve, sorted, for disclosure.
distinct_unmatched_tradeable = sorted(set(n for n in unmatched_tradeable if n))

# --- update _provenance: fix note + accessed date + disclosure -----------
prov = items["_provenance"]
prov["accessed"] = ACCESSED
# ge_prices is now an upstream source for the join key; record it.
src = prov.setdefault("source_urls", [])
if not any("api_rs.json" in u or "ge_prices" in u for u in src):
    src.append("data/ge_prices.json (canonical item_id<->name join key; OSRS Wiki real-time prices API)")

fix_note = (
    f"[{ACCESSED}] P1 fix: added numeric `item_id` join key to every record by "
    f"exact case-insensitive name match against data/ge_prices.json (canonical "
    f"item_id<->name). Resolved {matched}/{len(records)} records; "
    f"{unmatched_total} unresolved -> item_id=null (see "
    f"completeness.known_missing 'item_id join key (unresolved)'). No item_id "
    f"was fabricated."
)
prov["fix_notes"] = prov.get("fix_notes", []) + [fix_note]

km = prov.setdefault("completeness", {}).setdefault("known_missing", [])
km.append({
    "what": "item_id join key (unresolved)",
    "count": unmatched_total,
    "why": (
        "Added item_id by exact (case-insensitive) name match against "
        "data/ge_prices.json, which only lists items present on the OSRS Wiki "
        "real-time GE prices feed (tradeable items). "
        f"{unmatched_total} of {len(records)} equipment records have no exact "
        "name match and are set to item_id=null. Of these, "
        f"{unmatched_other} are untradeable/non-GE items (e.g. quest, broken, "
        "or holiday gear) that legitimately have no GE entry, and "
        f"{len(distinct_unmatched_tradeable)} are distinct tradeable-flagged "
        "names that did not match exactly (name-form differences such as "
        "variant suffixes, or items absent from the GE feed). No fuzzy matching "
        "was applied to avoid fabricating ids."
    ),
    "unmatched_tradeable_names": distinct_unmatched_tradeable,
})

# Coverage stat for visibility (non-binding, derived).
prov.setdefault("domain_stats", {})["records_with_item_id"] = matched
prov["domain_stats"]["records_without_item_id"] = unmatched_total

# record_count must equal len(records); reassert the contract.
prov["record_count"] = len(records)

assert list(items.keys()) == ["_provenance", "records", "_excluded"], items.keys()
assert prov["record_count"] == len(records)

with open(ITEMS_PATH, "w") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"records: {len(records)}")
print(f"matched (item_id set): {matched}")
print(f"unmatched (item_id null): {unmatched_total}")
print(f"  - untradeable/non-GE: {unmatched_other}")
print(f"  - tradeable-flagged distinct names: {len(distinct_unmatched_tradeable)}")
