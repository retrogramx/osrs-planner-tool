#!/usr/bin/env python3
"""Parse OSRS Achievement_Diary/All_achievements wikitext into enveloped JSON.

Strategy: the page lists every diary task across several wikitables grouped by
requirement type (by skill, quest-only, combat, no-req, special categories).
The SAME (diary, tier, task) can appear in more than one section (e.g. a task
needing two skills shows in the table of its highest-level skill; "Multiple"/
"Various" placeholder rows in the by-skill tables point to special-category
tables which hold the real per-task rows). We parse every data row, extract
diary + tier + task + requirements, drop placeholder rows (no real diary
anchor), and dedupe by (diary, tier, normalized task), merging requirements.
"""
import re, json, sys
from collections import OrderedDict

SRC = "data/raw/achievement_diaries_all_raw.wikitext"
with open(SRC) as f:
    TXT = f.read()

# ---- helpers ---------------------------------------------------------------
def strip_links(s):
    # [[A|B]] -> B ; [[A]] -> A
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)             # bold/italic
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<[^>]+>", "", s)          # remaining html tags
    s = re.sub(r"\{\{[Cc]oins\|([0-9,]+)\}\}", r"\1 coins", s)
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()

def linked_pages(s):
    """All [[Target|...]] / [[Target]] page targets in a cell."""
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]", s):
        out.append(m.group(1).strip())
    return out

SCP_RE = re.compile(r"\{\{SCP\|([A-Za-z ]+)\|([0-9]+)(?:-([0-9]+))?[^}]*\}\}")
def parse_skills(cell):
    """Return list of {skill, level} from SCP templates in a cell."""
    out = []
    for m in SCP_RE.finditer(cell):
        skill = m.group(1).strip()
        lo = int(m.group(2))
        out.append({"skill": skill, "level": lo})
    return out

DIFF_RE = re.compile(r"\[\[([A-Za-z &'\-]+Diary)#(Easy|Medium|Hard|Elite)\|", re.I)
DIARY_LINK_RE = re.compile(r"\[\[([A-Za-z &'\-]+Diary)\|([^\]]+)\]\]")

def diary_name(raw):
    return re.sub(r"\s*Diary$", "", raw).strip()

# ---- table extraction ------------------------------------------------------
def split_tables(txt):
    """Yield (header_cells, [row_raw_blocks]) for each wikitable."""
    tables = []
    i = 0
    while True:
        start = txt.find("{|", i)
        if start == -1:
            break
        depth = 0
        j = start
        # find matching |}
        while j < len(txt):
            if txt[j:j+2] == "{|":
                depth += 1; j += 2; continue
            if txt[j:j+2] == "|}":
                depth -= 1; j += 2
                if depth == 0:
                    break
                continue
            j += 1
        tables.append(txt[start:j])
        i = j
    return tables

def parse_row_cells(rowblock):
    """Given text between |- markers, return list of cell strings."""
    # cells start with | or ! at line start, can also be || separated
    cells = []
    # remove leading row attributes line
    lines = rowblock.split("\n")
    buf = None
    def flush():
        nonlocal buf
        if buf is not None:
            cells.append(buf)
        buf = None
    for ln in lines:
        if ln.startswith("|-") or ln.startswith("|+") or ln.startswith("{|") or ln.startswith("|}"):
            continue
        if ln.startswith("|") or ln.startswith("!"):
            flush()
            # could be multiple cells via || on one line
            body = ln[1:]
            # handle data-sort-value=... | actual  -> strip cell attr before first |
            parts = re.split(r"\|\|", body)
            for k, p in enumerate(parts):
                if k == 0:
                    buf = p
                else:
                    flush(); buf = p
        else:
            if buf is not None:
                buf += "\n" + ln
    flush()
    # strip cell attributes like data-sort-value=1| or style=...|
    cleaned = []
    for c in cells:
        c = re.sub(r"^\s*(?:data-sort-value=[^|\n]*|style=\"[^\"]*\"|width=\"[^\"]*\"|colspan=\d+|rowspan=\d+)\s*\|(?!\|)", "", c.strip())
        cleaned.append(c.strip())
    return cleaned

records = OrderedDict()  # key -> record
placeholder_rows = 0
all_rows = 0

for tbl in split_tables(TXT):
    if "Diary" not in tbl or "Difficulty" not in tbl:
        continue
    # split into rows by |-
    rowblocks = re.split(r"\n\|-", tbl)
    # first block contains header
    header_block = rowblocks[0]
    header_cells = parse_row_cells("\n" + header_block.split("{|",1)[-1])
    # determine header labels (text after ! )
    headers = [strip_links(h).lower() for h in header_cells]
    for rb in rowblocks[1:]:
        cells = parse_row_cells("\n|-\n" + rb)
        if not cells:
            continue
        rowtxt = "\n".join(cells)
        diff_m = DIFF_RE.search(rowtxt)
        if not diff_m:
            # placeholder "Multiple/Various" rows or non-task rows
            if re.search(r"Various|Multiple", rowtxt):
                placeholder_rows += 1
            continue
        all_rows += 1
        tier = diff_m.group(2).lower()
        # diary: prefer explicit diary link cell
        dm = DIARY_LINK_RE.search(rowtxt)
        if dm:
            diary = diary_name(dm.group(1))
        else:
            diary = diary_name(diff_m.group(1))
        # task = the last cell (Task column is always last)
        task_cell = cells[-1]
        task = strip_links(task_cell)
        if not task:
            continue
        # ---- requirements ----
        skills = []
        quests = []
        items = []
        # map columns by header where possible
        for idx, cell in enumerate(cells):
            hdr = headers[idx] if idx < len(headers) else ""
            sk = parse_skills(cell)
            if sk:
                skills.extend(sk)
            if "quest" in hdr:
                for q in linked_pages(cell):
                    if q and q != "None":
                        quests.append(q)
        # also catch single 'Level' column where header is just the skill section
        # dedupe skills by (skill, level)
        seen = set(); usk = []
        for s in skills:
            k = (s["skill"], s["level"])
            if k not in seen:
                seen.add(k); usk.append(s)
        # quests dedupe
        quests = list(dict.fromkeys(quests))
        key = (diary, tier, re.sub(r"[^a-z0-9]", "", task.lower()))
        if key in records:
            rec = records[key]
            # merge skills/quests
            for s in usk:
                if (s["skill"], s["level"]) not in {(x["skill"], x["level"]) for x in rec["requirements"]["skills"]}:
                    rec["requirements"]["skills"].append(s)
            for q in quests:
                if q not in rec["requirements"]["quests"]:
                    rec["requirements"]["quests"].append(q)
            rec["_seen_in_sections"] += 1
        else:
            records[key] = {
                "diary_region": diary,
                "tier": tier,
                "task": task,
                "requirements": {"skills": usk, "quests": quests, "items": items},
                "reward": None,
                "_seen_in_sections": 1,
            }

recs = list(records.values())
print("raw task-rows (with diff anchor):", all_rows)
print("placeholder Multiple/Various rows skipped:", placeholder_rows)
print("deduped records:", len(recs))
from collections import Counter
print("by diary:", dict(Counter(r["diary_region"] for r in recs)))
print("by tier:", dict(Counter(r["tier"] for r in recs)))
print("records seen in >1 section:", sum(1 for r in recs if r["_seen_in_sections"]>1))

# dump intermediate for inspection
with open("data/raw/diaries_parsed_intermediate.json","w") as f:
    json.dump(recs, f, indent=1)
