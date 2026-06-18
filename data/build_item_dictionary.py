#!/usr/bin/env python3
"""
Build the CANONICAL ITEM DICTIONARY (domain 17) for Gilded Tome.

Universal item<->id join key for the whole KG, covering ALL items (tradeable
AND untradeable), unlike ge_prices which is GE-only.

Source: OSRS Wiki Bucket API, table 'infobox_item'.
  - id field discovered to be: item_id (returned as an array of stringified ids)
  - page_name = wiki page title; item_name = specific variant display name
  - is_members_only: SMW boolean -> field present as "" when members, absent when f2p
  - default_version: SMW boolean -> field present as "" on the canonical variant row
  - version_anchor: the variant suffix/anchor (e.g. "(8)", "Unpoisoned")

Envelope (frozen, must match sibling domains exactly):
  { "_provenance": {...}, "records": [...], "_excluded": [...] }
  record_count lives INSIDE _provenance (and _provenance.completeness) and == len(records)

Records: { item_id, name, members, page_name, variant_of?, is_variant, is_canonical, version_anchor? }
"""
import json
import subprocess
import sys
import time
import datetime
import urllib.parse

DATA_DIR = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data"
RAW_PATH = f"{DATA_DIR}/raw/item_dictionary_bucket.json"
OUT_PATH = f"{DATA_DIR}/item_dictionary.json"
UA = "GildedTome-data-pipeline/1.0 (contact: aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
PAGE_SIZE = 5000  # hard cap enforced by the Bucket API
FIELDS = ["item_id", "page_name", "item_name", "is_members_only",
          "tradeable", "default_version", "version_anchor"]


