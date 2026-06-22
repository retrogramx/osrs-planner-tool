# Quest Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the committed quest *requirements* against the canonical wiki source, and build the *reward/value* layer the KG is missing — establishing a domain-agnostic reward/edge taxonomy (`grants` · `effect` · `progress_towards` + completion-goal nodes) proven end-to-end against an owner-verified seed of quests spanning every reward shape.

**Architecture:** The engine already defines most node-kinds and the `requires`/`grants` edge types but the committed data uses only `requires`. We (1) add a correctness-audit tool that re-parses `Module:Questreq/data` and diffs it against `data/quests.json`; (2) make the minimal schema additions (`Edge.data`, `EdgeType.EFFECT`, `EdgeType.PROGRESS_TOWARDS`, `NodeKind.GOAL`); (3) extend the deterministic id re-keyer so a node can own more than one edge; (4) add a `quest_rewards` builder that turns a committed `data/quest_rewards.json` overlay into `grants`/`effect`/`progress_towards` edges; (5) add a `completion_goals` builder for `goal:quest-point-cape` (the Quest cape = the QP cape, one node) with a threshold-gated grant; (6) gate everything with a committed structural validator and an owner-verified seed.

**Tech Stack:** Python 3 (stdlib only — `urllib`, `json`, `re`, `dataclasses`, `enum`); `networkx` (already a dependency); `pytest`. No new dependencies.

## Global Constraints

- **Source-grounded, never fabricated.** Every reward datum is transcribed from the *current* wiki reward pages (§7 of the spec) with provenance. Model memory proposes structure; sources dispose of specifics. A reward that cannot be sourced is left out and disclosed — never invented. This includes test values: golden assertions pin *machinery* (edge shape, validator behaviour) using clearly-synthetic fixtures; real reward numbers live only in committed data, owner-verified.
- **Owner is a required reviewer.** A structural validator cannot check whether an edge is *editorially* true. The seed (`data/quest_rewards.json`, `data/completion_goals.json`) must be reviewed by the owner (the live player) before it is considered correct.
- **Reference, don't duplicate.** Item stats / value / `tradeable` come from `data/items_equipment.json`; transport from `data/unlocks_transport.json`. The reward overlay stays thin (it references these by id, never re-derives them).
- **The Quest cape IS the QP cape — ONE node** (`goal:quest-point-cape`). Never two.
- **Deterministic, byte-stable build.** `python -m kg_ingest.assemble` must produce byte-identical `kg/*.json` on repeated runs. Output is sorted by id and serialized with `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False)` + trailing newline (existing `_write_json`). Builders mint *builder-local* ids in disjoint bands; `assemble.rekey()` derives global ids from the owning node id. Existing bands: quests `0x10000000`/`0x20000000` (`kg_ingest/ids.py`), goals `0x30000000`/`0x40000000` (`builders/goals.py`). New bands: **quest_rewards `0x50000000`/`0x60000000`**, **completion_goals `0x70000000`/`0x78000000`**.
- **Node id prefixes are locked** (`kg_ingest/ids.py`): `quest:<slug>`, `skill:<slug>`, `item:<item_id>`, `access:<slug>`, and new `goal:<slug>`. Always mint via the `ids.py` helpers + `slugify`.
- **Validators follow the committed idiom** (`data/validate_*.py`): a pure `check_*(...) -> list[str]` returning violation strings (`[]` == valid) + a `main() -> int` that prints `... VALIDATION PASSED/FAILED` and returns/exits 0 or 1. Tests import the script via `importlib.util` (see `tests/kg_ingest/test_validate_kg.py`).
- **Tests:** `pytest` from the project venv (`pyproject.toml`: `pythonpath=["."]`, `testpaths=["tests"]`). New tests live under `tests/<domain>/test_*.py`. Build `InMemoryKGStore(nodes, edges, groups)` directly in tests (frozen dataclasses — never mutate; construct fresh).
- **The engine only *gates* on `requires`** (and flips `grants` for cycle detection). `effect` and `progress_towards` edges are inert to gating in this brick — they are the substrate a later route/UI layer reads. Do not wire them into prereq evaluation.

---

## File Structure

**Correctness audit (Task 1):**
- Create `data/raw/questreq_parse.py` — pure `parse_questreq_lua(lua_text) -> list[dict]` (extracted from `parse_quests.py`; single source of truth for the Lua parse).
- Modify `data/raw/parse_quests.py` — delegate parsing to `questreq_parse.parse_questreq_lua` (DRY; keeps envelope + provenance + file I/O).
- Create `data/audit_quest_requirements.py` — re-parse + diff vs committed `data/quests.json`; `--refresh` fetches live; structured report; exit code.
- Create `tests/data/__init__.py`, `tests/data/test_audit_quest_requirements.py`.

**Schema (Task 2):**
- Modify `src/osrs_planner/engine/kg/model.py` — `EdgeType.EFFECT`, `EdgeType.PROGRESS_TOWARDS`, `NodeKind.GOAL`, `Edge.data: dict`.
- Modify `src/osrs_planner/engine/kg/json_store.py` — `edge_to_dict`/`edge_from_dict` carry `data`.
- Create `tests/engine/test_reward_edge_types.py`.
- Regenerate `kg/edges.json` (every edge gains `"data": {}`).

**Re-keyer (Task 3):**
- Modify `kg_ingest/assemble.py` — per-owner-cumulative group-id allocation in `rekey()` (byte-stable for single-edge owners).
- Create `tests/kg_ingest/test_rekey_multi_edge.py`.

**Reward builder (Tasks 4–5):**
- Create `kg_ingest/builders/quest_rewards.py` — `build_quest_rewards(reward_records) -> (nodes, edges, groups)`.
- Create `kg_ingest/builders/completion_goals.py` — `build_completion_goals(goal_records) -> (nodes, edges, groups)`.
- Create `data/quest_rewards.json`, `data/completion_goals.json` (seed; expanded in Task 8).
- Modify `kg_ingest/assemble.py` — load + wire both builders.
- Create `tests/kg_ingest/test_build_quest_rewards.py`, `tests/kg_ingest/test_build_completion_goals.py`.

**Validators + integration (Tasks 6–7):**
- Create `data/validate_quest_rewards.py`, `tests/kg_ingest/test_validate_quest_rewards.py`.
- Modify `data/validate_kg.py` (reward-aware invariants), `tests/kg_ingest/test_validate_kg.py`.

**Sourcing + docs (Task 8):**
- Expand `data/quest_rewards.json` / `data/completion_goals.json` to the owner-verified seed; fetch reward-page raws into `data/raw/`.
- Create `data/QUEST_REWARDS.md` (format + cross-domain reuse note + disclosed limitations).

---

## Task 1: Quest-requirement correctness audit

**Files:**
- Create: `data/raw/questreq_parse.py`
- Modify: `data/raw/parse_quests.py`
- Create: `data/audit_quest_requirements.py`
- Create: `tests/data/__init__.py`
- Test: `tests/data/test_audit_quest_requirements.py`

**Interfaces:**
- Produces: `questreq_parse.parse_questreq_lua(lua_text: str) -> list[dict]` — returns records `[{"name", "node_type", "prereqs":[{"quest","stage"}], "skill_reqs":[{"skill","level","ironman","boostable"}]}]` (same shape as `data/quests.json` records). Produces `audit_quest_requirements.diff_records(committed: list[dict], reparsed: list[dict]) -> dict` with keys `missing_in_committed`, `extra_in_committed`, `changed` (list of `{"name","prereqs_committed","prereqs_reparsed","skills_committed","skills_reparsed"}`).

- [ ] **Step 1: Extract the parser into `data/raw/questreq_parse.py`**

Move the parsing logic out of the script into a pure function. Create `data/raw/questreq_parse.py`:

```python
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
                        stage = "started"
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
```

- [ ] **Step 2: Refactor `data/raw/parse_quests.py` to delegate to the new parser**

Replace the inline parse body (lines 47–148 in the current file) with a call to `parse_questreq_lua`. Keep the envelope/provenance/I/O. The script body becomes:

```python
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
            "started_stage_prereq_count": sum(
                1 for r in records for p in r["prereqs"] if p["stage"] == "started"),
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
```

- [ ] **Step 3: Verify the refactor reproduces `data/quests.json` byte-for-byte**

Run: `./venv/bin/python data/raw/parse_quests.py && git diff --stat data/quests.json`
Expected: `records: 213 ...` printed, and **no diff** in `data/quests.json` (the refactor is behaviour-preserving). If `data/quests.json` changes, the extraction was not faithful — fix `questreq_parse.py` before continuing.

- [ ] **Step 4: Write the failing test for the diff tool**

Create `tests/data/__init__.py` (empty) and `tests/data/test_audit_quest_requirements.py`:

