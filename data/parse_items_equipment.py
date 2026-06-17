#!/usr/bin/env python3
"""Build data/items_equipment.json from the two raw Bucket API dumps.

Joins infobox_bonuses (combat stats + slot) with infobox_item (item metadata:
members, high alch, value, quest, tradeable) on page_name, and emits the frozen
output envelope.

KEY MODELLING DECISIONS (documented in the envelope completeness / notes):

1. The equipment universe = infobox_bonuses (every wearable/wieldable item with
   combat bonuses). One record per DISTINCT (page_name, stat-set). The bonuses
   bucket emits exact-duplicate rows (template internals); these are collapsed.
   Pages that genuinely have >1 distinct stat-set (e.g. Crystal shield
   active/inactive, trimmed/untrimmed capes) keep one record per stat-set, tagged
   with stat_variant_index.

2. infobox_bonuses carries NO version_anchor, so a stat-set cannot be bound 1:1
   to a specific item version. Item metadata is therefore taken from the page's
   DEFAULT version (default_version == ""), and the page's available item
   version anchors are listed under requirements/version context. This is
   disclosed in completeness.known_missing.

3. Wield/use SKILL requirements live in the wiki's Module:Equipment /
   SkillClickable template, NOT in either bucket — so requirements.skills is an
   honest null (empty) and disclosed in known_missing. requirements.quests is
   parsed from infobox_item.quest (the quest(s) associated with obtaining the
   item) where present; this is the only structured quest signal available and
   is labelled as 'quest associated with item', not strictly a wield gate.

Booleans come back from the API as "" (true) vs absent (false/unknown).
Content licensed CC BY-NC-SA 3.0 (oldschool.runescape.wiki).
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "items_equipment.json")

ACCESSED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SOURCE_URLS = [
    ("https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query="
     "bucket('infobox_bonuses').select(<stat fields>,'equipment_slot',"
     "'weapon_attack_speed','weapon_attack_range','combat_style').run()"),
    ("https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query="
     "bucket('infobox_item').select('page_name','item_name','version_anchor',"
     "'is_members_only','high_alchemy_value','value','weight','buy_limit',"
     "'default_version','quest','tradeable','examine','release_date').run()"),
    "https://oldschool.runescape.wiki/w/Bucket:Infobox_bonuses",
    "https://oldschool.runescape.wiki/w/Bucket:Infobox_item",
]

RAW_FILES = [
    "data/raw/infobox_bonuses_bucket.json",
    "data/raw/infobox_item_bucket.json",
]

STAT_FIELDS = [
    "stab_attack_bonus", "slash_attack_bonus", "crush_attack_bonus",
    "range_attack_bonus", "magic_attack_bonus",
    "stab_defence_bonus", "slash_defence_bonus", "crush_defence_bonus",
    "range_defence_bonus", "magic_defence_bonus",
    "strength_bonus", "ranged_strength_bonus", "prayer_bonus",
    "magic_damage_bonus",
]
WEAPON_FIELDS = ["weapon_attack_speed", "weapon_attack_range", "combat_style"]

WIKILINK = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


def is_true(v):
    """Bucket boolean: present-empty-string means true; None/absent means false."""
    return v == "" or v is True


def num(v):
    if v is None or v == "":
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def parse_quests(quest_field):
    """Extract quest page names from an infobox_item 'quest' field.

    The field can be 'No', a single [[wikilink]], or several separated by
    commas / <br>. Returns a de-duplicated, order-preserving list (possibly []).
    """
    if not quest_field or quest_field.strip() in ("No", "no", "None"):
        return []
    names = WIKILINK.findall(quest_field)
    if names:
        out = []
        for n in names:
            n = n.strip()
            if n and n not in out:
                out.append(n)
        return out
    # No wikilinks but not 'No' -> keep the literal text verbatim
    txt = quest_field.strip()
    return [txt] if txt else []


def stat_signature(b):
    """Order-stable signature of a bonuses row's non-page content (for dedup)."""
    return json.dumps({k: b.get(k) for k in b if k != "page_name"}, sort_keys=True)


def build_stats(b):
    stats = {}
    for f in STAT_FIELDS:
        stats[f] = num(b.get(f))
    return stats


