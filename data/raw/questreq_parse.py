#!/usr/bin/env python3
# Source: https://oldschool.runescape.wiki/w/Module:Questreq/data (?action=raw)
# License: CC BY-NC-SA 3.0 (Old School RuneScape Wiki)
"""Pure parser for the Module:Questreq/data Lua table.

parse_questreq_lua(lua_text) -> list of record dicts (no I/O, no provenance).
Section markers in the source delimit node_type:
  quests | miniquests (official + unofficial -> 'miniquest') | achievement diaries.
This is the single source of truth for the Lua parse; data/raw/parse_quests.py
(the data/quests.json builder) and data/audit_quest_requirements.py both call it.
"""
import re

ONE_INDENT = r"(?:\t|    )"
TWO_INDENT = r"(?:\t\t|        )"
_ENTRY_RE = re.compile(r"^" + ONE_INDENT + r"\[(?P<q>'(?:[^'\\]|\\.)*')\] = \{")
_QUESTS_RE = re.compile(r"^" + TWO_INDENT + r"\['quests'\] = \{")
_SKILLS_RE = re.compile(r"^" + TWO_INDENT + r"\['skills'\] = \{")
_SUBTABLE_CLOSE_RE = re.compile(r"^" + TWO_INDENT + r"\}\s*,?\s*$")
_STR_ITEM_RE = re.compile(r"^\s*'(?P<s>(?:[^'\\]|\\.)*)'\s*,?\s*$")
_SKILL_ITEM_RE = re.compile(
    r"^\s*\{\s*'(?P<skill>(?:[^'\\]|\\.)*)'\s*,\s*(?P<lvl>\d+)"
    r"(?P<flags>(?:\s*,\s*'[^']*')*)\s*\}\s*,?\s*$"
)


def _unescape_lua(s: str) -> str:
    return s.replace("\\'", "'").replace('\\"', '"')


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _build_sections(lines: list[str]):
    def find(marker: str):
        for i, ln in enumerate(lines):
            if marker in ln:
                return i + 1
        return None
    table_start = find("local questReqs = {")
    mini = find("Insert Miniquests below here")
    diary = find("Insert Achievement Diaries below here")
    _markers = {"local questReqs = {": table_start,
                "Insert Miniquests below here": mini,
                "Insert Achievement Diaries below here": diary}
    missing = [m for m, v in _markers.items() if v is None]
    if missing:
        raise ValueError(f"questreq_parse: missing section marker(s) in Lua source: {missing}")
    return [
        ("quest", table_start, mini - 1),
        ("miniquest", mini, diary - 1),
        ("diary", diary, 10 ** 9),
    ], table_start


def _node_type_for(lineno: int, sections) -> str | None:
    for nt, lo, hi in sections:
        if lo <= lineno <= hi:
            return nt
    return None


def parse_questreq_lua(lua_text: str) -> list[dict]:
    lines = lua_text.splitlines(keepends=True)
    sections, table_start = _build_sections(lines)

    entries = []  # (lineno_1based, name)
    for i, ln in enumerate(lines):
        if i + 1 < table_start:
            continue
        m = _ENTRY_RE.match(ln)
        if m:
            name = _norm_ws(_unescape_lua(m.group("q")[1:-1]))
            entries.append((i + 1, name))

    entry_bounds = []
    for idx, (start, name) in enumerate(entries):
        end = entries[idx + 1][0] - 1 if idx + 1 < len(entries) else len(lines)
        entry_bounds.append((start, end, name))

    records = []
    for start, end, name in entry_bounds:
        block = lines[start - 1:end]
        nt = _node_type_for(start, sections)
        prereqs, skill_reqs, mode = [], [], None
        for ln in block:
            if _QUESTS_RE.match(ln):
                mode = "quests"
                continue
            if _SKILLS_RE.match(ln):
                mode = "skills"
                continue
            if _SUBTABLE_CLOSE_RE.match(ln):
                mode = None
                continue
            if mode == "quests":
                m = _STR_ITEM_RE.match(ln)
                if m:
                    raw = _unescape_lua(m.group("s"))
                    stage = "completed"
                    if raw.startswith("Started:"):
                        # OSRS quest-state vocabulary: the source's "Started:" prefix maps to "in_progress"
                        # (the engine's QUEST_STATE_ORDER vocabulary), NOT a literal "started". This corrected a
                        # base-commit builder/data mismatch: the prior parser emitted "started" while committed
                        # quests.json already used "in_progress" (so the old builder couldn't reproduce its own data).
                        stage = "in_progress"
                        raw = raw[len("Started:"):]
                    prereqs.append({"quest": _norm_ws(raw), "stage": stage})
            elif mode == "skills":
                m = _SKILL_ITEM_RE.match(ln)
                if m:
                    fl = re.findall(r"'([^']*)'", m.group("flags") or "")
                    skill_reqs.append({
                        "skill": _norm_ws(_unescape_lua(m.group("skill"))),
                        "level": int(m.group("lvl")),
                        "ironman": "ironman" in fl,
                        "boostable": "boostable" in fl,
                    })
        records.append({"name": name, "node_type": nt,
                        "prereqs": prereqs, "skill_reqs": skill_reqs})
    return records
