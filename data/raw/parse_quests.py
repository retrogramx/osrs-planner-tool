#!/usr/bin/env python3
# Source: https://oldschool.runescape.wiki/w/Module:Questreq/data (?action=raw)
# License: CC BY-NC-SA 3.0 (Old School RuneScape Wiki)
# Provenance: parses data/raw/questreq_data.lua -> data/quests.json (Gilded Tome)
"""data/quests.json builder. Parsing logic lives in questreq_parse.py (DRY);
this script adds the provenance envelope + file I/O."""
import json
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from questreq_parse import parse_questreq_lua  # noqa: E402

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questreq_data.lua")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quests.json")

with open(RAW, encoding="utf-8") as f:
    records = parse_questreq_lua(f.read())

all_names = {r["name"] for r in records}
known_missing = sorted({
    p["quest"] for r in records for p in r["prereqs"] if p["quest"] not in all_names
})
type_counts = {}
for r in records:
    type_counts[r["node_type"]] = type_counts.get(r["node_type"], 0) + 1

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
envelope = {
    "_provenance": {
        "domain": "quests",
        "source_urls": ["https://oldschool.runescape.wiki/w/Module:Questreq/data?action=raw"],
        "source_query": None,
        "accessed": now,
        "license": "CC BY-NC-SA 3.0",
        "extraction_method": "script",
        "raw_files": ["data/raw/questreq_data.lua",
                      "data/raw/questreq_data.lua.PROVENANCE.txt",
                      "data/raw/parse_quests.py", "data/raw/questreq_parse.py"],
        "record_count": len(records),
        "completeness": {
            "bounded_by": "Module:Questreq/data top-level entries",
            "universe_count": len(records),
            "records_count": len(records),
            "known_missing": known_missing,
            "known_missing_note": (
                "known_missing = quest names referenced as prereqs but absent as their own "
                "Questreq entry (dangling targets). Questreq only lists nodes that HAVE "
                "requirements, so prereq-free quests are not module keys; a source property, "
                "not a capture gap."
            ),
        },
        "domain_stats": {
            "node_type_counts": type_counts,
            "prereq_edge_count": sum(len(r["prereqs"]) for r in records),
            "skill_req_count": sum(len(r["skill_reqs"]) for r in records),
            "in_progress_stage_prereq_count": sum(
                1 for r in records for p in r["prereqs"] if p["stage"] == "in_progress"),
            "dangling_prereq_count": len(known_missing),
            "note": ("Diaries here (node_type='diary') must be deduped against the "
                     "achievement_diaries domain. node_type classified by source section."),
        },
    },
    "records": records,
    "_excluded": [],
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(envelope, f, ensure_ascii=False, indent=2)
print("records:", len(records), "type_counts:", type_counts,
      "known_missing:", len(known_missing))
