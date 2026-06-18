#!/usr/bin/env python3
"""
Re-resolve every numeric item id on banked_xp_dataset.json
(source_item_id, output_item_id, secondaries[].item_id) against RuneLite's
AUTHORITATIVE gameval ItemID constant table -- superseding the earlier
fuzzy/name-matching joins (ge_prices.json, then item_dictionary.json) that
capped coverage well short of complete.

WHY THIS IS EXACT
  The banked-experience plugin (TheStonedTurtle/banked-experience) names every
  item with the RuneLite `ItemID.<SYMBOL>` constant (see its Activity.java /
  ExperienceItem.java / Secondaries.java). Those very SYMBOLs are carried
  verbatim in this dataset's name fields (source_item, output_item,
  secondaries[].item). RuneLite publishes `ItemID.<SYMBOL> = <numericId>` in
  runelite-api gameval/ItemID.java. Looking a SYMBOL up in that table yields the
  exact numeric id -- no name normalization, no fuzzy matching, no ambiguity.

SOURCE
  https://raw.githubusercontent.com/runelite/runelite/master/runelite-api/src/main/java/net/runelite/api/gameval/ItemID.java
  License: RuneLite is BSD 2-Clause; attribution retained. Raw saved to
  data/raw/runelite_itemid.java.

PARSING NOTE (important)
  gameval/ItemID.java declares the canonical item constants at the top level of
  `class ItemID` (each line indented with a SINGLE tab). It ALSO contains nested
  inner classes `Cert` and `Placeholder` whose constants reuse the same SYMBOL
  names but with DIFFERENT ids (the noted/placeholder variants), indented with
  TWO tabs. We parse ONLY the single-tab, top-level constants -- the real item
  ids -- and deliberately ignore the inner-class lines.

NO-FABRICATION POLICY
  - Existing non-null ids are PRESERVED verbatim. Only null slots are filled.
    (For full disclosure, slots whose preserved id DIFFERS from what the
    RuneLite symbol maps to are recorded in
    _provenance.domain_stats.itemid_symbol_divergences_preserved -- nothing is
    mutated, but the divergence is surfaced rather than hidden.)
  - A null slot is filled only if its SYMBOL exists in the top-level ItemID
    table. If a symbol is absent AND matches a known activity-abstraction
    pattern (reanimation spell targets, fossil-size buckets, etc.), it is left
    null and retagged kind="activity_abstraction". Any other still-absent symbol
    is left null and tagged kind="unresolved_item_id". No id is invented.

CROSS-CHECK
  Every newly filled id is checked for membership in item_dictionary.json. Ids
  present in RuneLite's ItemID but absent from the (wiki-derived) dictionary --
  e.g. *_DUMMY / SLAYERGUIDE_* constants -- are still filled (ItemID is the
  authority) and reported as dictionary misses.

Preserves the frozen envelope exactly: {_provenance, records, _excluded};
payload key "records"; _provenance.record_count == len(records) == 784.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

DATA = os.path.dirname(os.path.abspath(__file__))
DS_PATH = os.path.join(DATA, "banked_xp_dataset.json")
DICT_PATH = os.path.join(DATA, "item_dictionary.json")
ITEMID_PATH = os.path.join(DATA, "raw", "runelite_itemid.java")
ITEMID_SOURCE_URL = (
    "https://raw.githubusercontent.com/runelite/runelite/master/"
    "runelite-api/src/main/java/net/runelite/api/gameval/ItemID.java"
)
ACCESSED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")

# Patterns for symbols that are genuinely NOT tradeable/bankable items but
# activity abstractions (reanimation spell targets, fossil-size buckets, etc.).
# Only consulted for symbols ABSENT from the top-level ItemID table, so real
# items whose symbol happens to match (e.g. BIRDHOUSE_OAK, which IS in ItemID)
# are never misclassified.
ABSTRACTION_PATTERNS = [
    re.compile(r"^ARCEUUS_CORPSE"),     # reanimation spell targets
    re.compile(r"^FOSSIL_.*_SIZE$"),    # fossil-size buckets
    re.compile(r"^BIRDHOUSE_.*_TYPE$"), # birdhouse-type abstractions (not the item)
]


def parse_itemid_table(path):
    """SYMBOL -> int for the TOP-LEVEL ItemID constants only (single tab)."""
    table = {}
    pat = re.compile(r"^\tpublic static final int ([A-Za-z0-9_]+) = (-?\d+);")
    with open(path) as f:
        for line in f:
            m = pat.match(line)
            if m:
                table[m.group(1)] = int(m.group(2))
    return table


def is_abstraction(symbol):
    return any(p.search(symbol) for p in ABSTRACTION_PATTERNS)


def main():
    with open(DS_PATH) as f:
        ds = json.load(f)
    with open(DICT_PATH) as f:
        dct = json.load(f)

    itemid = parse_itemid_table(ITEMID_PATH)
    valid_dict_ids = {
        dr["item_id"] for dr in dct["records"] if isinstance(dr.get("item_id"), int)
    }

    records = ds["records"]
    named_slots = 0
    old_non_null = 0           # existing non-null on entry (preserved this run)
    newly_resolved = 0         # null -> filled via ItemID THIS run
    still_null = 0             # null and unresolvable after this run
    resolved_symbols = set()   # symbols filled THIS run
    abstraction_symbols = set()
    unresolved_symbols = set()
    divergences = {}           # symbol -> {"preserved": id, "itemid": id}
    # All id-bearing slots whose symbol IS in the ItemID table, regardless of
    # whether they were filled this run or a prior run -- this is the true
    # "resolved via RuneLite ItemID" population and is what the recorded
    # cross-check stats reflect, so reporting is stable across re-runs.
    itemid_filled = []         # (symbol, id) for every such slot

    def handle(obj, name_key, id_key):
        nonlocal named_slots, old_non_null, newly_resolved, still_null
        symbol = obj.get(name_key)
        if symbol is None:
            return
        named_slots += 1
        cur = obj.get(id_key)
        tid = itemid.get(symbol)
        if cur is not None:
            old_non_null += 1
            if tid is not None:
                if tid != cur:
                    divergences[symbol] = {"preserved": cur, "itemid": tid}
                else:
                    itemid_filled.append((symbol, tid))
            return
        if tid is not None:
            obj[id_key] = tid
            newly_resolved += 1
            resolved_symbols.add(symbol)
            itemid_filled.append((symbol, tid))
        else:
            still_null += 1
            if is_abstraction(symbol):
                abstraction_symbols.add(symbol)
            else:
                unresolved_symbols.add(symbol)

    for rec in records:
        handle(rec, "source_item", "source_item_id")
        handle(rec, "output_item", "output_item_id")
        for s in rec.get("secondaries") or []:
            handle(s, "item", "item_id")

    new_non_null = old_non_null + newly_resolved

    # --- dictionary cross-check (over the full ItemID-resolved population) -
    dict_hits = sum(1 for _, i in itemid_filled if i in valid_dict_ids)
    dict_misses = sorted(
        {(s, i) for s, i in itemid_filled if i not in valid_dict_ids}
    )
    dict_rate = round(100 * dict_hits / len(itemid_filled), 2) if itemid_filled else 100.0

    # --- update _provenance ----------------------------------------------
    prov = ds["_provenance"]
    prov["accessed"] = ACCESSED

    src = prov.setdefault("source_urls", [])
    if ITEMID_SOURCE_URL not in src:
        src.append(ITEMID_SOURCE_URL)

    raw_files = prov.setdefault("raw_files", [])
    if "data/raw/runelite_itemid.java" not in raw_files:
        raw_files.append("data/raw/runelite_itemid.java")

    # license_note: append RuneLite ItemID attribution if not already present.
    lic = prov.get("license_note", "")
    runelite_note = (
        " Numeric item ids are now re-resolved EXACTLY by looking up each item's "
        "RuneLite ItemID constant SYMBOL in RuneLite's gameval ItemID table "
        "(runelite-api gameval/ItemID.java, top-level class constants only); "
        "RuneLite is Copyright the RuneLite authors, licensed BSD 2-Clause, "
        "attribution retained."
    )
    if "gameval ItemID table" not in lic:
        prov["license_note"] = lic + runelite_note

    fix_note = (
        f"[{ACCESSED}] Re-resolved item ids (source_item_id, output_item_id, "
        f"secondaries[].item_id) EXACTLY against RuneLite's authoritative gameval "
        f"ItemID constant table ({ITEMID_SOURCE_URL}, raw at "
        f"data/raw/runelite_itemid.java), superseding the prior name/fuzzy joins. "
        f"Each item's symbolic name IS a RuneLite ItemID constant, so "
        f"ItemID.<SYMBOL> = <id> is an exact lookup (top-level class constants "
        f"only; inner Cert/Placeholder classes deliberately ignored). Existing "
        f"non-null ids preserved verbatim; only null slots filled. Non-null id "
        f"coverage lifted {old_non_null}/{named_slots} -> {new_non_null}/"
        f"{named_slots} ({round(100*old_non_null/named_slots,1)}% -> "
        f"{round(100*new_non_null/named_slots,1)}%); {newly_resolved} slots "
        f"newly resolved across {len(resolved_symbols)} distinct symbols. "
        f"{still_null} slots remain null "
        f"({len(abstraction_symbols)} activity_abstraction symbols, "
        f"{len(unresolved_symbols)} unresolved_item_id symbols). Cross-check: "
        f"{dict_hits}/{len(itemid_filled)} ({dict_rate}%) of all ItemID-resolved "
        f"ids are present in item_dictionary.json; {len(dict_misses)} are "
        f"RuneLite-only (authoritative ItemID id retained, dictionary lacks the "
        f"wiki page). No id fabricated."
    )
    # Re-runnable: append the dated note, but drop any prior RuneLite-ItemID note
    # so repeated runs don't accumulate near-duplicate entries (other-source
    # notes, e.g. the original P0 / dictionary notes, are kept).
    existing = prov.get("fix_note")
    if isinstance(existing, str):
        notes = [existing]
    elif isinstance(existing, list):
        notes = list(existing)
    else:
        notes = []
    notes = [n for n in notes
             if not (isinstance(n, str) and "RuneLite's authoritative gameval" in n)]
    notes.append(fix_note)
    prov["fix_note"] = notes

    # --- rebuild known_missing -------------------------------------------
    comp = prov.setdefault("completeness", {})
    km = comp.setdefault("known_missing", [])
    preserved_other = [
        k for k in km
        if not (isinstance(k, dict)
                and k.get("kind") in ("unresolved_item_id", "activity_abstraction"))
    ]
    new_km = []
    for sym in sorted(abstraction_symbols):
        new_km.append({
            "kind": "activity_abstraction",
            "symbol": sym,
            "reason": ("genuine non-item activity abstraction (e.g. reanimation "
                       "spell target / fossil-size bucket); has no tradeable/"
                       "bankable RuneLite ItemID constant; id intentionally null "
                       "(NOT a data gap)"),
        })
    for sym in sorted(unresolved_symbols):
        new_km.append({
            "kind": "unresolved_item_id",
            "symbol": sym,
            "reason": ("symbol not found in RuneLite's top-level gameval ItemID "
                       "constant table and not a known activity abstraction; id "
                       "left null (no fabrication)"),
        })
    comp["known_missing"] = preserved_other + new_km

    # --- update domain_stats ---------------------------------------------
    st = prov.setdefault("domain_stats", {})
    st["itemid_symbols_resolved_to_numeric_id"] = (len(unresolved_symbols) == 0)
    st["item_id_resolution_source"] = (
        "RuneLite gameval ItemID constant table "
        "(runelite-api/src/main/java/net/runelite/api/gameval/ItemID.java, "
        "top-level class constants); exact SYMBOL->id lookup. "
        "Supersedes earlier item_dictionary.json/ge_prices.json name joins."
    )
    st["named_id_slots_total"] = named_slots
    st["named_id_slots_non_null"] = new_non_null
    st["named_id_slots_null"] = still_null
    st["named_id_slots_non_null_pct"] = round(100 * new_non_null / named_slots, 2)
    st["id_slots_newly_resolved_via_itemid_this_run"] = newly_resolved
    st["distinct_symbols_resolved_via_itemid_this_run"] = len(resolved_symbols)
    st["id_slots_resolved_via_itemid_total"] = len(itemid_filled)
    st["activity_abstraction_symbols"] = sorted(abstraction_symbols)
    st["activity_abstraction_symbol_count"] = len(abstraction_symbols)
    st["unresolved_itemid_symbols"] = sorted(unresolved_symbols)
    st["unresolved_itemid_symbol_count"] = len(unresolved_symbols)
    st["itemid_resolved_ids_in_item_dictionary"] = dict_hits
    st["itemid_resolved_ids_total"] = len(itemid_filled)
    st["itemid_resolved_ids_dictionary_match_pct"] = dict_rate
    st["itemid_resolved_ids_absent_from_dictionary"] = [
        {"symbol": s, "item_id": i} for s, i in dict_misses
    ]
    # Preserved-but-divergent ids: stored id != what the RuneLite symbol says.
    st["itemid_symbol_divergences_preserved"] = [
        {"symbol": s, "preserved_item_id": d["preserved"], "itemid_value": d["itemid"]}
        for s, d in sorted(divergences.items())
    ]
    st["itemid_symbol_divergences_preserved_count"] = len(divergences)

    prov["record_count"] = len(records)

    # --- envelope invariants ---------------------------------------------
    assert list(ds.keys()) == ["_provenance", "records", "_excluded"], list(ds.keys())
    assert prov["record_count"] == len(records) == 784, (prov["record_count"], len(records))

    with open(DS_PATH, "w") as f:
        json.dump(ds, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"named id slots:        {named_slots}")
    print(f"old non-null:          {old_non_null} ({round(100*old_non_null/named_slots,2)}%)")
    print(f"new non-null:          {new_non_null} ({round(100*new_non_null/named_slots,2)}%)")
    print(f"newly resolved:        {newly_resolved} slots / {len(resolved_symbols)} symbols")
    print(f"still null:            {still_null} slots")
    print(f"  activity_abstraction symbols: {len(abstraction_symbols)}")
    print(f"  unresolved_item_id symbols:   {len(unresolved_symbols)}")
    print(f"dict cross-check:      {dict_hits}/{len(itemid_filled)} ({dict_rate}%) of ItemID-resolved ids in item_dictionary")
    print(f"dict misses (RuneLite-only): {len(dict_misses)}")
    for s, i in dict_misses:
        print(f"    {s} = {i}")
    print(f"preserved divergences: {len(divergences)}")
    for s, d in sorted(divergences.items()):
        print(f"    {s}: preserved={d['preserved']} itemid={d['itemid']}")
    print(f"Bones -> {itemid.get('BONES')}")
    print(f"_3DOSESTATRENEWAL -> {itemid.get('_3DOSESTATRENEWAL')}")


if __name__ == "__main__":
    main()