def main():
    bonuses = json.load(open(os.path.join(RAW, "infobox_bonuses_bucket.json")))["bucket"]
    items = json.load(open(os.path.join(RAW, "infobox_item_bucket.json")))["bucket"]

    # Index item rows by page_name
    items_by_page = defaultdict(list)
    for it in items:
        items_by_page[it["page_name"]].append(it)

    # Collapse exact-duplicate bonuses rows; keep distinct stat-sets per page
    seen_per_page = defaultdict(set)
    page_rows = defaultdict(list)  # page_name -> list of distinct bonuses rows
    for b in bonuses:
        sig = stat_signature(b)
        if sig in seen_per_page[b["page_name"]]:
            continue
        seen_per_page[b["page_name"]].add(sig)
        page_rows[b["page_name"]].append(b)

    records = []
    excluded = []
    unmatched_pages = []
    multivariant_pages = 0
    members_count = 0
    f2p_count = 0
    with_high_alch = 0

    for page_name in sorted(page_rows.keys()):
        rows = page_rows[page_name]
        item_versions = items_by_page.get(page_name, [])
        if not item_versions:
            unmatched_pages.append(page_name)

        # canonical item metadata: prefer default_version, else first row
        default_item = next(
            (i for i in item_versions if is_true(i.get("default_version"))),
            item_versions[0] if item_versions else None,
        )
        version_anchors = [
            i.get("version_anchor") for i in item_versions
            if i.get("version_anchor")
        ]
        # de-dup version anchors, preserve order
        seen_va = []
        for va in version_anchors:
            if va not in seen_va:
                seen_va.append(va)

        multi = len(rows) > 1
        if multi:
            multivariant_pages += 1

        for idx, b in enumerate(rows):
            slot = b.get("equipment_slot")
            members = is_true(default_item.get("is_members_only")) if default_item else None
            if members is True:
                members_count += 1
            elif members is False:
                f2p_count += 1

            high_alch = num(default_item.get("high_alchemy_value")) if default_item else None
            if high_alch is not None:
                with_high_alch += 1
            value = num(default_item.get("value")) if default_item else None

            quests = parse_quests(default_item.get("quest")) if default_item else []

            stats = build_stats(b)
            # weapon-only attributes
            weapon = {}
            for wf in WEAPON_FIELDS:
                v = b.get(wf)
                if wf == "weapon_attack_speed":
                    v = num(v)
                if v is not None:
                    weapon[wf] = v

            rec = {
                "item": (default_item.get("item_name") if default_item else page_name),
                "page_name": page_name,
                "slot": slot,
                "members": members,
                "requirements": {
                    # wield skill requirements are NOT in these buckets (see notes)
                    "skills": {},
                    # quest(s) associated with obtaining the item (from infobox_item)
                    "quests": quests,
                    "quests_basis": "infobox_item.quest (quest associated with item; not strictly a wield gate)",
                },
                "stats": stats,
                "weapon": weapon if weapon else None,
                "ge_value": value,
                "ge_value_basis": "infobox_item 'value' = item store/base value in coins; price-volatile snapshot, NOT a live GE price",
                "high_alch": high_alch,
                "high_alch_basis": "infobox_item 'high_alchemy_value' in coins; iron-realizable income (cast High Level Alchemy); price-volatile snapshot",
                "tradeable": is_true(default_item.get("tradeable")) if default_item else None,
                "buy_limit": num(default_item.get("buy_limit")) if default_item else None,
                "weight": num(default_item.get("weight")) if default_item else None,
                "examine": (default_item.get("examine") if default_item else None),
                "item_versions": seen_va,  # all version anchors on the page (context)
                "stat_variant_index": idx if multi else None,
                "stat_variant_count": len(rows),
                "audience": "all",  # gear is account-type agnostic; high_alch flagged for irons
                "metadata_from_version": (default_item.get("version_anchor") if default_item else None),
                "metadata_matched": default_item is not None,
            }
            records.append(rec)

    out = {
        "_provenance": {
            "domain": "items_equipment",
            "source_urls": SOURCE_URLS,
            "source_query": None,
            "accessed": ACCESSED,
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": RAW_FILES,
            "record_count": len(records),
            "completeness": {
                "bounded_by": "infobox_bonuses bucket (every item with combat bonuses = the equipment universe)",
                "universe_count": len(page_rows),  # distinct equipment pages
                "records_count": len(records),
                "known_missing": [
                    {
                        "what": "wield/use SKILL requirements (e.g. 60 Attack for Dragon scimitar)",
                        "why": "not present in infobox_bonuses or infobox_item; the wiki stores these in Module:Equipment / SkillClickable, which has no Bucket. requirements.skills is empty for every record.",
                    },
                    {
                        "what": "per-version combat stats binding",
                        "why": "infobox_bonuses has no version_anchor, so distinct stat-sets cannot be bound 1:1 to item version anchors. Item metadata (high_alch, value, members, quest) is taken from the page's default version; all version anchors are listed in item_versions.",
                    },
                    {
                        "what": "equipment pages with no infobox_item match",
                        "count": len(unmatched_pages),
                        "pages": unmatched_pages,
                        "why": "very new items present in infobox_bonuses but not yet in infobox_item; stats are still emitted, item metadata fields are null (metadata_matched=false).",
                    },
                    {
                        "what": "quest semantics",
                        "why": "requirements.quests is the quest(s) associated with the item per infobox_item.quest (obtain/related), which is not strictly a wield requirement.",
                    },
                ],
            },
            "domain_stats": {
                "distinct_equipment_pages": len(page_rows),
                "total_records": len(records),
                "pages_with_multiple_stat_variants": multivariant_pages,
                "members_records": members_count,
                "f2p_records": f2p_count,
                "records_with_high_alch": with_high_alch,
                "records_without_item_metadata": sum(1 for r in records if not r["metadata_matched"]),
                "exact_duplicate_bonus_rows_collapsed": len(bonuses) - sum(len(v) for v in page_rows.values()),
                "raw_bonuses_rows_fetched": len(bonuses),
                "raw_item_rows_fetched": len(items),
            },
            "account_type_note": (
                "Equipment is account-type agnostic gear (audience='all'). The members axis is "
                "carried per record. high_alch is iron-realizable income (cast High Level Alchemy); "
                "ge_value is a store/base value snapshot, NOT a live GE price. No method here requires "
                "GE buy/sell, so no record is excluded for ironman accounts."
            ),
        },
        "records": records,
        "_excluded": excluded,
    }

    with open(OUT, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("records:", len(records))
    print("distinct equipment pages:", len(page_rows))
    print("multi-variant pages:", multivariant_pages)
    print("unmatched (no item metadata):", len(unmatched_pages), unmatched_pages)
    print("members:", members_count, "f2p:", f2p_count)
    print("with high_alch:", with_high_alch)
    print("wrote:", OUT)


if __name__ == "__main__":
    main()
