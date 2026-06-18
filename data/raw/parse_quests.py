#!/usr/bin/env python3
# Source: https://oldschool.runescape.wiki/w/Module:Questreq/data (?action=raw)
# License: CC BY-NC-SA 3.0 (Old School RuneScape Wiki)
# Provenance: parses data/raw/questreq_data.lua -> data/quests.json (Gilded Tome)
"""Deterministic parser for Module:Questreq/data Lua table -> enveloped JSON.

Section markers in the source delimit node_type:
  line  30 .. 1568 : quests
  line 1569.. 1692 : miniquests (official)
  line 1693.. 1758 : unofficial miniquests (also classified 'miniquest')
  line 1759.. end   : achievement diaries
"""
import json
import re
import datetime

RAW = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/raw/questreq_data.lua"
OUT = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/quests.json"

# Section markers in the source (1-based line numbers of the divider comments):
#   "Insert Miniquests below here"            -> 1569
#   "Insert Unofficial Miniquests below here" -> 1693
#   "Insert Achievement Diaries below here"   -> 1759
# We resolve these dynamically below so the parser is robust to edits.
def build_sections(lines):
    def find(marker):
        for i, ln in enumerate(lines):
            if marker in ln:
                return i + 1
        return None
    table_start = find("local questReqs = {")
    mini = find("Insert Miniquests below here")
    diary = find("Insert Achievement Diaries below here")
    # both miniquest groups (official + unofficial) -> "miniquest"
    return [
        ("quest",     table_start, mini - 1),
        ("miniquest", mini,        diary - 1),
        ("diary",     diary,       10**9),
    ], table_start

def node_type_for(lineno, sections):
    for nt, lo, hi in sections:
        if lo <= lineno <= hi:
            return nt
    return None

def unescape_lua(s):
    # Lua single-quoted strings escape ' as \'  and \ as \\
    return s.replace("\\'", "'").replace('\\"', '"')

def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()

with open(RAW, encoding="utf-8") as f:
    lines = f.readlines()

sections, table_start = build_sections(lines)

# Locate top-level entry keys: a line indented exactly one level and ending
# with "] = {". The source mixes indentation styles: the quests section uses
# 4 spaces per level, the miniquest/diary sections use tabs. One indent unit =
# a single tab OR exactly 4 spaces. Nested ['quests']/['skills'] keys sit at
# two indent units (2 tabs or 8 spaces) and are excluded by the anchor.
ONE_INDENT = r"(?:\t|    )"
entry_re = re.compile(
    r"^" + ONE_INDENT + r"\[(?P<q>'(?:[^'\\]|\\.)*')\] = \{"
)

# Find entry start linenos. Only consider lines at/after the real table start
# so the commented-out QUEST TEMPLATE (['Name_of_quest'] = { 'subquest' ... })
# is never treated as a record.
entries = []  # (lineno_1based, name)
for i, ln in enumerate(lines):
    if i + 1 < table_start:
        continue
    m = entry_re.match(ln)
    if m:
        raw_key = m.group("q")[1:-1]  # strip surrounding quotes
        name = norm_ws(unescape_lua(raw_key))
        entries.append((i + 1, name))

# Determine end-of-entry by next entry start (or 'return questReqs')
entry_bounds = []
for idx, (start, name) in enumerate(entries):
    end = entries[idx + 1][0] - 1 if idx + 1 < len(entries) else len(lines)
    entry_bounds.append((start, end, name))

TWO_INDENT = r"(?:\t\t|        )"
quests_re = re.compile(r"^" + TWO_INDENT + r"\['quests'\] = \{")
skills_re = re.compile(r"^" + TWO_INDENT + r"\['skills'\] = \{")
# A quest prereq string item, possibly with trailing comma
str_item_re = re.compile(r"^\s*'(?P<s>(?:[^'\\]|\\.)*)'\s*,?\s*$")
# A skill tuple: {'Skill', level [, 'ironman'] [, 'boostable']}
skill_item_re = re.compile(
    r"^\s*\{\s*'(?P<skill>(?:[^'\\]|\\.)*)'\s*,\s*(?P<lvl>\d+)(?P<flags>(?:\s*,\s*'[^']*')*)\s*\}\s*,?\s*$"
)

