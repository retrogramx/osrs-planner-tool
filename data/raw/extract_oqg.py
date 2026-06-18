#!/usr/bin/env python3
"""Extract optimal quest order (editorial sequence) from OSRS Wiki raw wikitext.
Sources: Optimal_quest_guide (main), /Ironman, /Free-to-play (?action=raw).
Preserves editorial order. Faithful extraction; no fact paraphrasing.
"""
import re, json, datetime

RAW = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/raw/"


def parse_rows(txt, start_line, stop_at_close=True):
    """Parse wikitable rows that carry data-rowid, starting after start_line."""
    lines = txt.split("\n")[start_line:]
    rows = []
    cur = None

    def flush(c):
        if c and c["buf"]:
            c["cells"].append("\n".join(c["buf"]))
            c["buf"] = []

    for l in lines:
        if l.startswith("|- ") and "data-rowid=" in l:
            flush(cur)
            m = re.search(r'data-rowid="([^"\n]+)"', l)
            if not m:
                # unterminated quote in source -> take rest of line after the quote
                m2 = re.search(r'data-rowid="(.+)$', l)
                rowid = m2.group(1).strip() if m2 else l
            else:
                rowid = m.group(1)
            cur = {"rowid": rowid, "cells": [], "buf": []}
            rows.append(cur)
        elif cur is not None:
            if l.startswith("|}"):
                flush(cur)
                if stop_at_close:
                    break
                cur = None
            elif l.startswith("!"):
                # header/colspan banner row inside table -> ignore
                continue
            elif l.startswith("|"):
                flush(cur)
                cur["buf"] = [l[1:]]
            else:
                cur["buf"].append(l)
    flush(cur)
    return rows


WIKILINK_PIPE = re.compile(r"\[\[[^\]|]+\|([^\]]+)\]\]")   # [[target|display]] -> display
WIKILINK = re.compile(r"\[\[([^\]|]+)\]\]")                 # [[target]] -> target
BOLD_ITAL = re.compile(r"'''?")
TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
HTML_TAG = re.compile(r"<[^>]+>")
PLINK = re.compile(r"\{\{plink\|([^|}]+)(?:\|[^}]*)?\}\}", re.I)
SCP = re.compile(r"\{\{SCP\|([^|}]+)(?:\|[^}]*)?\}\}", re.I)


CELL_ATTR = re.compile(r'^\s*(?:data-sort-value|style|class|colspan|rowspan|align|scope)\s*=\s*"[^"]*"\s*\|(?!\|)')


def strip_cell_attr(s):
    """Remove a leading wikitable cell attribute (e.g. data-sort-value="...")|content."""
    return CELL_ATTR.sub("", s, count=1)


def clean(s):
    if s is None:
        return ""
    s = strip_cell_attr(s)
    s = s.strip()
    s = PLINK.sub(r"\1", s)
    s = SCP.sub(r"\1", s)
    # strip remaining simple templates
    prev = None
    while prev != s:
        prev = s
        s = TEMPLATE.sub("", s)
    s = WIKILINK_PIPE.sub(r"\1", s)
    s = WIKILINK.sub(r"\1", s)
    s = BOLD_ITAL.sub("", s)
    s = HTML_TAG.sub(" ", s)
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def classify(name_cell_clean, raw_name_cell, qp_raw):
    """Return row_type and is_quest flag."""
    low = raw_name_cell.lower()
    qp = 0
    mqp = re.search(r"Optimal quest/qp\|(\d+)", qp_raw)
    if mqp:
        qp = int(mqp.group(1))
    if low.startswith("unlock:") or "unlock: [[" in low:
        return "unlock", False, qp
    if "(miniquest)" in low:
        return "miniquest", False, qp
    if low.startswith("partially complete"):
        return "partial_quest_step", False, qp
    if "diary" in low and ("easy" in low or "medium" in low or "hard" in low or "elite" in low):
        return "achievement_diary", False, qp
    if "balloon transport" in low or "balloon" in name_cell_clean.lower() and "unlock" in low:
        return "unlock", False, qp
    if "quiz" in low or "training grounds" in low or "barcrawl" in low:
        return "activity", False, qp
    # real quest: has QP>0 or is a known quest link without the above markers
    return "quest", True, qp


def extract_notable_unlocks(info_cell_clean, info_cell_raw):
    """Pull an unlock note from the Additional-info column if it mentions an unlock/access/allows."""
    if not info_cell_clean:
        return None
    triggers = ("unlock", "allows", "access to", "ability to", "grants")
    low = info_cell_clean.lower()
    if any(t in low for t in triggers):
        # take the first sentence-ish chunk
        return info_cell_clean
    return None