def fetch_page(offset):
    sel = ",".join(f"'{f}'" for f in FIELDS)
    q = f"bucket('infobox_item').select({sel}).limit({PAGE_SIZE}).offset({offset}).run()"
    params = {"action": "bucket", "format": "json", "query": q}
    url = API + "?" + urllib.parse.urlencode(params)
    out = subprocess.run(
        ["curl", "-s", "-A", UA, url],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    if "bucket" not in data:
        raise RuntimeError(f"API error at offset {offset}: {data}")
    return data["bucket"]


def fetch_all():
    rows = []
    offset = 0
    while True:
        page = fetch_page(offset)
        rows.extend(page)
        print(f"  offset={offset} -> {len(page)} rows (total {len(rows)})", file=sys.stderr)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(1.0)  # be polite to the wiki
    return rows


def main():
    if "--reuse-raw" in sys.argv:
        print(f"Reusing raw fetch: {RAW_PATH}", file=sys.stderr)
        with open(RAW_PATH) as f:
            rows = json.load(f)["bucket"]
    else:
        print("Fetching infobox_item bucket (paginated, no truncation)...", file=sys.stderr)
        rows = fetch_all()
        # Save raw exactly as fetched
        with open(RAW_PATH, "w") as f:
            json.dump({"bucket": rows}, f, ensure_ascii=False)
        print(f"Wrote raw: {RAW_PATH} ({len(rows)} rows)", file=sys.stderr)

    # First pass: count variants per page_name to decide is_variant
    page_variant_count = {}
    for r in rows:
        pn = r.get("page_name")
        if pn is None:
            continue
        page_variant_count[pn] = page_variant_count.get(pn, 0) + 1

    records = []
    excluded = []

    # stats
    n_rows = len(rows)
    n_id_values = 0
    rows_without_id = 0
    multi_id_rows = 0
    members_true = 0
    members_false = 0
    canonical_count = 0
    variant_records = 0
    dup_ids = {}

    seen_ids = {}
    excluded_kind = {"historical": 0, "beta": 0, "placeholder": 0}

    for r in rows:
        page_name = r.get("page_name")
        item_name = r.get("item_name") or page_name
        ids = r.get("item_id")
        members = "is_members_only" in r  # SMW boolean: present == true
        is_canonical_variant = "default_version" in r
        version_anchor = r.get("version_anchor")
        # tradeable kept for stats only (not a requested record field), captured below

        if not ids:
            # No item_id on this infobox row: cannot join. DISCLOSE in _excluded.
            rows_without_id += 1
            excluded.append({
                "page_name": page_name,
                "item_name": item_name,
                "reason": "infobox_item row has no item_id (not a join-able in-game item id); "
                          "cannot be used as a KG join key",
            })
            continue

        if not isinstance(ids, list):
            ids = [ids]
        if len(ids) > 1:
            multi_id_rows += 1

        page_is_multivariant = page_variant_count.get(page_name, 1) > 1

        for raw_id in ids:
            # ids come back as strings; normalize to int where possible
            try:
                iid = int(str(raw_id).strip())
            except (ValueError, TypeError):
                rid = str(raw_id).strip()
                low = rid.lower()
                if low.startswith("hist"):
                    reason = ("item_id is a historical/removed-graphic id (hist-prefixed); "
                              "not a current live join key")
                    excluded_kind["historical"] += 1
                elif low.startswith("beta"):
                    reason = ("item_id is a beta/Leagues placeholder id (beta-prefixed); "
                              "not a live game item id")
                    excluded_kind["beta"] += 1
                else:
                    reason = ("item_id is a non-numeric placeholder (e.g. 'N/A'/'undefined'); "
                              "no real in-game id")
                    excluded_kind["placeholder"] += 1
                excluded.append({
                    "page_name": page_name,
                    "item_name": item_name,
                    "raw_item_id": raw_id,
                    "reason": reason,
                })
                continue

            n_id_values += 1
            if members:
                members_true += 1
            else:
                members_false += 1

            rec = {
                "item_id": iid,
                "name": item_name,
                "members": members,
                "page_name": page_name,
                "is_variant": bool(page_is_multivariant),
                "is_canonical": bool(is_canonical_variant) if page_is_multivariant else True,
            }
            if page_is_multivariant:
                rec["variant_of"] = page_name
                variant_records += 1
            if version_anchor:
                rec["version_anchor"] = version_anchor

            if rec["is_canonical"]:
                canonical_count += 1

            if iid in seen_ids:
                dup_ids.setdefault(iid, [seen_ids[iid]]).append(item_name)
            else:
                seen_ids[iid] = item_name

            records.append(rec)

    # Flag ambiguous ids: one in-game item_id that maps to >1 record.
    # Legitimate in OSRS data (e.g. every clue-scroll step page shares one id;
    # some league/variant anchors share an id). Surfaced so KG consumers joining
    # on item_id know the join is not always 1:1.
    id_to_count = {}
    for r in records:
        id_to_count[r["item_id"]] = id_to_count.get(r["item_id"], 0) + 1
    ambiguous_ids = {iid for iid, c in id_to_count.items() if c > 1}
    ambiguous_record_count = 0
    cross_page_ambiguous_ids = set()
    id_to_pages = {}
    for r in records:
        id_to_pages.setdefault(r["item_id"], set()).add(r["page_name"])
    for r in records:
        if r["item_id"] in ambiguous_ids:
            r["id_is_ambiguous"] = True
            ambiguous_record_count += 1
            if len(id_to_pages[r["item_id"]]) > 1:
                cross_page_ambiguous_ids.add(r["item_id"])

    # Sort records by item_id for stable, deterministic output
    records.sort(key=lambda x: (x["item_id"], x["name"] or ""))

    accessed = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record_count = len(records)

    provenance = {
        "domain": "item_dictionary",
        "source_urls": [
            "https://oldschool.runescape.wiki/api.php?action=bucket&query=bucket('infobox_item')..."
        ],
        "source_query": (
            "bucket('infobox_item').select('item_id','page_name','item_name',"
            "'is_members_only','tradeable','default_version','version_anchor')"
            ".limit(5000).offset(N).run()  [paginated, N=0,5000,...]"
        ),
        "accessed": accessed,
        "license": "CC BY-NC-SA 3.0",
        "extraction_method": "script",
        "raw_files": ["data/raw/item_dictionary_bucket.json"],
        "id_field_used": "item_id",
        "fix_note": (
            "v1 (2026-06-17): created canonical item dictionary (domain 17), the universal "
            "item<->id join key covering ALL items (tradeable AND untradeable), unlike GE-only "
            "ge_prices. id field discovered from infobox_item bucket schema = 'item_id' "
            "(returned as an array of stringified ids; flattened one record per id). "
            "members derived from SMW boolean 'is_members_only' (field present == members true). "
            "Canonical variant per multi-variant page marked via SMW boolean 'default_version'. "
            "Rows without an item_id are not join-able and were moved to _excluded with disclosure."
        ),
        "record_count": record_count,
        "completeness": {
            "bounded_by": "OSRS Wiki infobox_item bucket (every wiki page bearing an {{Infobox Item}})",
            "universe_count": n_rows,
            "records_count": record_count,
            "known_missing": [
                f"{rows_without_id} infobox_item rows carry no item_id field at all (abstract/placeholder "
                f"infoboxes); moved to _excluded, not join-able",
                f"{len(excluded) - rows_without_id} rows have a non-numeric item_id and are excluded "
                f"(not live join keys): {excluded_kind['historical']} historical/removed-graphic "
                f"(hist-prefixed), {excluded_kind['beta']} beta/Leagues placeholders (beta-prefixed), "
                f"{excluded_kind['placeholder']} other placeholders (N/A/undefined). No row mixes a real "
                f"id with a non-numeric one, so no live id is lost by these exclusions",
                "name = item_name (specific variant display name) which may differ from page_name; "
                "page_name retained on every record",
                f"{len(ambiguous_ids)} item_ids map to >1 record ({ambiguous_record_count} records); join "
                f"on item_id is not always 1:1 (e.g. every clue-scroll step page shares one id, some "
                f"league/variant anchors share an id). Records flagged id_is_ambiguous=true; kept (not "
                f"dropped) so the dictionary stays a complete id index",
                "a few very recent ids present in the realtime GE /mapping may not yet appear in the "
                "infobox_item bucket (wiki infobox lag); observed 3 such ids at build time "
                "(Demonic quill, Trinket of vengeance (1)/(2)). Not fabricated here; will appear once "
                "the wiki infobox catches up",
                "no item id is fabricated; rows lacking ids are disclosed, never invented",
            ],
        },
        "domain_stats": {
            "infobox_rows_total": n_rows,
            "rows_without_item_id_excluded": rows_without_id,
            "excluded_total": len(excluded),
            "excluded_historical_ids": excluded_kind["historical"],
            "excluded_beta_ids": excluded_kind["beta"],
            "excluded_placeholder_ids": excluded_kind["placeholder"],
            "rows_with_multiple_item_ids": multi_id_rows,
            "id_values_total": n_id_values,
            "records_count": record_count,
            "distinct_item_ids": len(seen_ids),
            "duplicate_item_id_count": len(dup_ids),
            "ambiguous_records_flagged": ambiguous_record_count,
            "cross_page_duplicate_ids": len(cross_page_ambiguous_ids),
            "members_true": members_true,
            "members_false": members_false,
            "variant_records": variant_records,
            "canonical_records": canonical_count,
            "schema_note": (
                "Each record is one in-game item id. variant_of/is_variant link variants that share a "
                "wiki page_name; is_canonical marks the page's default_version variant (single-variant "
                "pages are canonical by definition). members = members-only flag."
            ),
        },
    }

    envelope = {
        "_provenance": provenance,
        "records": records,
        "_excluded": excluded,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    # Report
    print("\n=== BUILD COMPLETE ===", file=sys.stderr)
    print(f"id field used: item_id", file=sys.stderr)
    print(f"infobox rows total: {n_rows}", file=sys.stderr)
    print(f"record_count: {record_count}", file=sys.stderr)
    print(f"distinct item_ids: {len(seen_ids)}", file=sys.stderr)
    print(f"duplicate item_ids: {len(dup_ids)}", file=sys.stderr)
    print(f"excluded (no/invalid id): {len(excluded)}", file=sys.stderr)
    print(f"members true/false: {members_true}/{members_false}", file=sys.stderr)
    print(f"variant records / canonical records: {variant_records}/{canonical_count}", file=sys.stderr)
    if dup_ids:
        sample = list(dup_ids.items())[:5]
        print(f"sample dup ids: {sample}", file=sys.stderr)
    print(f"output: {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
