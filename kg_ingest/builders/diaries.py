"""Achievement-diary builder (diaries spec §2,§3,§4,§6). Grows across Tasks 2/5/7.

Task 2: 48 diary:<region>:<tier> tier nodes + a requires edge per tier (the tier's
aggregate gate: max skill level per skill across the tier's tasks + union of quest
prereqs). The 492 per-task details are retained in node.data["tasks"] for route detail;
the engine gates tier completion via the existing achievement_diary atom, not per-task.

IDs (K9): builder-local bands 0x90000000 (group) / 0x98000000 (edge). assemble.rekey()
re-keys to global ids. Region display->slug via supporting.DIARY_REGION_LABELS (inverted).

Quest-req parsing (resolution §1):
  'Completion of X'         -> state=completed
  'Partial completion of X' -> state=in_progress
  'Partial X'               -> state=in_progress
  'Started X'               -> state=in_progress
  Entries with no recognized prefix (item/skill noise, compound prose) -> skipped + counted.
  After outer-prefix strip, the remainder is tried as a single quest name first. If that
  fails, it is split on ', ' / ' and ' into parts; each part may carry a sub-prefix
  ('having started', 'completion of', 'partial ...') that overrides the outer state. Each
  part is then resolved independently: real quest parts become QUEST atoms; unresolvable
  parts are skipped + counted. The whole-name-first strategy preserves quests whose names
  contain 'and' (e.g. 'Skippy and the Mogres').
  Total skipped stored in node.data["skipped_quest_reqs"] for disclosure.
"""
from __future__ import annotations

import re
from pathlib import Path

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, diary_tier_id, skill_id
from kg_ingest.builders.supporting import DIARY_REGION_LABELS

_GROUP_BAND = 0x90000000
_EDGE_BAND = 0x98000000
_REGION_SLUG: dict[str, str] = {label: slug for slug, label in DIARY_REGION_LABELS.items()}
_TIERS = ("easy", "medium", "hard", "elite")

_STATE_RANK = {"completed": 1, "in_progress": 0}

_PAREN_SUFFIX = re.compile(r"\s*\(.*?\)\s*$")
_COMPOUND_SEP = re.compile(r",\s+|\s+and\s+")


def _gid(owner: str, slot: int) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner}#diary-group#{slot}")


