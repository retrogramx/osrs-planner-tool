#!/usr/bin/env python3
"""Deterministic parser for the OSRS Wiki combat_achievement Bucket API data.

Reads the raw Bucket API response
(data/raw/combat_achievement_bucket.json) and normalizes each row into the
frozen domain record shape, writing the enveloped JSON to
data/combat_achievements.json.

Source: OSRS Wiki Bucket API (action=bucket) — bucket('combat_achievement').
Content licensed CC BY-NC-SA 3.0 (oldschool.runescape.wiki).

No heuristics / no inference of facts: id, name, monster, task, tier, type
and league_region are taken verbatim from the API. The only derived field is
`points`, computed from the verified per-tier point map (see TIER_POINTS),
which was cross-checked against the rendered Combat Achievements points table
on the wiki (Easy=1, Medium=2, Hard=3, Elite=4, Master=5, Grandmaster=6).
"""
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(HERE, "raw", "combat_achievement_bucket.json")
OUT_PATH = os.path.join(HERE, "combat_achievements.json")

DOMAIN = "combat_achievements"

SOURCE_URL = (
    "https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query="
    "bucket('combat_achievement').select('id','name','monster','task','tier',"
    "'type','league_region').limit(5000).run()"
)
# Secondary source: per-task tier points table, verified on the page below.
POINTS_SOURCE_URL = "https://oldschool.runescape.wiki/w/Combat_Achievements"

RAW_FILES = [
    "data/raw/combat_achievement_bucket.json",
]

# Verified against the wiki "Points per task" table (Total tasks 637, total
# points 2630). Bucket tier string is the key.
TIER_POINTS = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
    "Elite": 4,
    "Master": 5,
    "Grandmaster": 6,
}

# Expected per-tier task counts from the same wiki table, for completeness audit.
EXPECTED_TIER_COUNTS = {
    "Easy": 41,
    "Medium": 60,
    "Hard": 85,
    "Elite": 162,
    "Master": 168,
    "Grandmaster": 121,
}
EXPECTED_TOTAL = 637  # wiki "Total" row


def normalize(row):
    """Map a single Bucket row -> normalized record. Facts verbatim; points derived."""
    tier = row.get("tier")
    league_region = row.get("league_region")
    record = {
        "id": row.get("id"),
        "name": row.get("name"),
        "monster": row.get("monster"),
        "task": row.get("task"),
        "tier": tier,
        "type": row.get("type"),
        "points": TIER_POINTS.get(tier),
    }
    # league_region is provided by the bucket; preserve it (non-binding metadata).
    if league_region not in (None, ""):
        record["league_region"] = league_region
    return record


def main():
    with open(RAW_PATH) as f:
        data = json.load(f)
    rows = data["bucket"]

    records = [normalize(r) for r in rows]

    # ---- completeness audit (no silent truncation) -------------------------
    from collections import Counter

    tier_counts = Counter(r["tier"] for r in records)
    type_counts = Counter(r["type"] for r in records)

    known_missing = []
    # any record whose tier had no point mapping (unexpected new tier string)
    unmapped = sorted({r["tier"] for r in records if r["points"] is None})
    for t in unmapped:
        known_missing.append(f"tier '{t}' has no verified point mapping")
    # per-tier count drift vs. the wiki points table
    for tier, expected in EXPECTED_TIER_COUNTS.items():
        got = tier_counts.get(tier, 0)
        if got != expected:
            known_missing.append(
                f"tier '{tier}' count {got} != wiki table {expected}"
            )
    # duplicate ids
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        known_missing.append("duplicate id values present")

    total_points = sum(p for p in (r["points"] for r in records) if p)

    out = {
        "_provenance": {
            "domain": DOMAIN,
            "source_urls": [SOURCE_URL, POINTS_SOURCE_URL],
            "source_query": None,
            "accessed": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": RAW_FILES,
            "record_count": len(records),
            "completeness": {
                "bounded_by": "OSRS Wiki combat_achievement bucket (full task universe)",
                "universe_count": EXPECTED_TOTAL,
                "records_count": len(records),
                "known_missing": known_missing,
            },
            "domain_stats": {
                "tier_counts": dict(sorted(tier_counts.items())),
                "type_counts": dict(sorted(type_counts.items())),
                "tier_points": TIER_POINTS,
                "total_points_available": total_points,
                "id_min": min(ids),
                "id_max": max(ids),
            },
        },
        "records": records,
        "_excluded": [],
    }

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("records:", len(records))
    print("tiers:", dict(sorted(tier_counts.items())))
    print("types:", dict(sorted(type_counts.items())))
    print("total_points_available:", total_points)
    print("known_missing:", known_missing)
    print("wrote:", OUT_PATH)


if __name__ == "__main__":
    main()
