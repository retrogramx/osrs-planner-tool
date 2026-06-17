#!/usr/bin/env python3
"""
Re-resolve the numeric `item_id` join key on every record in items_equipment.json
against item_dictionary.json (the canonical FULL item set: tradeable AND
untradeable), superseding the earlier ge_prices.json-only join (which could only
resolve tradeable items, capping coverage at ~47.7%).

Layered, no-fabrication matching (first layer that yields exactly ONE id wins):
  L1 item (specific variant name) -> dict.name, unique numeric id
  L2 page_name                    -> dict.page_name, unique numeric id
  L3 page_name -> dict.page_name candidates, exactly one is_canonical
  L4 item      -> dict.name candidates, exactly one is_canonical
  L5 page_name -> dict.page_name canonical candidates, exactly one with members==record.members
  L6 item      -> dict.name canonical candidates, exactly one with members==record.members

Anything that does not yield a single id stays item_id=null (no fuzzy matching,
no arbitrary pick among equal candidates). Unresolved counts are DISCLOSED in
_provenance.completeness.known_missing.

Preserves the frozen envelope exactly: {_provenance, records, _excluded};
payload key "records"; _provenance.record_count == len(records).
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

DATA = os.path.dirname(os.path.abspath(__file__))
ITEMS_PATH = os.path.join(DATA, "items_equipment.json")
DICT_PATH = os.path.join(DATA, "item_dictionary.json")
ACCESSED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with open(ITEMS_PATH) as f:
    items = json.load(f)
with open(DICT_PATH) as f:
    dct = json.load(f)

# --- build dictionary lookups (numeric ids only) -------------------------
by_name = defaultdict(list)   # lower(name) -> [dict_record, ...]
by_page = defaultdict(list)   # lower(page_name) -> [dict_record, ...]
for dr in dct["records"]:
    iid = dr.get("item_id")
    if not isinstance(iid, int):          # only live numeric join keys
        continue
    nm = dr.get("name")
    pg = dr.get("page_name")
    if isinstance(nm, str):
        by_name[nm.lower()].append(dr)
    if isinstance(pg, str):
        by_page[pg.lower()].append(dr)


def resolve(rec):
    """Return (item_id_or_None, layer_label)."""
    item = rec.get("item")
    page = rec.get("page_name")
    members = rec.get("members")
    il = item.lower() if isinstance(item, str) else None
    pl = page.lower() if isinstance(page, str) else None
    ncands = by_name.get(il, []) if il is not None else []
    pcands = by_page.get(pl, []) if pl is not None else []

    if len(ncands) == 1:
        return ncands[0]["item_id"], "L1_item_unique"
    if len(pcands) == 1:
        return pcands[0]["item_id"], "L2_page_unique"

    pcanon = [c for c in pcands if c.get("is_canonical")]
    ncanon = [c for c in ncands if c.get("is_canonical")]
    if len(pcanon) == 1:
        return pcanon[0]["item_id"], "L3_page_canonical"
    if len(ncanon) == 1:
        return ncanon[0]["item_id"], "L4_item_canonical"

    pcm = [c for c in pcanon if c.get("members") == members]
    ncm = [c for c in ncanon if c.get("members") == members]
    if len(pcm) == 1:
        return pcm[0]["item_id"], "L5_page_canonical_members"
    if len(ncm) == 1:
        return ncm[0]["item_id"], "L6_item_canonical_members"

    return None, "UNRESOLVED"


records = items["records"]
old_non_null = sum(1 for r in records if r.get("item_id") is not None)

layer_counts = defaultdict(int)
matched = 0
unmatched_tradeable = []
unmatched_other = 0
for r in records:
    iid, layer = resolve(r)
    layer_counts[layer] += 1
    if iid is not None:
        matched += 1
    else:
        if r.get("tradeable") is True:
            nm = r.get("item")
            if isinstance(nm, str):
                unmatched_tradeable.append(nm)
        else:
            unmatched_other += 1
    # Rebuild record with item_id first; preserve all other keys/values/order.
    new_r = {"item_id": iid}
    for k, v in r.items():
        if k != "item_id":
            new_r[k] = v
    r.clear()
    r.update(new_r)

unmatched_total = len(records) - matched
distinct_unmatched_tradeable = sorted(set(unmatched_tradeable))

# --- update _provenance --------------------------------------------------
prov = items["_provenance"]
prov["accessed"] = ACCESSED

src = prov.setdefault("source_urls", [])
dict_src = ("data/item_dictionary.json (canonical FULL item<->id join key; OSRS "
            "Wiki infobox_item bucket; covers tradeable AND untradeable items)")
if dict_src not in src:
    src.append(dict_src)

fix_note = (
    f"[{ACCESSED}] re-resolved `item_id` against data/item_dictionary.json (the "
    f"canonical FULL item set, tradeable AND untradeable), superseding the "
    f"earlier ge_prices-only join. Layered exact-match (item->name, "
    f"page_name->page_name, then single is_canonical, then single canonical with "
    f"matching members flag); first layer yielding exactly one numeric id wins. "
    f"Non-null item_id coverage lifted {old_non_null} -> {matched} of "
    f"{len(records)} records ({round(100*old_non_null/len(records),1)}% -> "
    f"{round(100*matched/len(records),1)}%). {unmatched_total} remain null and "
    f"are disclosed in completeness.known_missing 'item_id join key "
    f"(unresolved)'. No item_id was fabricated; no fuzzy matching."
)
prov["fix_notes"] = prov.get("fix_notes", []) + [fix_note]

# Update the EXISTING 'item_id join key (unresolved)' disclosure in place
# (do not append a duplicate); fall back to creating it if absent.
km = prov.setdefault("completeness", {}).setdefault("known_missing", [])
why = (
    "item_id is resolved by exact (case-insensitive) match against "
    "data/item_dictionary.json (the canonical full item<->id index for both "
    "tradeable and untradeable items), using a layered strategy that only "
    "accepts a single unambiguous numeric id (specific name, then page name, "
    "then single is_canonical, then single canonical matching the members "
    f"flag). {unmatched_total} of {len(records)} equipment records still have no "
    "single unambiguous id and are set to item_id=null. These fall into two "
    f"groups: (a) records whose name/page has NO numeric id in the dictionary "
    "(beta/Leagues placeholders e.g. '(beta)' suffixes, Trailblazer/Leagues "
    "tools, corrupted PvP-armour '(c)' variants, and a few very recent items "
    "not yet carried in the wiki infobox_item bucket); and (b) records whose "
    "name/page maps to MULTIPLE numeric ids with no single canonical (e.g. "
    "'Crate of fish', 'Black mask (i)', the imbued/trimmed cape and mask "
    "duplicates), where picking one id would be fabrication. No fuzzy matching "
    f"was applied. Of the unresolved, {unmatched_other} are untradeable/non-GE "
    f"items and {len(distinct_unmatched_tradeable)} are distinct "
    "tradeable-flagged names."
)
entry = {
    "what": "item_id join key (unresolved)",
    "count": unmatched_total,
    "why": why,
    "unmatched_tradeable_names": distinct_unmatched_tradeable,
}
for i, k in enumerate(km):
    if isinstance(k, dict) and k.get("what") == "item_id join key (unresolved)":
        km[i] = entry
        break
else:
    km.append(entry)

# Derived coverage stats (non-binding).
ds = prov.setdefault("domain_stats", {})
ds["records_with_item_id"] = matched
ds["records_without_item_id"] = unmatched_total
ds["item_id_match_layers"] = dict(sorted(layer_counts.items()))

# record_count must equal len(records); reassert the contract.
prov["record_count"] = len(records)

# --- envelope invariants -------------------------------------------------
assert list(items.keys()) == ["_provenance", "records", "_excluded"], list(items.keys())
assert prov["record_count"] == len(records)
assert matched == sum(1 for r in records if isinstance(r.get("item_id"), int))
assert unmatched_total == sum(1 for r in records if r.get("item_id") is None)

with open(ITEMS_PATH, "w") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"records:           {len(records)}")
print(f"old non-null:      {old_non_null} ({round(100*old_non_null/len(records),2)}%)")
print(f"new non-null:      {matched} ({round(100*matched/len(records),2)}%)")
print(f"still null:        {unmatched_total}")
print(f"  untradeable:     {unmatched_other}")
print(f"  tradeable names: {len(distinct_unmatched_tradeable)}")
print("layers:")
for k in sorted(layer_counts):
    print(f"  {k}: {layer_counts[k]}")
