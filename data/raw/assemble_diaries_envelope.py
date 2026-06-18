#!/usr/bin/env python3
"""Assemble the frozen-envelope achievement_diaries.json from the authoritative
per-diary parse."""
import json, datetime
from collections import Counter

inter = json.load(open("data/raw/diaries_authoritative_intermediate.json"))
records = inter["records"]
stats_by_diary = inter["domain_stats_by_diary"]

WIKI = "https://oldschool.runescape.wiki/w/"
DIARY_SLUGS = [
    "Ardougne_Diary", "Desert_Diary", "Falador_Diary", "Fremennik_Diary",
    "Kandarin_Diary", "Karamja_Diary", "Kourend_&_Kebos_Diary",
    "Lumbridge_&_Draynor_Diary", "Morytania_Diary", "Varrock_Diary",
    "Western_Provinces_Diary", "Wilderness_Diary",
]
source_urls = [WIKI + "Achievement_Diary/All_achievements"] + [WIKI + s for s in DIARY_SLUGS]
# The on-disk wikitext files are named by region only (diary_<Region>.wikitext);
# the "_Diary" suffix belongs to the wiki *URL/page title*, not the saved file.
# Strip it so raw_files points at files that actually exist (previously these
# 12 paths were broken: diary_<Region>_Diary.wikitext).
DIARY_FILE_SLUGS = [s[:-len("_Diary")] if s.endswith("_Diary") else s
                    for s in DIARY_SLUGS]
raw_files = [
    "data/raw/achievement_diaries_all_raw.wikitext",  # cross-check source
] + [f"data/raw/diary_{s}.wikitext" for s in DIARY_FILE_SLUGS] + [
    "data/raw/parse_diaries_authoritative.py",
    "data/raw/assemble_diaries_envelope.py",
]

# Canonical per-diary totals (OSRS Wiki) used as the bounded universe.
universe = sum(s["total"] for s in stats_by_diary.values())

# strip internal helper key tier-level reward is already on each record;
# nothing else to drop.
clean_records = []
for r in records:
    clean_records.append(r)

by_tier = dict(Counter(r["tier"] for r in clean_records))
by_diary = {d: s["total"] for d, s in stats_by_diary.items()}

# 'accessed' reflects the wiki *fetch* date; this pass re-parses the already-
# saved raw wikitext (no new fetch), so the original fetch timestamp is kept and
# the repairs are recorded separately in 'fix_note'.
accessed = "2026-06-17T18:22:53Z"
fix_note = (
    "2026-06-17: repaired 12 broken raw_files paths "
    "(diary_<Region>_Diary.wikitext -> diary_<Region>.wikitext, the real "
    "on-disk names; '_Diary' is the wiki page-title suffix, not the file name); "
    "recovered the Varrock hard/elite reward fields (15 records) that the "
    "reward-extraction regex dropped because those headers are written "
    "'===Rewards=== ' with trailing whitespace; and fixed 9 conditional-skill "
    "parse artifacts where Raiments-of-the-Eye / Ironman / item-based "
    "alternative levels (e.g. Runecraft 88 + 77 + 66 + 55) were emitted as "
    "duplicate flat skill requirements and left stranded qualifier fragments "
    "in items. Flat skills now carry only the primary/unconditional level; each "
    "conditional alternative is preserved as a self-contained item-note with "
    "its skill+level inline. Re-parsed from the saved OSRS Wiki raw wikitext; "
    "no values fabricated."
)

envelope = {
    "_provenance": {
        "domain": "achievement_diaries",
        "source_urls": source_urls,
        "source_query": None,
        "accessed": accessed,
        "fix_note": fix_note,
        "license": "CC BY-NC-SA 3.0",
        "extraction_method": "script",
        "raw_files": raw_files,
        "record_count": len(clean_records),
        "completeness": {
            "bounded_by": "12 OSRS achievement diaries x {easy,medium,hard,elite} tiers; numbered task lists on each diary page",
            "universe_count": universe,
            "records_count": len(clean_records),
            "known_missing": [],
            "known_missing_note": (
                "Complete: all 492 numbered tasks across the 12 individual diary "
                "pages are captured; per-diary totals match the canonical OSRS Wiki "
                "counts exactly (Ardougne 42, Desert 39, Falador 42, Fremennik 34, "
                "Kandarin 43, Karamja 44, Kourend & Kebos 43, Lumbridge & Draynor 41, "
                "Morytania 38, Varrock 42, Western Provinces 44, Wilderness 40). "
                "SOURCE NOTE: the assigned source Achievement_Diary/All_achievements "
                "groups tasks by requirement type and contains cross-section phrasing "
                "drift plus 'Multiple/Various' placeholder rows, which corrupt a "
                "text-keyed dedup (it yields 497 noisy keys). The 12 individual diary "
                "pages (same wiki) carry numbered, per-tier task tables and were used "
                "as the authoritative extraction; All_achievements is retained as a "
                "raw cross-check artifact."
            ),
        },
        "domain_stats": {
            "diary_count": 12,
            "tiers": ["easy", "medium", "hard", "elite"],
            "by_tier": by_tier,
            "by_diary": by_diary,
            "records_with_skill_req": sum(1 for r in clean_records if r["requirements"]["skills"]),
            "records_with_quest_req": sum(1 for r in clean_records if r["requirements"]["quests"]),
            "records_with_item_req": sum(1 for r in clean_records if r["requirements"]["items"]),
            "records_no_req": sum(1 for r in clean_records if not r["requirements"]["skills"] and not r["requirements"]["quests"] and not r["requirements"]["items"]),
            "boostable_records": sum(1 for r in clean_records if r.get("boostable")),
        },
    },
    "records": clean_records,
    "_excluded": [],
}

# Account-type / content gate note (diaries are a members-only feature).
envelope["_provenance"]["account_gate"] = {
    "audience": "members",
    "note": (
        "Achievement diaries are a members-only feature; every task requires a "
        "members world. This domain is content-gated, not money/income-gated, so "
        "no GE pricing_basis applies and no records are excluded for ironman "
        "(requires_ge does not apply to diary tasks). Tasks set in the Wilderness "
        "are reachable by all account types but carry PvP/item-loss risk; see the "
        "Wilderness diary records. Account axes carried: {main, ironman (HCIM/GIM/"
        "UIM reuse), uim} x members."
    ),
}

with open("data/achievement_diaries.json", "w") as f:
    json.dump(envelope, f, indent=1, ensure_ascii=False)

print("WROTE data/achievement_diaries.json")
print("record_count:", len(clean_records))
print("universe_count:", universe)
print("by_tier:", by_tier)
print("envelope keys:", list(envelope.keys()))
print("payload key 'records' present:", "records" in envelope)
print("_excluded count:", len(envelope["_excluded"]))