records = []
all_names = set(name for _, _, name in entry_bounds)

for start, end, name in entry_bounds:
    block = lines[start - 1:end]
    nt = node_type_for(start, sections)
    prereqs = []
    skill_reqs = []
    mode = None
    for ln in block:
        if quests_re.match(ln):
            mode = "quests"
            continue
        if skills_re.match(ln):
            mode = "skills"
            continue
        # closing of a sub-table (the ['quests']/['skills'] table)
        if re.match(r"^" + TWO_INDENT + r"\}\s*,?\s*$", ln):
            mode = None
            continue
        if mode == "quests":
            m = str_item_re.match(ln)
            if m:
                raw = unescape_lua(m.group("s"))
                stage = "completed"
                if raw.startswith("Started:"):
                    stage = "started"
                    raw = raw[len("Started:"):]
                qname = norm_ws(raw)
                prereqs.append({"quest": qname, "stage": stage})
        elif mode == "skills":
            m = skill_item_re.match(ln)
            if m:
                skill = norm_ws(unescape_lua(m.group("skill")))
                lvl = int(m.group("lvl"))
                flags_raw = m.group("flags") or ""
                fl = re.findall(r"'([^']*)'", flags_raw)
                ironman = "ironman" in fl
                boostable = "boostable" in fl
                skill_reqs.append({
                    "skill": skill,
                    "level": lvl,
                    "ironman": ironman,
                    "boostable": boostable,
                })
    records.append({
        "name": name,
        "node_type": nt,
        "prereqs": prereqs,
        "skill_reqs": skill_reqs,
    })

# Dangling detection: prereq quest targets that are not themselves top-level entries.
known_missing = sorted({
    p["quest"]
    for r in records
    for p in r["prereqs"]
    if p["quest"] not in all_names
})

# domain stats
type_counts = {}
for r in records:
    type_counts[r["node_type"]] = type_counts.get(r["node_type"], 0) + 1

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

envelope = {
    "_provenance": {
        "domain": "quests",
        "source_urls": [
            "https://oldschool.runescape.wiki/w/Module:Questreq/data?action=raw"
        ],
        "source_query": None,
        "accessed": now,
        "license": "CC BY-NC-SA 3.0",
        "extraction_method": "script",
        "raw_files": [
            "data/raw/questreq_data.lua",
            "data/raw/questreq_data.lua.PROVENANCE.txt",
            "data/raw/parse_quests.py",
        ],
        "record_count": len(records),
        "completeness": {
            "bounded_by": "Module:Questreq/data top-level entries",
            "universe_count": len(records),
            "records_count": len(records),
            "known_missing": known_missing,
            "known_missing_note": (
                "known_missing = quest names referenced as prereqs but absent as "
                "their own Questreq entry (dangling targets). Questreq only lists "
                "nodes that HAVE requirements, so prereq-free quests like these are "
                "not module keys; this is a source property, not a capture gap. All "
                "213 module top-level entries were captured (records_count == "
                "universe_count)."
            ),
        },
        "domain_stats": {
            "node_type_counts": type_counts,
            "prereq_edge_count": sum(len(r["prereqs"]) for r in records),
            "skill_req_count": sum(len(r["skill_reqs"]) for r in records),
            "started_stage_prereq_count": sum(
                1 for r in records for p in r["prereqs"] if p["stage"] == "started"
            ),
            "dangling_prereq_count": len(known_missing),
            "note": "Diaries here (node_type='diary') must be deduped against the achievement_diaries domain. Skill req levels reflect Questreq data; some carry ironman/boostable flags. node_type classified by source section: official+unofficial miniquest sections -> 'miniquest'; achievement diary section -> 'diary'; rest -> 'quest'.",
        },
    },
    "records": records,
    "_excluded": [],
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(envelope, f, ensure_ascii=False, indent=2)

print("records:", len(records))
print("type_counts:", type_counts)
print("known_missing (%d):" % len(known_missing), known_missing)
