#!/usr/bin/env python3
"""Quest-requirement correctness audit (foundation-audit roadmap, Quests brick).

Diffs the committed data/quests.json against a fresh parse of Module:Questreq/data.
  - default (offline): re-parse the committed data/raw/questreq_data.lua. This is a
    REPRODUCIBILITY regression (catches hand-edits / parser drift).
  - --refresh: fetch the LIVE Module:Questreq/data?action=raw and diff against it.
    This is the living-game DRIFT check (the spec's "diff vs canonical"). Network only.

Usage:  ./venv/bin/python data/audit_quest_requirements.py [--refresh]
Exit 0 if no differences, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
sys.path.insert(0, RAW_DIR)
from questreq_parse import parse_questreq_lua  # noqa: E402

QUESTS_PATH = os.path.join(ROOT, "data", "quests.json")
RAW_LUA = os.path.join(RAW_DIR, "questreq_data.lua")
LIVE_URL = "https://oldschool.runescape.wiki/w/Module:Questreq/data?action=raw"
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"

# Compare only requirement-bearing nodes; diaries are deduped into their own domain.
_AUDIT_TYPES = ("quest", "miniquest")


def _key_prereqs(rec: dict):
    return sorted((p["quest"], p.get("stage") or "completed") for p in rec["prereqs"])


def _key_skills(rec: dict):
    return sorted((s["skill"], s["level"], bool(s.get("ironman")), bool(s.get("boostable")))
                  for s in rec["skill_reqs"])


def diff_records(committed: list[dict], reparsed: list[dict]) -> dict:
    """Diff two record lists by name. Returns missing_in_committed / extra_in_committed /
    changed (prereqs or skill_reqs differ)."""
    c = {r["name"]: r for r in committed if r["node_type"] in _AUDIT_TYPES}
    s = {r["name"]: r for r in reparsed if r["node_type"] in _AUDIT_TYPES}
    missing = sorted(set(s) - set(c))   # in source, not in committed
    extra = sorted(set(c) - set(s))     # in committed, not in source
    changed = []
    for name in sorted(set(c) & set(s)):
        cp, sp = _key_prereqs(c[name]), _key_prereqs(s[name])
        cs, ss = _key_skills(c[name]), _key_skills(s[name])
        if cp != sp or cs != ss:
            changed.append({"name": name, "prereqs_committed": cp, "prereqs_reparsed": sp,
                            "skills_committed": cs, "skills_reparsed": ss})
    return {"missing_in_committed": missing, "extra_in_committed": extra, "changed": changed}


def _committed_records() -> list[dict]:
    with open(QUESTS_PATH, encoding="utf-8") as f:
        return json.load(f)["records"]


def audit_offline() -> dict:
    with open(RAW_LUA, encoding="utf-8") as f:
        return diff_records(_committed_records(), parse_questreq_lua(f.read()))


def audit_refresh() -> dict:
    req = urllib.request.Request(LIVE_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        live = r.read().decode("utf-8")
    return diff_records(_committed_records(), parse_questreq_lua(live))


def _print_report(report: dict, mode: str) -> int:
    n = len(report["missing_in_committed"]) + len(report["extra_in_committed"]) + len(report["changed"])
    if n == 0:
        print(f"QUEST-REQUIREMENT AUDIT PASSED ({mode}) — committed quests match the source.")
        return 0
    print(f"QUEST-REQUIREMENT AUDIT: {n} difference(s) ({mode}):")
    for name in report["missing_in_committed"]:
        print(f"  - missing from committed (in source): {name}")
    for name in report["extra_in_committed"]:
        print(f"  - extra in committed (not in source): {name}")
    for c in report["changed"]:
        print(f"  - changed: {c['name']}")
        if c["prereqs_committed"] != c["prereqs_reparsed"]:
            print(f"      prereqs committed={c['prereqs_committed']} source={c['prereqs_reparsed']}")
        if c["skills_committed"] != c["skills_reparsed"]:
            print(f"      skills  committed={c['skills_committed']} source={c['skills_reparsed']}")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="fetch live Module:Questreq/data and diff (network); default re-parses committed raw")
    args = ap.parse_args(argv)
    if args.refresh:
        return _print_report(audit_refresh(), "refresh/live")
    return _print_report(audit_offline(), "offline/committed-raw")


if __name__ == "__main__":
    sys.exit(main())