def build_records(txt, start_line, variant):
    rows = parse_rows(txt, start_line)
    records = []
    for idx, r in enumerate(rows):
        cells = r["cells"]
        # The expected layout is 6 cells: name, quickguide, newlevels, qp, info, location.
        # Some rows carry a junk leading cell (row attribute split as an empty cell),
        # giving 7 cells; in that case shift everything right by one.
        offset = 0
        if len(cells) >= 7 and clean(cells[0]) == "":
            offset = 1
        name_raw = cells[offset] if len(cells) > offset else r["rowid"]
        qp_raw = cells[offset + 3] if len(cells) > offset + 3 else ""
        info_raw = cells[offset + 4] if len(cells) > offset + 4 else ""
        name = clean(name_raw)
        if not name:
            name = clean(r["rowid"])
        # strip trailing "(miniquest)" qualifier note from display but keep type
        info = clean(info_raw)
        row_type, is_quest, qp = classify(name, name_raw, qp_raw)
        rec = {
            "order_index": idx + 1,
            "quest": name,
            "account_variant": variant,
            "row_type": row_type,
            "is_quest": is_quest,
            "quest_points": qp,
        }
        nu = extract_notable_unlocks(info, info_raw)
        if nu:
            rec["notable_unlocks"] = nu
        records.append(rec)
    return records


def main():
    main_txt = open(RAW + "optimal_quest_guide_main.wikitext").read()
    iron_txt = open(RAW + "optimal_quest_guide_ironman.wikitext").read()
    f2p_txt = open(RAW + "optimal_quest_guide_f2p.wikitext").read()

    # main: table starts at line 19 (0-indexed); start parsing after line 18
    main_recs = build_records(main_txt, 18, "main")
    # ironman: order table at line 144; parse after 143 (skip first ref table)
    iron_recs = build_records(iron_txt, 143, "ironman")
    # f2p: table at line 31; parse after 30
    f2p_recs = build_records(f2p_txt, 30, "f2p")

    all_recs = main_recs + iron_recs + f2p_recs

    domain_stats = {
        "main_rows": len(main_recs),
        "main_true_quests": sum(1 for r in main_recs if r["is_quest"]),
        "ironman_rows": len(iron_recs),
        "ironman_true_quests": sum(1 for r in iron_recs if r["is_quest"]),
        "f2p_rows": len(f2p_recs),
        "f2p_true_quests": sum(1 for r in f2p_recs if r["is_quest"]),
        "row_type_counts": {},
    }
    from collections import Counter
    domain_stats["row_type_counts"] = dict(Counter(r["row_type"] for r in all_recs))

    envelope = {
        "_provenance": {
            "domain": "optimal_quest_order",
            "source_urls": [
                "https://oldschool.runescape.wiki/w/Optimal_quest_guide?action=raw",
                "https://oldschool.runescape.wiki/w/Optimal_quest_guide/Ironman?action=raw",
                "https://oldschool.runescape.wiki/w/Optimal_quest_guide/Free-to-play?action=raw",
            ],
            "source_query": None,
            "accessed": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": [
                "data/raw/optimal_quest_guide_main.wikitext",
                "data/raw/optimal_quest_guide_ironman.wikitext",
                "data/raw/optimal_quest_guide_f2p.wikitext",
            ],
            "record_count": len(all_recs),
            "completeness": {
                "bounded_by": "OSRS Wiki Optimal quest guide tables (main + Ironman + F2P editorial sequences)",
                "universe_count": len(all_recs),
                "records_count": len(all_recs),
                "known_missing": [
                    "Notable quest unlocks section (transcluded template {{Optimal quest guide/Recommended Quests}}; not in raw wikitext of these pages)",
                    "Per-quest skill/XP requirements columns omitted by domain spec (record schema is order_index/quest/account_variant/notable_unlocks)",
                    "Free-to-play/Ironman combined sub-guide (Optimal quest guide/Free-to-play/Ironman) not requested",
                ],
            },
            "domain_stats": domain_stats,
        },
        "records": all_recs,
        "_excluded": [],
    }

    out = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/optimal_quest_order.json"
    with open(out, "w") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)
    print("WROTE", out)
    print("record_count:", len(all_recs))
    print("domain_stats:", json.dumps(domain_stats, indent=2))


if __name__ == "__main__":
    main()