```python
"""Tests for data/audit_quest_requirements.py — the quest-requirement correctness audit."""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "audit_quest_requirements.py")
_spec = importlib.util.spec_from_file_location("audit_quest_requirements", _PATH)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def _rec(name, prereqs=(), skills=()):
    return {"name": name, "node_type": "quest",
            "prereqs": [{"quest": q, "stage": s} for q, s in prereqs],
            "skill_reqs": [{"skill": sk, "level": lv, "ironman": ir, "boostable": bo}
                           for sk, lv, ir, bo in skills]}


def test_identical_records_have_no_diff():
    a = [_rec("Cook's Assistant", skills=[("Cooking", 10, False, False)])]
    report = audit.diff_records(a, [dict(r) for r in a])
    assert report["missing_in_committed"] == []
    assert report["extra_in_committed"] == []
    assert report["changed"] == []


def test_changed_skill_level_is_flagged():
    committed = [_rec("Druidic Ritual", skills=[("Herblore", 3, False, False)])]
    reparsed = [_rec("Druidic Ritual", skills=[("Herblore", 31, False, False)])]
    report = audit.diff_records(committed, reparsed)
    assert [c["name"] for c in report["changed"]] == ["Druidic Ritual"]
    assert report["missing_in_committed"] == [] and report["extra_in_committed"] == []


def test_missing_and_extra_quests_are_flagged():
    committed = [_rec("A"), _rec("B")]
    reparsed = [_rec("A"), _rec("C")]
    report = audit.diff_records(committed, reparsed)
    assert report["missing_in_committed"] == ["C"]   # in source, absent from committed
    assert report["extra_in_committed"] == ["B"]     # in committed, absent from source


def test_committed_data_reproduces_from_raw():
    # The offline regression: committed data/quests.json == re-parse of committed raw.
    report = audit.audit_offline()
    assert report["missing_in_committed"] == [], report["missing_in_committed"]
    assert report["extra_in_committed"] == [], report["extra_in_committed"]
    assert report["changed"] == [], [c["name"] for c in report["changed"]]
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/data/test_audit_quest_requirements.py -v`
Expected: collection/exec error (module `audit_quest_requirements` not found).

- [ ] **Step 6: Implement `data/audit_quest_requirements.py`**

```python
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
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/data/test_audit_quest_requirements.py -v`
Expected: 4 passed (incl. `test_committed_data_reproduces_from_raw`).

- [ ] **Step 8: Run the tool both ways and record the error rate**

Run: `./venv/bin/python data/audit_quest_requirements.py`
Expected: `QUEST-REQUIREMENT AUDIT PASSED (offline/committed-raw) ...` (exit 0).
Then run: `./venv/bin/python data/audit_quest_requirements.py --refresh`
Expected (if network available): a PASS, or a list of living-game drifts. **Record the result** (the count + any drift) in the commit message — this is the measured error rate the foundation-audit roadmap asks for. If the network is unavailable, note that the live-drift check is ready but unrun; the offline regression stands.

- [ ] **Step 9: Commit**

```bash
git add data/raw/questreq_parse.py data/raw/parse_quests.py data/audit_quest_requirements.py tests/data/
git commit -m "quest-foundation: requirement correctness audit (re-parse + diff vs Questreq)"
```

---

## Task 2: Schema additions — `Edge.data` + new edge/node types

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py`
- Modify: `src/osrs_planner/engine/kg/json_store.py`
- Test: `tests/engine/test_reward_edge_types.py`
- Regenerate: `kg/edges.json` (via `python -m kg_ingest.assemble`)

**Interfaces:**
- Produces: `EdgeType.EFFECT = "effect"`, `EdgeType.PROGRESS_TOWARDS = "progress_towards"`, `NodeKind.GOAL = "goal"`. `Edge` gains a final field `data: dict = field(default_factory=dict)`. `edge_to_dict(e)` returns `{"id","type","src","dst","cond_group","data"}`; `edge_from_dict(d)` reads `data=d.get("data") or {}`.

- [ ] **Step 1: Write the failing test**

Create `tests/engine/test_reward_edge_types.py`:

```python
"""Schema round-trip + inertness for the reward edge/node types (quest-foundation Task 2)."""
from osrs_planner.engine.kg.model import (
    Edge, EdgeType, Node, NodeKind, ConditionGroup, ConditionAtom, AtomType, Op,
)
from osrs_planner.engine.kg.json_store import edge_to_dict, edge_from_dict, node_from_dict
from osrs_planner.engine.kg.store import InMemoryKGStore


def test_new_enum_values_exist():
    assert EdgeType.EFFECT.value == "effect"
    assert EdgeType.PROGRESS_TOWARDS.value == "progress_towards"
    assert NodeKind.GOAL.value == "goal"


def test_edge_data_round_trips():
    e = Edge(id=1, type=EdgeType.GRANTS, src="quest:x", dst="skill:attack",
             cond_group=None, data={"reward": "xp", "form": "fixed", "amount": 13750})
    d = edge_to_dict(e)
    assert d["data"] == {"reward": "xp", "form": "fixed", "amount": 13750}
    assert edge_from_dict(d) == e


def test_edge_without_data_key_decodes_to_empty_dict():
    # Pre-Task-2 committed edges have no "data" key; they must load as data={}.
    legacy = {"id": 9, "type": "requires", "src": "quest:b", "dst": None, "cond_group": None}
    assert edge_from_dict(legacy).data == {}


def test_goal_node_round_trips():
    d = {"id": "goal:quest-point-cape", "kind": "goal", "name": "Quest point cape",
         "slug": "quest-point-cape", "data": {"counter_type": "points", "thresholds": [33]}}
    n = node_from_dict(d)
    assert n.kind is NodeKind.GOAL and n.data["thresholds"] == [33]


def test_progress_towards_edges_are_inert_to_cycle_detection():
    # A goal node + a progress_towards edge from a quest must not break find_cycles().
    nodes = [Node(id="quest:x", kind=NodeKind.QUEST, name="X", slug="x"),
             Node(id="goal:quest-point-cape", kind=NodeKind.GOAL, name="QP cape",
                  slug="quest-point-cape", data={"counter_type": "points", "thresholds": [2]})]
    edges = [Edge(id=1, type=EdgeType.PROGRESS_TOWARDS, src="quest:x",
                  dst="goal:quest-point-cape", cond_group=None, data={"weight": 1})]
    store = InMemoryKGStore(nodes, edges, {})
    assert store.find_cycles() == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_reward_edge_types.py -v`
Expected: FAIL — `AttributeError: EFFECT` (enum members absent) and `Edge.__init__` rejecting `data`.

- [ ] **Step 3: Add the enum members and `Edge.data`**

In `src/osrs_planner/engine/kg/model.py`, add to `NodeKind` (after `CLOG_SLOT`):

```python
    CLOG_SLOT = "clog_slot"
    GOAL = "goal"  # completion-goal aggregate node (Quest cape, music cape, ...): data={counter_type, thresholds}
```

Add to `EdgeType` (after `GATED_BY`):

```python
    GATED_BY = "gated_by"
    EFFECT = "effect"                  # a passive/permanent perk riding on a granted item/unlock (spec §4)
    PROGRESS_TOWARDS = "progress_towards"  # counting contribution toward a goal node; data={weight} (spec §5)
```

Add a trailing field to the `Edge` dataclass (after `cond_group`):

```python
    id: int
    type: EdgeType
    src: str
    dst: Optional[str] = None
    cond_group: Optional[int] = None
    data: dict = field(default_factory=dict)
```

(`field` is already imported on line 10.)

- [ ] **Step 4: Carry `data` through edge serialization**

In `src/osrs_planner/engine/kg/json_store.py`, change `edge_to_dict`:

```python
def edge_to_dict(edge: Edge) -> dict:
    return {"id": edge.id, "type": edge.type.value, "src": edge.src,
            "dst": edge.dst, "cond_group": edge.cond_group, "data": edge.data}
```

and `edge_from_dict`:

```python
def edge_from_dict(d: dict) -> Edge:
    return Edge(id=d["id"], type=EdgeType(d["type"]), src=d["src"],
                dst=d.get("dst"), cond_group=d.get("cond_group"), data=d.get("data") or {})
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./venv/bin/python -m pytest tests/engine/test_reward_edge_types.py -v`
Expected: 5 passed.

- [ ] **Step 6: Regenerate the KG so `edges.json` carries `data`**

Run: `./venv/bin/python -m kg_ingest.assemble`
Then run: `git diff --stat kg/` — expected: only `kg/edges.json` changes (every edge gains `"data": {}`); `nodes.json`/`condition_groups.json` unchanged.
Then run: `./venv/bin/python data/validate_kg.py`
Expected: `KG VALIDATION PASSED ...` (exit 0).

- [ ] **Step 7: Run the full suite to catch any edge-shape assertions**

Run: `./venv/bin/python -m pytest -q`
Expected: all pass. If a test asserted an exact edge dict without `data`, update it to include `"data": {}` (the new canonical shape).

- [ ] **Step 8: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py src/osrs_planner/engine/kg/json_store.py tests/engine/test_reward_edge_types.py kg/edges.json
git commit -m "quest-foundation: schema — Edge.data + effect/progress_towards/goal types"
```

---

## Task 3: Extend `rekey()` for multiple edges per owner

**Files:**
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_rekey_multi_edge.py`

**Interfaces:**
- Consumes: `Edge`, `ConditionGroup`, `ConditionAtom` from Task 2 (`Edge.data`).
- Produces: `rekey(nodes, edges, groups)` (signature unchanged) now allocates group ids per-owner-*cumulatively* (a stable counter per owning node across all its edges' condition trees), so an owner with two cond_group-bearing edges gets two distinct group roots instead of colliding. Edge ids are already per-owner-cumulative within a single `rekey` call. **Byte-stable** for every owner that has exactly one edge (today's entire KG).

- [ ] **Step 1: Write the failing test**

Create `tests/kg_ingest/test_rekey_multi_edge.py`:

```python
"""rekey() must support >1 edge per owning node without id collisions (quest-foundation Task 3)."""
from kg_ingest.assemble import rekey, stable_edge_id, stable_group_id
from osrs_planner.engine.kg.model import (
    Edge, EdgeType, Node, NodeKind, ConditionGroup, ConditionAtom, AtomType, Op,
)


