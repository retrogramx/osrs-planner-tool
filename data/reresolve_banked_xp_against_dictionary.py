#!/usr/bin/env python3
"""
Re-resolve every numeric item id on banked_xp_dataset.json (source_item_id,
output_item_id, secondaries[].item_id) against item_dictionary.json -- the
canonical FULL item<->id index (tradeable AND untradeable) -- superseding the
earlier ge_prices.json-only join (GE/tradeable items only, which capped coverage
at ~40.4%).

NO-FABRICATION POLICY
  - Existing non-null ids are PRESERVED verbatim (all current ids were verified
    to be valid dictionary ids, so preservation is lossless and never regresses
    an already-correct id). Resolution is attempted only for null slots.
  - A null slot is resolved only when a normalized form of its symbolic name
    yields exactly ONE unambiguous numeric id in the dictionary. Disambiguation
    layers, each requiring a single survivor:
        1. name maps to a single item_id (unique)
        2. else: exactly one candidate has is_canonical==True
        3. else: among canonical candidates, exactly one has a page_name with no
           parenthetical qualifier (the bare base item, vs. minigame/quest/POH
           variants like "... (Barbarian Assault)")
    Anything still ambiguous (>1 survivor) stays null -- picking one would be
    fabrication.
  - Name normalization variants are limited to deterministic, verified
    transforms (each only ever produced a single correct dictionary hit and the
    un-transformed form had no item at all):
        base      underscores->spaces, lowercased
        plural    base + "s"            (e.g. SHRIMP->shrimps, *_LOG->* logs)
        arrowtips "arrowheads"->"arrowtips"   (RuneLite gameval vs wiki naming)
        concat_rune  XRUNE -> "x rune"  (e.g. NATURERUNE->nature rune)
        bucket_of "bucket x"->"bucket of x"   (e.g. BUCKET_SAND->bucket of sand)
    No fuzzy/substring matching. No dose/potion or corpse/fossil reverse-
    engineering (those mangled constants have no safe 1:1 wiki name).

Symbols that remain null are DISCLOSED per-symbol in
_provenance.completeness.known_missing (kind=unresolved_item_id) with the exact
normalization keys tried, and summarized in _provenance.domain_stats.

Preserves the frozen envelope exactly: {_provenance, records, _excluded};
payload key "records"; _provenance.record_count == len(records).
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

DATA = os.path.dirname(os.path.abspath(__file__))
DS_PATH = os.path.join(DATA, "banked_xp_dataset.json")
DICT_PATH = os.path.join(DATA, "item_dictionary.json")
ACCESSED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")

with open(DS_PATH) as f:
    ds = json.load(f)
with open(DICT_PATH) as f:
    dct = json.load(f)

# --- build dictionary lookups (numeric ids only) -------------------------
by_name = defaultdict(list)   # lower(name|page_name) -> [dict_record, ...]
valid_ids = set()
for dr in dct["records"]:
    iid = dr.get("item_id")
    if not isinstance(iid, int):
        continue
    valid_ids.add(iid)
    for fld in ("name", "page_name"):
        v = dr.get(fld)
        if isinstance(v, str):
            by_name[v.lower().strip()].append(dr)


def lookup(key):
    """Single unambiguous numeric id for a normalized name key, else None."""
    cands = by_name.get(key)
    if not cands:
        return None
    ids = {c["item_id"] for c in cands}
    if len(ids) == 1:
        return next(iter(ids))
    canon = [c for c in cands if c.get("is_canonical")]
    cids = {c["item_id"] for c in canon}
    if len(cids) == 1:
        return next(iter(cids))
    bare = [c for c in canon if "(" not in (c.get("page_name") or "")]
    bids = {c["item_id"] for c in bare}
    if len(bids) == 1:
        return next(iter(bids))
    return None


def base_key(symbol):
    return symbol.replace("_", " ").lower().strip()


def variant_keys(symbol):
    """(normalized_key, transform_tag) candidates, in priority order."""
    b = base_key(symbol)
    out = [(b, "base"), (b + "s", "plural")]
    if "arrowheads" in b:
        out.append((b.replace("arrowheads", "arrowtips"), "arrowtips"))
    if re.fullmatch(r"[a-z]+rune", b):
        out.append((b[:-4] + " rune", "concat_rune"))
    if b.startswith("bucket "):
        out.append(("bucket of " + b[len("bucket "):], "bucket_of"))
    return out


def resolve(symbol):
    """Return (item_id_or_None, transform_tag_or_None, tried_keys)."""
    tried = []
    for key, tag in variant_keys(symbol):
        tried.append(key)
        iid = lookup(key)
        if iid is not None:
            return iid, tag, tried
    return None, None, tried


# --- sanity: every existing non-null id must be a real dictionary id ------
for rec in ds["records"]:
    slot_ids = [rec.get("source_item_id"), rec.get("output_item_id")]
    slot_ids += [s.get("item_id") for s in (rec.get("secondaries") or [])]
    for sid in slot_ids:
        if sid is not None:
            assert sid in valid_ids, f"stored id {sid} not in dictionary"

# --- walk every named id slot, preserving existing, resolving nulls -------
records = ds["records"]
named_slots = 0
old_non_null = 0           # existing non-null (preserved)
newly_resolved = 0
still_null = 0
layer_counts = defaultdict(int)
still_symbols = {}         # symbol -> sorted tried keys (for disclosure)
resolved_symbols = set()


def handle(obj, name_key, id_key):
    global named_slots, old_non_null, newly_resolved, still_null
    name = obj.get(name_key)
    if name is None:
        return
    named_slots += 1
    cur = obj.get(id_key)
    if cur is not None:
        old_non_null += 1
        return
    iid, tag, tried = resolve(name)
    if iid is not None:
        obj[id_key] = iid
        newly_resolved += 1
        layer_counts[tag] += 1
        resolved_symbols.add(name)
    else:
        still_null += 1
        still_symbols[name] = tried


for rec in records:
    handle(rec, "source_item", "source_item_id")
    handle(rec, "output_item", "output_item_id")
    for s in rec.get("secondaries") or []:
        handle(s, "item", "item_id")

new_non_null = old_non_null + newly_resolved

# --- update _provenance --------------------------------------------------
prov = ds["_provenance"]
prov["accessed"] = ACCESSED

src = prov.setdefault("source_urls", [])
dict_src = ("data/item_dictionary.json (canonical FULL item name<->id join key; "
            "OSRS Wiki infobox_item bucket; covers tradeable AND untradeable)")
if dict_src not in src:
    src.append(dict_src)

fix_note = (
    f"[{ACCESSED}] Re-resolved item ids (source_item_id, output_item_id, "
    f"secondaries[].item_id) against data/item_dictionary.json (the canonical "
    f"FULL item set, tradeable AND untradeable), superseding the ge_prices-only "
    f"(GE/tradeable) join. Existing non-null ids preserved (all were valid "
    f"dictionary ids); only null slots re-resolved, by exact case-insensitive "
    f"match of the symbolic name (underscores->spaces) plus a small set of "
    f"deterministic verified transforms (plural, arrowheads->arrowtips, "
    f"XRUNE->'x rune', 'bucket x'->'bucket of x'), each accepted only when it "
    f"yields a single unambiguous numeric id (unique -> single is_canonical -> "
    f"single bare-page canonical). Non-null id coverage lifted "
    f"{old_non_null}/{named_slots} -> {new_non_null}/{named_slots} named slots "
    f"({round(100*old_non_null/named_slots,1)}% -> "
    f"{round(100*new_non_null/named_slots,1)}%); {newly_resolved} slots newly "
    f"resolved across {len(resolved_symbols)} distinct symbols. {still_null} "
    f"slots ({len(still_symbols)} distinct symbols) remain null and are disclosed "
    f"per-symbol in completeness.known_missing. No id fabricated; no fuzzy "
    f"matching; ambiguous (>1 candidate) names left null."
)
# fix_note has historically been a single string on this dataset; promote to a
# list so prior notes are not lost.
existing = prov.get("fix_note")
if isinstance(existing, str):
    prov["fix_note"] = [existing, fix_note]
elif isinstance(existing, list):
    prov["fix_note"] = existing + [fix_note]
else:
    prov["fix_note"] = [fix_note]

# Rebuild known_missing: keep any non-unresolved entries, replace the per-symbol
# unresolved_item_id disclosures with the current still-null set.
comp = prov.setdefault("completeness", {})
km = comp.setdefault("known_missing", [])
preserved_other = [
    k for k in km
    if not (isinstance(k, dict) and k.get("kind") == "unresolved_item_id")
]
new_km = []
for sym in sorted(still_symbols):
    tried = still_symbols[sym]
    new_km.append({
        "kind": "unresolved_item_id",
        "symbol": sym,
        "tried_name_keys": tried,
        "reason": ("no single unambiguous numeric id in item_dictionary.json "
                   "for any tried normalization key (name absent, or maps to >1 "
                   "id with no single canonical / bare-page base item); id left "
                   "null (no fabrication)"),
    })
comp["known_missing"] = preserved_other + new_km

# --- update domain_stats -------------------------------------------------
ds_stats = prov.setdefault("domain_stats", {})
ds_stats["itemid_symbols_resolved_to_numeric_id"] = (still_null == 0)
ds_stats["item_id_resolution_source"] = (
    "item_dictionary.json name/page_name<->item_id (canonical full item index); "
    "previously ge_prices.json (GE/tradeable only)"
)
ds_stats["named_id_slots_total"] = named_slots
ds_stats["named_id_slots_non_null"] = new_non_null
ds_stats["named_id_slots_null"] = still_null
ds_stats["named_id_slots_non_null_pct"] = round(100 * new_non_null / named_slots, 2)
ds_stats["id_slots_newly_resolved_vs_ge_prices"] = newly_resolved
ds_stats["id_resolution_transform_counts"] = dict(sorted(layer_counts.items()))
ds_stats["unresolved_itemid_symbols"] = sorted(still_symbols)
ds_stats["unresolved_itemid_symbol_count"] = len(still_symbols)

# record_count must equal len(records); reassert the contract.
prov["record_count"] = len(records)

# --- envelope invariants -------------------------------------------------
assert list(ds.keys()) == ["_provenance", "records", "_excluded"], list(ds.keys())
assert prov["record_count"] == len(records)
# Every newly written id is a real dictionary id.
for rec in records:
    chk = [rec.get("source_item_id"), rec.get("output_item_id")]
    chk += [s.get("item_id") for s in (rec.get("secondaries") or [])]
    for sid in chk:
        assert sid is None or sid in valid_ids

with open(DS_PATH, "w") as f:
    json.dump(ds, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"named id slots:      {named_slots}")
print(f"old non-null:        {old_non_null} ({round(100*old_non_null/named_slots,2)}%)")
print(f"new non-null:        {new_non_null} ({round(100*new_non_null/named_slots,2)}%)")
print(f"newly resolved:      {newly_resolved} slots / {len(resolved_symbols)} symbols")
print(f"still null:          {still_null} slots / {len(still_symbols)} symbols")
print("transform counts:")
for k, v in sorted(layer_counts.items()):
    print(f"  {k}: {v}")