def _eid(owner: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{owner}#diary-edge#{slot}")


def _region_slug(display: str) -> str:
    if display not in _REGION_SLUG:
        raise ValueError(f"build_diaries: unknown diary_region {display!r}")
    return _REGION_SLUG[display]


_OUTER_PREFIXES = (
    ("Completion of ", "completed"),
    ("Partial completion of ", "in_progress"),
    ("Partial ", "in_progress"),
    ("Started ", "in_progress"),
)

_PART_PREFIXES = (
    ("having completed ", "completed"),
    ("completion of ", "completed"),
    ("having started ", "in_progress"),
    ("started ", "in_progress"),
    ("partial completion of ", "in_progress"),
    ("partial ", "in_progress"),
)


def _resolve_quest_id(name: str, known_slugs: frozenset[str]) -> str | None:
    """Resolve a quest name to a quest:* node id, or None if unresolvable.

    Strategy (handles diary data that omits the 'The ' article prefix, e.g.
    'Fremennik Trials' -> 'The Fremennik Trials', and entries ending in ' quest'):
      1. Direct slug
      2. Strip leading 'the '/'The ' and retry
      3. Prepend 'The ' and retry
      4. Strip trailing ' quest' (case-insensitive) and retry each of the above
    """
    from kg_ingest.ids import slugify as _slugify

    def _try(n: str) -> str | None:
        qid = f"quest:{_slugify(n)}"
        return qid if qid in known_slugs else None

    attempts = [name]
    if name.lower().startswith("the "):
        attempts.append(name[4:])
    attempts.append("The " + name)
    if name.lower().startswith("the "):
        attempts.append("The " + name[4:])

    base_attempts = list(attempts)
    for a in base_attempts:
        if a.lower().endswith(" quest"):
            stripped = a[:-6]
            attempts.extend([stripped, "The " + stripped])

    for attempt in attempts:
        result = _try(attempt)
        if result is not None:
            return result
    return None


def _parse_compound_quest_req(
    raw: str,
    known_slugs: frozenset[str],
) -> tuple[dict[str, str], int]:
    """Parse a single diary quest-req string into resolved quest atoms.

    Returns (quest_states, skipped_count) where quest_states maps quest_id -> state.

    Algorithm:
      1. Strip trailing parentheticals.
      2. Match one of the outer prefixes to get (remainder, outer_state). If none
         matches, the entry has no recognized prefix: skip it (return {}, 1).
      3. Try resolving the full remainder as a single quest name. If it resolves,
         return that one atom. This preserves quests whose names contain 'and'
         (e.g. 'Skippy and the Mogres').
      4. Otherwise split remainder on ', ' / ' and ' into parts. For each part,
         detect an optional sub-prefix (case-insensitive) that overrides outer_state.
         Resolve the part name; if it resolves → atom; else → count as skipped.
    """
    s = _PAREN_SUFFIX.sub("", raw.strip())
    outer_state: str | None = None
    remainder = s
    for prefix, state in _OUTER_PREFIXES:
        if s.startswith(prefix):
            remainder = s[len(prefix):].strip()
            outer_state = state
            break
    if outer_state is None:
        return {}, 1  # no recognized prefix → skip

    # Try the whole remainder as a single quest name first.
    single_qid = _resolve_quest_id(remainder, known_slugs)
    if single_qid is not None:
        return {single_qid: outer_state}, 0

    # Split into parts and resolve each independently.
    parts = _COMPOUND_SEP.split(remainder)
    quest_states: dict[str, str] = {}
    skipped = 0
    for part in parts:
        part = part.strip()
        if not part:
            continue
        state = outer_state
        for prefix, s in _PART_PREFIXES:
            if part.lower().startswith(prefix):
                part = part[len(prefix):].strip()
                state = s
                break
        qid = _resolve_quest_id(part, known_slugs)
        if qid is not None:
            existing = quest_states.get(qid)
            if existing is None or _STATE_RANK[state] > _STATE_RANK[existing]:
                quest_states[qid] = state
        else:
            skipped += 1

    return quest_states, skipped


def build_diaries(
    task_records: list[dict],
    reward_records: list[dict] | None = None,
    content_records: list[dict] | None = None,
) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    """Build 48 diary tier nodes + one requires edge per tier from 492 task records.

    Returns (nodes, edges, groups) with builder-local ids (rekey() globalises them).
    """
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    # Group tasks by (region_slug, tier)
    by_tier: dict[tuple[str, str], list[dict]] = {}
    for rec in task_records:
        key = (_region_slug(rec["diary_region"]), rec["tier"])
        by_tier.setdefault(key, []).append(rec)

    # Build the known quest slug set from the KG nodes directory when available;
    # fall back to None (caller can't inject at import time). Unresolvable refs
    # get skipped with disclosure — validate_kg catches truly dangling refs.
    _repo = Path(__file__).resolve().parents[2]
    _known_slugs: frozenset[str] = frozenset()
    try:
        import json
        _nodes_path = _repo / "kg" / "nodes.json"
        if _nodes_path.exists():
            _raw_nodes = json.loads(_nodes_path.read_text())
            _known_slugs = frozenset(
                n["id"] for n in _raw_nodes if n.get("id", "").startswith("quest:")
            )
    except Exception:
        pass

    # Also build from quests.json (the authoritative source), if available.
    try:
        import json as _json2
        _quests_path = _repo / "data" / "quests.json"
        _qd = _json2.loads(_quests_path.read_text())
        from kg_ingest.ids import slugify as _slugify2
        _known_slugs = _known_slugs | frozenset(
            f"quest:{_slugify2(r['name'])}" for r in _qd.get("records", [])
        )
    except Exception:
        pass

    for (region, tier) in sorted(by_tier):
        tasks = by_tier[(region, tier)]
        nid = diary_tier_id(region, tier)
        region_label = DIARY_REGION_LABELS[region]

        # Aggregate requirements: max level per skill, union of quest prereqs.
        max_skill: dict[str, tuple[int, bool]] = {}  # skill_slug -> (level, boostable)
        quest_states: dict[str, str] = {}            # quest_id -> strictest state
        skipped_count = 0

        for t in tasks:
            for s in t["requirements"].get("skills", []):
                sk = skill_id(s["skill"])
                lvl = s["level"]
                boost = bool(t.get("boostable", False))
                cur = max_skill.get(sk)
                if cur is None or lvl > cur[0]:
                    max_skill[sk] = (lvl, boost)

            for q_raw in t["requirements"].get("quests", []):
                resolved, skipped = _parse_compound_quest_req(q_raw, _known_slugs)
                skipped_count += skipped
                for q_id, state in resolved.items():
                    existing = quest_states.get(q_id)
                    if existing is None or _STATE_RANK[state] > _STATE_RANK[existing]:
                        quest_states[q_id] = state

            # items[] are recommendations/consumables, not hard gates — excluded (resolution §3)

        # Build condition group
        children: list[ConditionAtom] = []
        for sk in sorted(max_skill):
            lvl, boost = max_skill[sk]
            children.append(ConditionAtom(
                atom_type=AtomType.SKILL_LEVEL,
                ref_node=sk,
                threshold=lvl,
                data={"boostable": boost},
            ))
        for q_id in sorted(quest_states):
            children.append(ConditionAtom(
                atom_type=AtomType.QUEST,
                ref_node=q_id,
                data={"state": quest_states[q_id]},
            ))

        root_gid = _gid(nid, 0)
        groups[root_gid] = ConditionGroup(
            id=root_gid, op=Op.AND, parent=None, children=children,
        )

        sorted_tasks = sorted(tasks, key=lambda t: t["task_number"])
        nodes.append(Node(
            id=nid,
            kind=NodeKind.DIARY,
            name=f"{region_label} {tier.capitalize()}",
            slug=f"{region}-{tier}",
            data={
                "region": region,
                "tier": tier,
                "tasks": [{"n": t["task_number"], "task": t["task"]} for t in sorted_tasks],
                "skipped_quest_reqs": skipped_count,
            },
        ))
        edges.append(Edge(
            id=_eid(nid, 0),
            type=EdgeType.REQUIRES,
            src=nid,
            dst=None,
            cond_group=root_gid,
        ))

    return nodes, edges, groups