def _atom_group(gid, atom):
    return ConditionGroup(id=gid, op=Op.AND, parent=None, children=[atom])


def test_single_edge_owner_is_byte_stable():
    # The existing scheme: one requires edge per owner -> ids unchanged.
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b")]
    g = {0x10000000: _atom_group(0x10000000,
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:a", data={"state": "completed"}))}
    e = [Edge(id=0x20000000, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=0x10000000)]
    _, new_edges, new_groups = rekey(nodes, e, g)
    assert new_edges[0].id == stable_edge_id("quest:b", 0)
    assert new_edges[0].cond_group == stable_group_id("quest:b", 0)
    assert set(new_groups) == {stable_group_id("quest:b", 0)}


def test_two_cond_group_edges_from_one_owner_do_not_collide():
    nodes = [Node(id="quest:x", kind=NodeKind.QUEST, name="X", slug="x")]
    g = {
        0x10000000: _atom_group(0x10000000,
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=60)),
        0x10000001: _atom_group(0x10000001,
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:ranged", threshold=50)),
    }
    e = [
        Edge(id=0x20000000, type=EdgeType.REQUIRES, src="quest:x", dst=None, cond_group=0x10000000),
        Edge(id=0x20000001, type=EdgeType.GRANTS, src="quest:x", dst="item:99",
             cond_group=0x10000001, data={"reward": "items", "qty": 1, "tradeable": False}),
    ]
    _, new_edges, new_groups = rekey(nodes, e, g)
    assert len({ne.id for ne in new_edges}) == 2          # distinct edge ids
    assert len({ne.cond_group for ne in new_edges}) == 2  # distinct group roots
    assert len(new_groups) == 2                            # no group dropped/collided
    assert new_edges[0].cond_group == stable_group_id("quest:x", 0)
    assert new_edges[1].cond_group == stable_group_id("quest:x", 1)
    # edge.data survives rekey
    assert new_edges[1].data == {"reward": "items", "qty": 1, "tradeable": False}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_rekey_multi_edge.py -v`
Expected: `test_two_cond_group_edges_from_one_owner_do_not_collide` FAILS — `rekey` raises `ValueError: group id collision at ...` (both edges' roots map to `stable_group_id("quest:x", 0)`).

- [ ] **Step 3: Make group-id allocation per-owner-cumulative**

In `kg_ingest/assemble.py` `rekey()`, the group ids must be indexed by a per-owner counter that advances as *new* local groups are discovered across *all* of an owner's edges (not reset per edge), and `Edge` reconstruction must carry `data`. Replace the body of the edge loop (the `for e in edges:` block, current lines 86–106) with:

```python
    group_local_index: dict[str, int] = {}  # per-owner cumulative group counter
    for e in edges:
        owner = e.src
        e_idx = edge_local_index.get(owner, 0)
        edge_local_index[owner] = e_idx + 1
        new_cond_group = None
        if e.cond_group is not None:
            for local_gid in _walk_group_ids(e.cond_group, groups):
                if local_gid not in local_to_new_group:
                    gi = group_local_index.get(owner, 0)
                    group_local_index[owner] = gi + 1
                    local_to_new_group[local_gid] = stable_group_id(owner, gi)
            new_cond_group = local_to_new_group[e.cond_group]
        new_edge_id = stable_edge_id(owner, e_idx)
        if new_edge_id in seen_edge_ids:
            prior = seen_edge_ids[new_edge_id]
            raise ValueError(
                f"edge id collision at {new_edge_id}: {prior.src}->{prior.dst} and "
                f"{e.src}->{e.dst} hash to the same global id (unrecoverable; not "
                f"silently droppable)")
        new_edge = Edge(id=new_edge_id, type=e.type, src=e.src, dst=e.dst,
                        cond_group=new_cond_group, data=e.data)
        seen_edge_ids[new_edge_id] = new_edge
        new_edges.append(new_edge)
```

> Why byte-stable: for an owner with one cond_group edge, `_walk_group_ids` yields the root then sub-groups in the same pre-order as before, so the cumulative counter assigns `0,1,2…` identically to the old `enumerate(...)`. Only *additional* edges from the same owner consume higher indices — new ids that did not exist before.

- [ ] **Step 4: Run the test to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_rekey_multi_edge.py -v`
Expected: 2 passed.

- [ ] **Step 5: Confirm the committed KG is unchanged (byte-stability)**

Run: `./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/`
Expected: **no diff** (every current owner has exactly one edge, so all ids are identical).
Then run: `./venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add kg_ingest/assemble.py tests/kg_ingest/test_rekey_multi_edge.py
git commit -m "quest-foundation: rekey supports >1 edge per owner (byte-stable)"
```

---

## Task 4: Quest-reward builder — `grants` + `effect` edges

**Files:**
- Create: `kg_ingest/builders/quest_rewards.py`
- Create: `data/quest_rewards.json` (minimal seed: ~3 source-grounded quests covering fixed-XP, items, unlock, and one effect)
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_build_quest_rewards.py`

**Interfaces:**
- Consumes: `quest_id`, `skill_id`, `item_id`, `access_id`, `slugify` (`kg_ingest/ids.py`); `Edge.data` (Task 2); the rekey from Task 3.
- Produces: `build_quest_rewards(reward_records: list[dict]) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]`. Returns **no nodes** (it references existing `skill:`/`item:`/`access:` leaves and, in Task 5, `goal:` nodes). Edge mapping:
  - `{"reward_type":"xp","form":"fixed","skill":S,"amount":N}` → `Edge(GRANTS, src=quest:<q>, dst=skill:<S>, data={"reward":"xp","form":"fixed","amount":N})`
  - `{"reward_type":"xp","form":"choice_lamp","amount":N,"count":C,"eligible_skills":[...],"min_level":L}` → `Edge(GRANTS, src=quest:<q>, dst=None, data={"reward":"xp","form":"choice_lamp", ...})`
  - `{"reward_type":"items","item_id":I,"qty":Q,"tradeable":T,...}` → `Edge(GRANTS, src=quest:<q>, dst=item:<I>, data={"reward":"items","qty":Q,"tradeable":T,...})`. If `condition` present, the grant carries a cond_group (Task 5 handles the cond_group construction; in Task 4, unconditional items only).
  - `{"reward_type":"unlock","category":C,"stage":ST,"access":A?}` → `Edge(GRANTS, src=quest:<q>, dst=access:<A> if A else None, data={"reward":"unlock","category":C,"stage":ST,...})`
  - `{"reward_type":"cosmetic","kind":K,"name":NM}` → `Edge(GRANTS, src=quest:<q>, dst=None, data={"reward":"cosmetic","kind":K,"name":NM})`
  - `effects[]` entry `{"rides_on_item_id":I,"effect_kind":EK,...}` → `Edge(EFFECT, src=item:<I>, dst=None, data={...effect fields...})`
  - (`quest_points` and `progress_towards` are added in Task 5.)

- [ ] **Step 1: Write the failing test**

Create `tests/kg_ingest/test_build_quest_rewards.py`:

```python
"""Tests for kg_ingest/builders/quest_rewards.py (quest-foundation Task 4/5)."""
from kg_ingest.builders.quest_rewards import build_quest_rewards
from osrs_planner.engine.kg.model import EdgeType


def _edges_by_type(edges, t):
    return [e for e in edges if e.type is t]


def test_fixed_xp_becomes_a_grants_edge_to_the_skill():
    rec = {"quest": "Waterfall Quest", "rewards": [
        {"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750}]}
    nodes, edges, groups = build_quest_rewards([rec])
    assert nodes == []
    g = _edges_by_type(edges, EdgeType.GRANTS)
    assert len(g) == 1
    assert g[0].src == "quest:waterfall-quest" and g[0].dst == "skill:attack"
    assert g[0].data == {"reward": "xp", "form": "fixed", "amount": 13750}


def test_item_reward_becomes_a_grants_edge_to_the_item_node():
    rec = {"quest": "Recipe for Disaster", "rewards": [
        {"reward_type": "items", "item": "Barrows gloves", "item_id": 7462,
         "qty": 1, "tradeable": False}]}
    _, edges, _ = build_quest_rewards([rec])
    g = _edges_by_type(edges, EdgeType.GRANTS)[0]
    assert g.dst == "item:7462"
    assert g.data == {"reward": "items", "qty": 1, "tradeable": False}


def test_choice_lamp_has_no_dst_and_carries_eligibility():
    rec = {"quest": "Fairytale I - Growing Pains", "rewards": [
        {"reward_type": "xp", "form": "choice_lamp", "amount": 1000, "count": 1,
         "eligible_skills": ["Attack", "Strength"], "min_level": 30}]}
    _, edges, _ = build_quest_rewards([rec])
    g = _edges_by_type(edges, EdgeType.GRANTS)[0]
    assert g.dst is None and g.data["eligible_skills"] == ["Attack", "Strength"]


def test_effect_becomes_an_effect_edge_owned_by_the_item():
    rec = {"quest": "Fairytale I - Growing Pains", "rewards": [], "effects": [
        {"rides_on_item": "Magic secateurs", "rides_on_item_id": 7409,
         "effect_kind": "rate_multiplier", "magnitude": 0.10,
         "target": "Farming herb yield", "condition": "while-wielded",
         "tier_source": "Fairytale I - Growing Pains"}]}
    _, edges, _ = build_quest_rewards([rec])
    ef = _edges_by_type(edges, EdgeType.EFFECT)
    assert len(ef) == 1 and ef[0].src == "item:7409" and ef[0].dst is None
    assert ef[0].data["effect_kind"] == "rate_multiplier" and ef[0].data["magnitude"] == 0.10


def test_unlock_with_access_targets_the_access_node():
    rec = {"quest": "Fairytale II - Cure a Queen", "rewards": [
        {"reward_type": "unlock", "category": "transportation",
         "name": "Fairy rings", "stage": "in_progress", "access": "Fairy rings"}]}
    _, edges, _ = build_quest_rewards([rec])
    g = [e for e in edges if e.type is EdgeType.GRANTS][0]
    assert g.dst == "access:fairy-rings" and g.data["stage"] == "in_progress"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_build_quest_rewards.py -v`
Expected: import error (module `quest_rewards` does not exist).

- [ ] **Step 3: Implement `kg_ingest/builders/quest_rewards.py`**

```python
"""Quest-reward builder (spec §3,§4,§5; quest-foundation Tasks 4-5).

build_quest_rewards(reward_records) -> (nodes, edges, groups)
Turns the data/quest_rewards.json reward overlay into reward edges. Emits NO nodes
(it references existing skill:/item:/access: leaves + the goal: node from
build_completion_goals). Edge mapping per the spec reward taxonomy:
  xp(fixed)       -> GRANTS quest -> skill:<skill>      data{reward:xp,form:fixed,amount}
  xp(choice_lamp) -> GRANTS quest -> None              data{reward:xp,form:choice_lamp,...}
  items           -> GRANTS quest -> item:<id>          data{reward:items,qty,tradeable,...}
  unlock          -> GRANTS quest -> access:<slug>|None data{reward:unlock,category,stage,...}
  cosmetic        -> GRANTS quest -> None               data{reward:cosmetic,kind,name}
  quest_points(N) -> PROGRESS_TOWARDS quest -> goal:quest-point-cape data{weight:N}  (Task 5)
  effects[]       -> EFFECT item:<id> -> None           data{effect_kind,magnitude,...}

IDs (K9): builder-local group/edge ids use bands 0x50000000/0x60000000 (disjoint
from quests 0x10/0x20 and goals 0x30/0x40). assemble.rekey() re-keys to global ids.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, access_id, item_id, quest_id, skill_id

_GROUP_BAND = 0x50000000
_EDGE_BAND = 0x60000000
_QP_CAPE_GOAL = "goal:quest-point-cape"

_UNLOCK_CATEGORIES = frozenset({
    "skill", "equipment", "skilling-method", "magic", "spellbook", "prayer",
    "location", "area", "transportation", "guild", "shortcut", "monster",
    "slayer", "minigame", "shop", "respawn-point", "area-effect",
})
_REWARD_STAGES = frozenset({"started", "in_progress", "completed"})


def _eid(owner: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{owner}#reward-edge#{slot}")


def _gid(owner: str, slot: int) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner}#reward-group#{slot}")


def build_quest_rewards(
    reward_records: list[dict],
) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    for rec in reward_records:
        qid = quest_id(rec["quest"])
        slot = 0  # per-owner edge slot; rekey re-derives global ids anyway

        for rw in rec.get("rewards", []):
            rtype = rw["reward_type"]
            if rtype == "xp":
                if rw["form"] == "fixed":
                    dst = skill_id(rw["skill"])
                    data = {"reward": "xp", "form": "fixed", "amount": rw["amount"]}
                else:  # choice_lamp / special: no single skill -> dst=None, carry the spec
                    dst = None
                    data = {"reward": "xp", **{k: v for k, v in rw.items()
                                               if k != "reward_type"}}
            elif rtype == "items":
                dst = item_id(rw["item_id"]) if rw.get("item_id") is not None else None
                data = {"reward": "items",
                        **{k: v for k, v in rw.items()
                           if k not in ("reward_type", "item", "item_id")}}
            elif rtype == "unlock":
                dst = access_id(rw["access"]) if rw.get("access") else None
                data = {"reward": "unlock",
                        **{k: v for k, v in rw.items()
                           if k not in ("reward_type", "access")}}
                if rw.get("access"):
                    data["access"] = rw["access"]
            elif rtype == "cosmetic":
                dst = None
                data = {"reward": "cosmetic",
                        **{k: v for k, v in rw.items() if k != "reward_type"}}
            else:
                raise ValueError(f"build_quest_rewards: unknown reward_type {rtype!r} "
                                 f"for quest {rec['quest']!r}")
            edges.append(Edge(id=_eid(qid, slot), type=EdgeType.GRANTS,
                              src=qid, dst=dst, cond_group=None, data=data))
            slot += 1

        # quest_points -> a counting contribution toward the QP cape (Task 5).
        qp = rec.get("quest_points")
        if qp:
            edges.append(Edge(id=_eid(qid, slot), type=EdgeType.PROGRESS_TOWARDS,
                              src=qid, dst=_QP_CAPE_GOAL, cond_group=None,
                              data={"weight": qp}))
            slot += 1

        # effects ride on the granted ITEM (or unlock); owner = the item node.
        for ef in rec.get("effects", []):
            iid = item_id(ef["rides_on_item_id"])
            data = {k: v for k, v in ef.items()
                    if k not in ("rides_on_item_id", "rides_on_item")}
            data["rides_on_item"] = ef.get("rides_on_item")
            edges.append(Edge(id=_eid(iid, 0), type=EdgeType.EFFECT,
                              src=iid, dst=None, cond_group=None, data=data))

    return nodes, edges, groups
```

> Note: `quest_points` / `progress_towards` handling is included here but only fires when a record carries `quest_points`; the seed in this task omits it (the goal node arrives in Task 5). The `test_*` for `progress_towards` lives in Task 5.

- [ ] **Step 4: Run the test to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_build_quest_rewards.py -v`
Expected: 5 passed.

- [ ] **Step 5: Author the minimal source-grounded seed `data/quest_rewards.json`**

Author 3 quests from the wiki (transcribe — do not invent values; if a value is uncertain, leave the reward out and note it). Use the `{_provenance, records, _excluded}` envelope:

```json
{
  "_provenance": {
    "domain": "quest_rewards",
    "source_urls": [
      "https://oldschool.runescape.wiki/w/Quest_experience_rewards",
      "https://oldschool.runescape.wiki/w/Quest_item_rewards",
      "https://oldschool.runescape.wiki/w/Unlockable_content"
    ],
    "accessed": "2026-06-22",
    "license": "CC BY-NC-SA 3.0",
    "extraction_method": "manual-transcription-from-wiki",
    "record_count": 3,
    "completeness": {
      "bounded_by": "owner-verified seed (machinery proof); full corpus is a follow-on plan",
      "universe_count": null,
      "records_count": 3,
      "known_missing": ["full quest corpus (deferred to follow-on sourcing plan)"],
      "known_missing_note": "Seed proves the taxonomy + builder + validator end-to-end."
    }
  },
  "records": [
    {
      "quest": "Waterfall Quest",
      "quest_points": 1,
      "rewards": [
        {"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750},
        {"reward_type": "xp", "form": "fixed", "skill": "Strength", "amount": 13750}
      ],
      "effects": [],
      "source_urls": ["https://oldschool.runescape.wiki/w/Waterfall_Quest"]
    },
    {
      "quest": "Recipe for Disaster",
      "quest_points": 1,
      "rewards": [
        {"reward_type": "items", "item": "Barrows gloves", "item_id": 7462, "qty": 1, "tradeable": false}
      ],
      "effects": [],
      "source_urls": ["https://oldschool.runescape.wiki/w/Recipe_for_Disaster"]
    },
    {
      "quest": "Fairytale I - Growing Pains",
      "quest_points": 2,
      "rewards": [
        {"reward_type": "unlock", "category": "skilling-method", "name": "Magic secateurs (herb yield)", "stage": "completed"}
      ],
      "effects": [
        {"rides_on_item": "Magic secateurs", "rides_on_item_id": 7409, "effect_kind": "rate_multiplier", "magnitude": 0.10, "target": "Farming herb yield", "condition": "while-wielded", "tier_source": "Fairytale I - Growing Pains"}
      ],
      "source_urls": ["https://oldschool.runescape.wiki/w/Fairytale_I_-_Growing_Pains"]
    }
  ],
  "_excluded": []
}
```

> Verify `item_id` 7462 (Barrows gloves) and 7409 (Magic secateurs) against `data/items_equipment.json` before committing (`grep` the file). If an id does not resolve, fix it — the validator (Task 6) will reject an unresolved id, but catch it now.

- [ ] **Step 6: Wire the builder into `kg_ingest/assemble.py`**

Add the import (after the `build_quests` import, line 29):

```python
from kg_ingest.builders.quest_rewards import build_quest_rewards
```

Add the loader (after `_load_quest_records`, ~line 168):

```python
QUEST_REWARDS_PATH = Path(__file__).resolve().parents[1] / "data" / "quest_rewards.json"


def _load_reward_records() -> list[dict]:
    if not QUEST_REWARDS_PATH.exists():
        return []
    return json.loads(QUEST_REWARDS_PATH.read_text())["records"]
```

In `assemble()`, build quests + rewards and rekey them **together** (so the quest-owned `requires` and `grants` edges share one per-owner index space). Replace the current steps 1–2 (lines 178–190) with:

```python
    # 1) run the builders (each returns builder-LOCAL group/edge ids).
    q_nodes, q_edges, q_groups, _diaries = build_quests(_load_quest_records())
    qr_nodes, qr_edges, qr_groups = build_quest_rewards(_load_reward_records())
    g_nodes, g_edges, g_groups = build_goals()

    # 2) re-key. Quests + quest-rewards share quest:* owners (requires + grants from the
    #    same quest), so they MUST be re-keyed in ONE call to get a continuous per-owner
    #    edge/group index (Task 3). Goals own disjoint ids -> re-keyed independently.
    qr_combined_nodes = q_nodes + qr_nodes
    qr_combined_edges = q_edges + qr_edges          # requires first, then grants (stable order)
    qr_combined_groups = {**q_groups, **qr_groups}
    q_nodes, q_edges, q_groups = rekey(qr_combined_nodes, qr_combined_edges, qr_combined_groups)
    g_nodes, g_edges, g_groups = rekey(g_nodes, g_edges, g_groups)

    edges = q_edges + g_edges
    groups = {**q_groups, **g_groups}
```

> `_collect_referenced_ids` already adds `e.dst` for all edge types, so reward `dst`s (`skill:`/`item:`/`access:`) are covered by `build_supporting` (all in `_LEAF_DOMAINS`). `goal:` dsts (from `progress_towards`, Task 5) are NOT leaf domains, so they are never sent to `build_supporting`; the `completion_goals` builder (Task 5) owns them.

- [ ] **Step 7: Re-assemble and validate**

Run: `./venv/bin/python -m kg_ingest.assemble`
Then: `./venv/bin/python data/validate_kg.py`
Expected: `KG VALIDATION PASSED ...`. The KG now contains `grants` + `effect` edges from the 3 seed quests. (`item:7409` becomes a supporting node via `build_supporting`.)
Then: `./venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add kg_ingest/builders/quest_rewards.py kg_ingest/assemble.py data/quest_rewards.json tests/kg_ingest/test_build_quest_rewards.py kg/
git commit -m "quest-foundation: quest-reward builder (grants + effect edges) + seed"
```

---

## Task 5: Completion goals — `goal:quest-point-cape`, `progress_towards`, threshold-gated grant

**Files:**
- Create: `kg_ingest/builders/completion_goals.py`
- Create: `data/completion_goals.json`
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_build_completion_goals.py`
- Test (add cases): `tests/kg_ingest/test_build_quest_rewards.py`

**Interfaces:**
- Consumes: `Edge.data` (Task 2), the rekey (Task 3), `AtomType.QUEST_POINTS` (existing), `NodeKind.GOAL` (Task 2).
- Produces: `build_completion_goals(goal_records: list[dict]) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]`. For each goal record it emits: one `Node(kind=GOAL, data={"counter_type","thresholds"})`; one `Edge(REQUIRES, src=goal, dst=None, cond_group=AND(<accumulator> >= final threshold))` (the completion gate — engine-evaluable); and, if the record has a `grants` payload, one **threshold-gated** `Edge(GRANTS, src=goal, dst=access:<slug>, cond_group=AND(<accumulator> >= threshold), data=<grant>)`. Goal-record `counter_type:"points"` → `AtomType.QUEST_POINTS` (ref-less accumulator). The `quest_rewards` builder's `progress_towards` edges (Task 4) point at `goal:quest-point-cape`.

- [ ] **Step 1: Write the failing test**

Create `tests/kg_ingest/test_build_completion_goals.py`:

```python
"""Tests for kg_ingest/builders/completion_goals.py (quest-foundation Task 5)."""
from kg_ingest.builders.completion_goals import build_completion_goals
from osrs_planner.engine.kg.model import AtomType, ConditionAtom, EdgeType, NodeKind, Op


def _qp_cape_record():
    return {
        "id": "goal:quest-point-cape",
        "name": "Quest point cape",
        "counter_type": "points",
        "accumulator": "quest_points",
        "thresholds": [33],
        "grants": {"reward": "unlock", "category": "equipment",
                   "name": "Quest point cape (untradeable)", "access": "Quest point cape"}
    }


def test_goal_node_carries_counter_type_and_thresholds():
    nodes, edges, groups = build_completion_goals([_qp_cape_record()])
    goal = [n for n in nodes if n.kind is NodeKind.GOAL]
    assert len(goal) == 1
    assert goal[0].id == "goal:quest-point-cape"
    assert goal[0].data == {"counter_type": "points", "thresholds": [33]}


def test_completion_requires_edge_uses_the_quest_points_accumulator():
    nodes, edges, groups = build_completion_goals([_qp_cape_record()])
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    assert req.src == "goal:quest-point-cape" and req.dst is None
    grp = groups[req.cond_group]
    atom = grp.children[0]
    assert isinstance(atom, ConditionAtom)
    assert atom.atom_type is AtomType.QUEST_POINTS and atom.threshold == 33


def test_threshold_gated_grant_fires_on_the_accumulator():
    nodes, edges, groups = build_completion_goals([_qp_cape_record()])
    grant = [e for e in edges if e.type is EdgeType.GRANTS][0]
    assert grant.src == "goal:quest-point-cape" and grant.dst == "access:quest-point-cape"
    assert grant.cond_group is not None  # the §5.1 threshold gate
    gate_atom = groups[grant.cond_group].children[0]
    assert gate_atom.atom_type is AtomType.QUEST_POINTS and gate_atom.threshold == 33
    assert grant.data["reward"] == "unlock"
```

Add to `tests/kg_ingest/test_build_quest_rewards.py`:

```python
def test_quest_points_becomes_progress_towards_the_cape():
    from osrs_planner.engine.kg.model import EdgeType
    rec = {"quest": "Waterfall Quest", "quest_points": 1, "rewards": []}
    _, edges, _ = build_quest_rewards([rec])
    pt = [e for e in edges if e.type is EdgeType.PROGRESS_TOWARDS]
    assert len(pt) == 1
    assert pt[0].src == "quest:waterfall-quest"
    assert pt[0].dst == "goal:quest-point-cape" and pt[0].data == {"weight": 1}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_build_completion_goals.py tests/kg_ingest/test_build_quest_rewards.py::test_quest_points_becomes_progress_towards_the_cape -v`
Expected: FAIL — `completion_goals` import error. (The `progress_towards` case already passes — that logic shipped in Task 4.)

- [ ] **Step 3: Implement `kg_ingest/builders/completion_goals.py`**

```python
"""Completion-goal builder (spec §5.1,§6; quest-foundation Task 5).

build_completion_goals(goal_records) -> (nodes, edges, groups)
Each record -> a GOAL node aggregating "complete enough of X", plus:
  - one REQUIRES edge (the completion gate: <accumulator> >= final threshold) — this is
    engine-evaluable, so is_unlocked(goal:...) works off the player's accumulator.
  - one THRESHOLD-GATED GRANTS edge (spec §5.1, the grant-side twin of progress_towards):
    the cape's own reward, gated by the SAME accumulator >= threshold cond_group.

counter_type 'points' uses the existing AtomType.QUEST_POINTS accumulator (ref-less).
(member_count / count_satisfied accumulators arrive with the diary/clog domains.)

The Quest cape IS the QP cape: ONE node, goal:quest-point-cape.

IDs (K9): builder-local bands 0x70000000/0x78000000 (disjoint from quests/goals/rewards).
assemble.rekey() re-keys to global ids; goal owners are unique so re-keyed independently.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, access_id, slugify

_GROUP_BAND = 0x70000000
_EDGE_BAND = 0x78000000

_ACCUMULATORS = {
    "points": AtomType.QUEST_POINTS,  # quest-domain points cape
}


def _gid(owner: str, slot: int) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner}#goal-group#{slot}")


def _eid(owner: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{owner}#goal-edge#{slot}")


def build_completion_goals(
    goal_records: list[dict],
) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    for rec in goal_records:
        gid_node = rec["id"]
        counter_type = rec["counter_type"]
        thresholds = rec["thresholds"]
        accum = _ACCUMULATORS.get(counter_type)
        if accum is None:
            raise ValueError(f"build_completion_goals: unsupported counter_type "
                             f"{counter_type!r} for {gid_node!r}")
        final_threshold = thresholds[-1]

        nodes.append(Node(id=gid_node, kind=NodeKind.GOAL, name=rec["name"],
                          slug=slugify(rec["name"]),
                          data={"counter_type": counter_type, "thresholds": thresholds}))

        # completion gate (REQUIRES): accumulator >= final threshold.
        req_gid = _gid(gid_node, 0)
        groups[req_gid] = ConditionGroup(
            id=req_gid, op=Op.AND, parent=None,
            children=[ConditionAtom(atom_type=accum, threshold=final_threshold)])
        edges.append(Edge(id=_eid(gid_node, 0), type=EdgeType.REQUIRES,
                          src=gid_node, dst=None, cond_group=req_gid))

        # threshold-gated GRANTS (§5.1): the cape's own reward, fired by the accumulator.
        grant = rec.get("grants")
        if grant:
            grant_gid = _gid(gid_node, 1)
            groups[grant_gid] = ConditionGroup(
                id=grant_gid, op=Op.AND, parent=None,
                children=[ConditionAtom(atom_type=accum, threshold=final_threshold)])
            dst = access_id(grant["access"]) if grant.get("access") else None
            data = {k: v for k, v in grant.items() if k != "access"}
            if grant.get("access"):
                data["access"] = grant["access"]
            edges.append(Edge(id=_eid(gid_node, 1), type=EdgeType.GRANTS,
                              src=gid_node, dst=dst, cond_group=grant_gid, data=data))

    return nodes, edges, groups
```

- [ ] **Step 4: Author `data/completion_goals.json`**

```json
{
  "_provenance": {
    "domain": "completion_goals",
    "source_urls": [
      "https://oldschool.runescape.wiki/w/Quest_point_cape",
      "https://oldschool.runescape.wiki/w/Quests/List"
    ],
    "accessed": "2026-06-22",
    "license": "CC BY-NC-SA 3.0",
    "extraction_method": "manual-transcription-from-wiki",
    "record_count": 1,
    "completeness": {
      "bounded_by": "quest-domain completion goals; member_count goals (music/diary/clog cape) arrive with their feeder domains",
      "records_count": 1,
      "known_missing": ["goal:music-cape", "goal:diary-cape", "goal:clog (DROPS-fed)"],
      "known_missing_note": "The Quest cape IS the QP cape — one node. Other completion goals are deferred to their domains."
    }
  },
  "records": [
    {
      "id": "goal:quest-point-cape",
      "name": "Quest point cape",
      "counter_type": "points",
      "accumulator": "quest_points",
      "thresholds": [33],
      "grants": {"reward": "unlock", "category": "equipment", "name": "Quest point cape", "access": "Quest point cape"},
      "note": "thresholds = total QP required for the cape; VERIFY the current total against the wiki before relying on it (living game)."
    }
  ]
}
```

> The `thresholds` value is the *current* total quest points required for the cape — **fetch and confirm it from the wiki**; do not trust the example `33`. The owner verifies this number.

- [ ] **Step 5: Wire `build_completion_goals` into `kg_ingest/assemble.py`**

Add import (after the `build_quest_rewards` import):

```python
from kg_ingest.builders.completion_goals import build_completion_goals
```

Add loader (after `_load_reward_records`):

```python
COMPLETION_GOALS_PATH = Path(__file__).resolve().parents[1] / "data" / "completion_goals.json"


def _load_completion_goal_records() -> list[dict]:
    if not COMPLETION_GOALS_PATH.exists():
        return []
    return json.loads(COMPLETION_GOALS_PATH.read_text())["records"]
```

In `assemble()`, build + rekey the completion goals alongside `build_goals()` and merge:

```python
    g_nodes, g_edges, g_groups = build_goals()
    cg_nodes, cg_edges, cg_groups = build_completion_goals(_load_completion_goal_records())
```

and after the existing `g_nodes, g_edges, g_groups = rekey(...)` line add:

```python
    cg_nodes, cg_edges, cg_groups = rekey(cg_nodes, cg_edges, cg_groups)
```

and extend the merge:

```python
    edges = q_edges + g_edges + cg_edges
    groups = {**q_groups, **g_groups, **cg_groups}
```

and include the completion-goal nodes in the final dedup (step 4 of `assemble`):

```python
    owned_ids = {n.id for n in q_nodes} | {n.id for n in g_nodes} | {n.id for n in cg_nodes}
    ...
    nodes = dedup_nodes(q_nodes + g_nodes + cg_nodes + s_nodes)
```

> `goal:` is not in `_LEAF_DOMAINS`, so a `progress_towards` edge's `goal:` dst is never sent to `build_supporting`; it resolves to the node built here.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_build_completion_goals.py tests/kg_ingest/test_build_quest_rewards.py -v`
Expected: all pass (6 + 1 new).

- [ ] **Step 7: Re-assemble and validate**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python data/validate_kg.py`
Expected: `KG VALIDATION PASSED ...`. The KG now has `goal:quest-point-cape`, its completion `requires` edge, its threshold-gated `grants`, and `progress_towards` edges from the 3 seed quests.
Then: `./venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add kg_ingest/builders/completion_goals.py kg_ingest/assemble.py data/completion_goals.json tests/kg_ingest/ kg/
git commit -m "quest-foundation: completion goals — QP cape, progress_towards, threshold-gated grant"
```

---

## Task 6: `data/validate_quest_rewards.py` — structural reward validator

**Files:**
- Create: `data/validate_quest_rewards.py`
- Test: `tests/kg_ingest/test_validate_quest_rewards.py`

**Interfaces:**
- Consumes: `data/quest_rewards.json`, `data/completion_goals.json`, `data/items_equipment.json`, the committed quest node ids (from `data/quests.json`).
- Produces: `validate_quest_rewards.check_quest_rewards(reward_data, goal_data, item_ids, item_tradeable, quest_names) -> list[str]` (pure) + `main() -> int`. `item_ids: set[int]`, `item_tradeable: dict[int,bool]`, `quest_names: set[str]`.

- [ ] **Step 1: Write the failing test**

Create `tests/kg_ingest/test_validate_quest_rewards.py`:

```python
"""Tests for data/validate_quest_rewards.py — structural reward validator (Task 6)."""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "validate_quest_rewards.py")
_spec = importlib.util.spec_from_file_location("validate_quest_rewards", _PATH)
vqr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vqr)

_ITEM_IDS = {7462, 7409}
_ITEM_TRADEABLE = {7462: False, 7409: True}
_QUESTS = {"Waterfall Quest", "Recipe for Disaster"}


def _data(records):
    return {"_provenance": {"source_urls": ["x"]}, "records": records}


def _ok_record():
    return {"quest": "Waterfall Quest", "quest_points": 1,
            "rewards": [{"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750}],
            "effects": []}


def test_valid_record_has_no_violations():
    errs = vqr.check_quest_rewards(_data([_ok_record()]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert errs == [], errs


def test_unresolved_item_id_is_flagged():
    rec = {"quest": "Recipe for Disaster", "rewards": [
        {"reward_type": "items", "item": "Fake", "item_id": 999999, "qty": 1, "tradeable": False}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("999999" in e for e in errs), errs


def test_unknown_quest_is_flagged():
    rec = dict(_ok_record(), quest="Nonexistent Quest")
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("Nonexistent Quest" in e for e in errs), errs


def test_bad_unlock_category_is_flagged():
    rec = {"quest": "Waterfall Quest", "rewards": [
        {"reward_type": "unlock", "category": "not-a-category", "stage": "completed"}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("not-a-category" in e for e in errs), errs


def test_tradeable_flag_mismatch_is_flagged():
    # Barrows gloves (7462) is untradeable; a record claiming tradeable=true is wrong.
    rec = {"quest": "Recipe for Disaster", "rewards": [
        {"reward_type": "items", "item": "Barrows gloves", "item_id": 7462, "qty": 1, "tradeable": True}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("tradeable" in e and "7462" in e for e in errs), errs


def test_committed_seed_passes():
    rc = vqr.main([])
    assert rc == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_validate_quest_rewards.py -v`
Expected: import error (module does not exist).

- [ ] **Step 3: Implement `data/validate_quest_rewards.py`**

```python
#!/usr/bin/env python3
"""Quest-reward structural validator (spec §10,§11; quest-foundation Task 6).

Committed, deterministic guard over data/quest_rewards.json + data/completion_goals.json.
Checks STRUCTURE + referential integrity (NOT editorial truth — that is the owner's
review). Mirrors the data/validate_*.py idiom: pure check_* + main() exit 0/1.

Usage:  ./venv/bin/python data/validate_quest_rewards.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REWARDS_PATH = os.path.join(ROOT, "data", "quest_rewards.json")
GOALS_PATH = os.path.join(ROOT, "data", "completion_goals.json")
ITEMS_PATH = os.path.join(ROOT, "data", "items_equipment.json")
QUESTS_PATH = os.path.join(ROOT, "data", "quests.json")

_REWARD_TYPES = {"xp", "items", "unlock", "cosmetic"}
_XP_FORMS = {"fixed", "choice_lamp", "special"}
_UNLOCK_CATEGORIES = {
    "skill", "equipment", "skilling-method", "magic", "spellbook", "prayer",
    "location", "area", "transportation", "guild", "shortcut", "monster",
    "slayer", "minigame", "shop", "respawn-point", "area-effect",
}
_STAGES = {"started", "in_progress", "completed"}
_EFFECT_KINDS = {
    "stat_multiplier", "rate_multiplier", "capacity_change", "fee_waiver",
    "behavior_toggle", "recurring_resource", "access",
}
_COUNTER_TYPES = {"points", "member_count", "tier_count"}


def check_quest_rewards(reward_data: dict, goal_data: dict, item_ids: set,
                        item_tradeable: dict, quest_names: set) -> list[str]:
    errors: list[str] = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    check(reward_data.get("_provenance", {}).get("source_urls"),
          "quest_rewards: _provenance.source_urls missing or empty")

    granted_item_ids: dict[str, set] = {}  # quest -> set(item_id) granted (for effect cross-check)
    for rec in reward_data.get("records", []):
        q = rec.get("quest")
        check(q in quest_names, f"quest_rewards: quest {q!r} resolves to no quest record")
        granted_item_ids.setdefault(q, set())

        qp = rec.get("quest_points")
        check(qp is None or (isinstance(qp, int) and qp >= 0),
              f"quest_rewards: {q!r} quest_points {qp!r} must be a non-negative int")

        for rw in rec.get("rewards", []):
            rt = rw.get("reward_type")
            check(rt in _REWARD_TYPES, f"quest_rewards: {q!r} bad reward_type {rt!r}")
            if rt == "xp":
                check(rw.get("form") in _XP_FORMS, f"quest_rewards: {q!r} bad xp form {rw.get('form')!r}")
                check(isinstance(rw.get("amount"), int) and rw["amount"] > 0,
                      f"quest_rewards: {q!r} xp amount must be a positive int, got {rw.get('amount')!r}")
                if rw.get("form") == "fixed":
                    check(rw.get("skill"), f"quest_rewards: {q!r} fixed xp missing skill")
            elif rt == "items":
                iid = rw.get("item_id")
                check(iid in item_ids,
                      f"quest_rewards: {q!r} item reward item_id {iid!r} resolves to no items_equipment item")
                if iid in item_ids and "tradeable" in rw:
                    check(bool(rw["tradeable"]) == bool(item_tradeable.get(iid)),
                          f"quest_rewards: {q!r} item {iid} tradeable={rw['tradeable']} "
                          f"disagrees with items_equipment ({item_tradeable.get(iid)})")
                    granted_item_ids[q].add(iid)
            elif rt == "unlock":
                check(rw.get("category") in _UNLOCK_CATEGORIES,
                      f"quest_rewards: {q!r} bad unlock category {rw.get('category')!r}")
                check(rw.get("stage") in _STAGES,
                      f"quest_rewards: {q!r} bad unlock stage {rw.get('stage')!r}")
            elif rt == "cosmetic":
                check(rw.get("kind"), f"quest_rewards: {q!r} cosmetic missing kind")

        for ef in rec.get("effects", []):
            check(ef.get("effect_kind") in _EFFECT_KINDS,
                  f"quest_rewards: {q!r} bad effect_kind {ef.get('effect_kind')!r}")
            iid = ef.get("rides_on_item_id")
            check(iid in item_ids,
                  f"quest_rewards: {q!r} effect rides_on_item_id {iid!r} resolves to no item")
            # The effect's item should be granted by the same quest (or disclosed otherwise).
            check(iid in granted_item_ids.get(q, set()) or ef.get("rides_on_external"),
                  f"quest_rewards: {q!r} effect rides on item {iid} that this quest does not grant "
                  f"(set rides_on_external:true to disclose an intentional cross-reference)")

    for rec in goal_data.get("records", []):
        gid = rec.get("id", "?")
        check(str(gid).startswith("goal:"), f"completion_goals: id {gid!r} must start with 'goal:'")
        check(rec.get("counter_type") in _COUNTER_TYPES,
              f"completion_goals: {gid!r} bad counter_type {rec.get('counter_type')!r}")
        thr = rec.get("thresholds")
        check(isinstance(thr, list) and thr and all(isinstance(t, int) and t > 0 for t in thr),
              f"completion_goals: {gid!r} thresholds must be a non-empty list of positive ints, got {thr!r}")
    return errors


def main(argv=None) -> int:
    with open(REWARDS_PATH, encoding="utf-8") as f:
        reward_data = json.load(f)
    goal_data = {"records": []}
    if os.path.exists(GOALS_PATH):
        with open(GOALS_PATH, encoding="utf-8") as f:
            goal_data = json.load(f)
    with open(ITEMS_PATH, encoding="utf-8") as f:
        items = json.load(f)["records"]
    item_ids = {r["item_id"] for r in items if r.get("item_id") is not None}
    item_tradeable = {r["item_id"]: bool(r.get("tradeable"))
                      for r in items if r.get("item_id") is not None}
    with open(QUESTS_PATH, encoding="utf-8") as f:
        quest_names = {r["name"] for r in json.load(f)["records"]
                       if r.get("node_type") in ("quest", "miniquest")}

    errors = check_quest_rewards(reward_data, goal_data, item_ids, item_tradeable, quest_names)
    if errors:
        print(f"QUEST-REWARDS VALIDATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1
    print("QUEST-REWARDS VALIDATION PASSED — reward/goal structure + references hold.")
    print(f"  quest reward records: {len(reward_data.get('records', []))}")
    print(f"  completion goals: {len(goal_data.get('records', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_validate_quest_rewards.py -v`
Expected: 6 passed (incl. `test_committed_seed_passes`). If `test_committed_seed_passes` fails, the seed authored in Tasks 4–5 has a real structural error — fix the seed, not the test.

- [ ] **Step 5: Run the validator directly**

Run: `./venv/bin/python data/validate_quest_rewards.py`
Expected: `QUEST-REWARDS VALIDATION PASSED ...` (exit 0).

- [ ] **Step 6: Commit**

```bash
git add data/validate_quest_rewards.py tests/kg_ingest/test_validate_quest_rewards.py
git commit -m "quest-foundation: structural quest-reward validator"
```

---

## Task 7: Reward-aware KG invariants + integration

**Files:**
- Modify: `data/validate_kg.py`
- Test: `tests/kg_ingest/test_validate_kg.py` (add cases)

**Interfaces:**
- Consumes: the built KG with `grants`/`effect`/`progress_towards` edges + `goal:` nodes.
- Produces: `check_kg` additionally enforces: (a) every `progress_towards` edge has a numeric `data["weight"]` and a `dst` that is a `goal:` node; (b) every `goal:` node has `data.counter_type` + a non-empty `data.thresholds`; (c) every `grants` edge carries a `data["reward"]` string. These are added to the existing `check_kg(...)` (the generic `[ref]` checks already cover endpoint resolution for all edge types).

- [ ] **Step 1: Write the failing test**

Add to `tests/kg_ingest/test_validate_kg.py`:

```python
def test_progress_towards_without_weight_is_flagged():
    nodes = [
        Node(id="quest:x", kind=NodeKind.QUEST, name="X", slug="x", data={}),
        Node(id="goal:quest-point-cape", kind=NodeKind.GOAL, name="QP cape",
             slug="quest-point-cape", data={"counter_type": "points", "thresholds": [2]}),
    ]
    edges = [Edge(id=8001, type=EdgeType.PROGRESS_TOWARDS, src="quest:x",
                  dst="goal:quest-point-cape", cond_group=None, data={})]  # no weight
    store = InMemoryKGStore(nodes, edges, {})
    v = validate_kg.check_kg(store, _quests_data(["X"]))
    assert any("weight" in e and "8001" in e for e in v), v


def test_goal_node_without_counter_type_is_flagged():
    nodes = [Node(id="goal:bad", kind=NodeKind.GOAL, name="Bad", slug="bad", data={})]
    store = InMemoryKGStore(nodes, [], {})
    v = validate_kg.check_kg(store, _quests_data([]))
    assert any("goal:bad" in e and "counter_type" in e for e in v), v


def test_progress_towards_to_non_goal_is_flagged():
    nodes = [
        Node(id="quest:x", kind=NodeKind.QUEST, name="X", slug="x", data={}),
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={}),
    ]
    edges = [Edge(id=8002, type=EdgeType.PROGRESS_TOWARDS, src="quest:x",
                  dst="skill:attack", cond_group=None, data={"weight": 1})]
    store = InMemoryKGStore(nodes, edges, {})
    v = validate_kg.check_kg(store, _quests_data(["X"]))
    assert any("8002" in e and "goal" in e for e in v), v
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest "tests/kg_ingest/test_validate_kg.py::test_progress_towards_without_weight_is_flagged" "tests/kg_ingest/test_validate_kg.py::test_goal_node_without_counter_type_is_flagged" "tests/kg_ingest/test_validate_kg.py::test_progress_towards_to_non_goal_is_flagged" -v`
Expected: 3 FAIL (no such invariants yet).

- [ ] **Step 3: Add the reward-aware invariants to `check_kg`**

In `data/validate_kg.py`, inside `check_kg`, after the edge referential-integrity loop (after current line 180, before the group walk at line 182), add:

```python
    # --- Reward-edge + goal-node invariants (quest-foundation) ---
    goal_ids = {nid for nid, n in store.nodes.items()
                if (n.kind.value if hasattr(n.kind, "value") else n.kind) == NodeKind.GOAL.value}
    for e in store.edges:
        if e.type is EdgeType.PROGRESS_TOWARDS:
            w = (e.data or {}).get("weight")
            if not isinstance(w, int) or w <= 0:
                errors.append(f"[reward] progress_towards edge {e.id} has non-positive/missing "
                              f"data.weight {w!r}")
            if e.dst not in goal_ids:
                errors.append(f"[reward] progress_towards edge {e.id} dst {e.dst!r} is not a goal node")
        elif e.type is EdgeType.GRANTS:
            if not (e.data or {}).get("reward"):
                errors.append(f"[reward] grants edge {e.id} missing data.reward")
    for nid in goal_ids:
        data = store.nodes[nid].data or {}
        if data.get("counter_type") is None:
            errors.append(f"[goal] node {nid} missing data.counter_type")
        if not data.get("thresholds"):
            errors.append(f"[goal] node {nid} missing/empty data.thresholds")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_validate_kg.py -v`
Expected: all pass (existing + 3 new).

- [ ] **Step 5: Full integration — re-assemble, validate, demo, suite**

Run, in order:
```bash
./venv/bin/python -m kg_ingest.assemble
git diff --stat kg/                                   # expect only additive reward edges/nodes/groups
./venv/bin/python data/validate_kg.py                 # KG VALIDATION PASSED
./venv/bin/python data/validate_quest_rewards.py      # QUEST-REWARDS VALIDATION PASSED
./venv/bin/python data/audit_quest_requirements.py    # AUDIT PASSED (offline)
./venv/bin/python -m kg_ingest.assemble && git diff --quiet kg/ && echo "BYTE-STABLE"
./venv/bin/python -m pytest -q                        # all pass
```
Expected: each validator exits 0; the second assemble produces no diff (`BYTE-STABLE`); full suite green.

- [ ] **Step 6: Commit**

```bash
git add data/validate_kg.py tests/kg_ingest/test_validate_kg.py kg/
git commit -m "quest-foundation: reward-aware KG invariants + integration"
```

---

## Task 8: Owner-verified seed expansion + cross-domain documentation

**Files:**
- Modify: `data/quest_rewards.json` (expand to ~15 quests spanning every reward shape)
- Modify: `data/completion_goals.json` (confirm the QP-cape threshold against the live wiki)
- Add (raw): the fetched reward-page raws under `data/raw/` (provenance)
- Create: `data/QUEST_REWARDS.md` (format reference + cross-domain reuse + disclosed limitations)

**Interfaces:**
- Consumes: all prior tasks' machinery (builder, validators, assemble).
- Produces: an owner-reviewable seed (`data/quest_rewards.json`) covering: fixed XP, choice-lamp XP, a split-allocation or special XP, tradeable + untradeable items, a conditional item reward (§3.6 — exercises the cond_group path through the Task-3 rekey), stage-tagged unlocks (`started`/`in_progress`/`completed`), a `skill` unlock, a numeric `effect`, a non-numeric `effect` (e.g. `behavior_toggle`), `quest_points`, and a `cosmetic`. The doc records the format and how Diaries/CAs/Clogs/Clues reuse it.

- [ ] **Step 1: Fetch the reward source pages (raw, with provenance)**

Fetch the three canonical reward pages via `?action=raw` (the repo's established pattern — `urllib`, User-Agent `GildedTome-research/1.0 (aalvarez0295@gmail.com)`), saving each to `data/raw/`:
```bash
./venv/bin/python - <<'PY'
import urllib.request, os
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
RAW = "data/raw"
pages = {
  "quest_experience_rewards_raw.wikitext": "https://oldschool.runescape.wiki/w/Quest_experience_rewards?action=raw",
  "quest_item_rewards_raw.wikitext": "https://oldschool.runescape.wiki/w/Quest_item_rewards?action=raw",
  "unlockable_content_raw.wikitext": "https://oldschool.runescape.wiki/w/Unlockable_content?action=raw",
}
for fn, url in pages.items():
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        open(os.path.join(RAW, fn), "wb").write(r.read())
    print("wrote", fn)
PY
```
If the network is unavailable in this environment, STOP and report — the seed must be sourced from these pages, not from memory. (The machinery from Tasks 1–7 is already complete and committed; this task is the source-grounded data fill.)

- [ ] **Step 2: Author the expanded seed from the fetched raws**

Transcribe ~15 quests' rewards from the fetched pages into `data/quest_rewards.json`, covering every shape listed in the Interfaces block above. For each `item_id`, confirm it resolves in `data/items_equipment.json` and that `tradeable` matches. For the conditional item reward, model the condition explicitly (e.g. Ava's accumulator requires Ranged ≥ 50) as a `condition` field — and add a `cond_group`-bearing variant the builder turns into a gated grant (extend `build_quest_rewards` to emit a cond_group when a reward has a `condition`, mirroring `build_completion_goals`'s gated-grant construction; add a unit test for it in `tests/kg_ingest/test_build_quest_rewards.py`). Update each file's `_provenance.record_count`, `completeness`, and `accessed`.

> Discipline: transcribe, do not invent. If a number is uncertain, leave that reward out and add it to `known_missing`. The owner reviews the finished seed.

- [ ] **Step 3: Re-validate the expanded seed**

Run:
```bash
./venv/bin/python data/validate_quest_rewards.py
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py
./venv/bin/python -m pytest -q
```
Expected: both validators exit 0; suite green. Fix any reported structural issue in the *data* (not the validators).

- [ ] **Step 4: Write the cross-domain documentation**

Create `data/QUEST_REWARDS.md` documenting: the `quest_rewards.json` / `completion_goals.json` record schemas; the reward_type → edge mapping; how the same taxonomy serves Diaries/CAs (threshold-gated grants + `effect`), Collection Log (`progress_towards` fed by `DROPS`, `member_count`), and Clue Scrolls (`tier_count` + threshold-gated grants); and the **disclosed limitations** (§11): this is an owner-verified *seed*, not the full corpus; `count_satisfied`/`member_count` accumulators and the cross-builder effect-edge collision check (currently caught by `validate_kg`'s duplicate-id guard) are noted for the follow-on domains; reward editorial correctness is owner-gated, not validator-gated.

- [ ] **Step 5: Owner review gate**

Present the seed (`data/quest_rewards.json` + `data/completion_goals.json`) to the owner for editorial review (the live-player check the validator cannot perform). Apply corrections. This step is a human gate — do not mark the task complete until the owner has reviewed the reward values.

- [ ] **Step 6: Commit**

```bash
git add data/quest_rewards.json data/completion_goals.json data/raw/*reward*raw.wikitext data/raw/unlockable_content_raw.wikitext data/QUEST_REWARDS.md kg/ tests/kg_ingest/test_build_quest_rewards.py
git commit -m "quest-foundation: owner-verified reward seed + cross-domain taxonomy doc"
```

---

## Self-Review

**1. Spec coverage:**
- §2 axis 1 (correctness) → Task 1. §2 axis 2 (completeness) → Tasks 2–8.
- §3.1 `quest_points` → Task 4/5 (`progress_towards` + the QP-cape accumulator). §3.2 xp fixed/choice-lamp/special → Task 4 builder + Task 8 seed. §3.3 items + `tradeable` iron-lens → Task 4 (dst=item, data.tradeable) + Task 6 (tradeable cross-check vs items_equipment). §3.4 unlocks (categories, stage) → Task 4 + Task 6 enum. §3.5 cosmetics → Task 4. §3.6 conditional/choice → Task 8 (conditional grant via cond_group + the Task-3 rekey). §3.7 random-bundle → **not in the seed** (named in the doc as deferred; the format admits it, no quest in the seed needs it — YAGNI).
- §4 `effect` (effect_kind enum, magnitude, tier_source) → Task 4 EFFECT edges + Task 6 enum. §5 edges → Task 2 (types) + Tasks 4–5 (emission). §5.1 threshold-gated grants → Task 5 (QP-cape grant) + Task 8 (conditional item). §6 completion goals ({counter_type, thresholds}; cape = ONE node) → Task 5.
- §7 source map → Tasks 1 + 8. §8 cross-domain reuse → Task 8 doc. §9 deferred sockets → documented, not built. §10 scope (audit + taxonomy + reward build + validator + doc) → all tasks. §10.1 5-W → covered by the model; deferrals already disclosed in the spec. §11 limitations → Task 8 doc + provenance `known_missing`.
- **Deliberate scope cut (Option A, owner-deferred decision):** full-corpus reward sourcing is a follow-on plan; this plan ships the machinery + an owner-verified seed. Recorded here and in Task 8's provenance so it is not a silent gap.

**2. Placeholder scan:** No "TBD"/"handle errors"/"similar to Task N". Every code step shows complete code; every test step shows real assertions; the only human-judgment steps (Task 8 sourcing + owner review) are explicitly flagged as such, not hidden as code.

**3. Type consistency:** `build_quest_rewards(reward_records) -> (nodes, edges, groups)` and `build_completion_goals(goal_records) -> (nodes, edges, groups)` used identically in their tasks + `assemble`. `Edge.data` added in Task 2 is consumed by Tasks 3 (rekey carries it), 4/5 (builders set it), 7 (validator reads it). `goal:quest-point-cape` id string consistent across Tasks 4 (`_QP_CAPE_GOAL`), 5 (record `id`), 7 (tests). `AtomType.QUEST_POINTS` (existing) used for the points accumulator throughout. Unlock-category + effect-kind enums match between the builder (Task 4) and the validator (Task 6). Builder-local id bands disjoint (quests `0x1/0x2`, goals `0x3/0x4`, quest_rewards `0x5/0x6`, completion_goals `0x7/0x78`).
