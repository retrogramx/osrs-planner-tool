#!/usr/bin/env python3
"""KG invariant + completeness guard (spec §7).

Mirrors data/validate_iron_gate.py: a committed, deterministic check that exits
non-zero on any violation (gates CI / pre-merge). Loads the committed kg/*.json
via JsonKGStore and asserts the six §7 invariant families (see module body).

Usage:  ./venv/bin/python data/validate_kg.py
"""
from __future__ import annotations

import json
import os
import sys

# Ensure the repo root (which contains kg_ingest/ and src/) is importable when
# this script is run directly (e.g. ./venv/bin/python data/validate_kg.py).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
_SRC = os.path.join(ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from osrs_planner.engine.kg.model import AtomType, ConditionAtom, EdgeType, NodeKind, Op
from osrs_planner.engine.kg.store import KGStore
from kg_ingest.ids import slugify
KG_DIR = os.path.join(ROOT, "kg")
QUESTS_PATH = os.path.join(ROOT, "data", "quests.json")

_VALID_ATOM_TYPES = {a.value for a in AtomType}
_VALID_NODE_KINDS = {k.value for k in NodeKind}
_VALID_OPS = {o.value for o in Op}


def check_kg_warnings(store: KGStore, quests_data: dict) -> list[str]:
    """Return non-fatal warning strings (printed but do not affect exit code).

    Covers:
      - [known-gap]: dangling quest:* ref_node whose slug appears in
        _provenance.completeness.known_missing (amendment A).
      - [diary]: records in quests_data with node_type=='diary' that are
        mis-filed in quests.json (amendment B / K2).
    """
    warnings: list[str] = []
    node_ids = set(store.nodes.keys())
    completeness = quests_data.get("_provenance", {}).get("completeness", {})
    known_missing_names = completeness.get("known_missing", [])
    known_missing_slugs = {slugify(n) for n in known_missing_names}

    # Amendment A: scan condition group atoms for dangling quest:* refs that are
    # explicitly in known_missing — demote to non-fatal [known-gap] warning.
    for gid, group in store.groups.items():
        for child in group.children:
            if isinstance(child, ConditionAtom):
                ref = child.ref_node
                if ref is not None and ref not in node_ids and ref.startswith("quest:"):
                    quest_slug = ref[len("quest:"):]
                    if quest_slug in known_missing_slugs:
                        warnings.append(
                            f"[known-gap] group {gid} atom ref_node {ref!r} is a known-missing "
                            f"quest (disclosed in _provenance.completeness.known_missing) — "
                            f"node absent from KG, dependency unenforced"
                        )

    # Amendment B: diary records mis-filed in quests.json (K2).
    diary_records = [r["name"] for r in quests_data.get("records", [])
                     if r.get("node_type") == "diary"]
    if diary_records:
        warnings.append(
            f"[diary] {len(diary_records)} diary record(s) found in quests.json "
            f"(mis-filed; diaries belong in achievement_diaries): {diary_records}"
        )

    return warnings


def check_kg(store: KGStore, quests_data: dict,
             raw_node_dicts: list[dict] | None = None,
             raw_edge_dicts: list[dict] | None = None,
             raw_group_dicts: list[dict] | None = None) -> list[str]:
    """Return a list of violation strings ([] == valid). Pure; store-injectable.

    raw_node_dicts (optional): the RAW serialized nodes.json list BEFORE JsonKGStore
    collapses duplicate ids into a dict — passed by main() so the duplicate-node-id
    check (§7.4 / M4) can see duplicates the dict would otherwise hide.

    raw_edge_dicts (optional): the RAW serialized edges.json list — passed by main()
    for global edge integer-id uniqueness check (amendment C).

    raw_group_dicts (optional): the RAW serialized condition_groups.json list — passed
    by main() for global group integer-id uniqueness check (amendment C).
    """
    errors: list[str] = []
    node_ids = set(store.nodes.keys())
    group_ids = set(store.groups.keys())

    # Derive known-missing slugs for amendment A (dangling quest ref tolerance).
    completeness = quests_data.get("_provenance", {}).get("completeness", {})
    known_missing_names = completeness.get("known_missing", [])
    known_missing_slugs = {slugify(n) for n in known_missing_names}

    # --- 1. Acyclic (I1) ---
    # Guard: find_cycles() internally walks condition groups; if the graph has dangling
    # group refs the walk raises KeyError. Catch it so referential-integrity checks below
    # can report the actual broken ref rather than a confusing crash.
    try:
        for c in store.find_cycles()[:10]:
            errors.append(f"[acyclic] requires-graph cycle: {c}")
    except (KeyError, ValueError) as exc:
        errors.append(f"[acyclic] find_cycles() raised {type(exc).__name__}: {exc} "
                      f"(likely a dangling group/node ref — see [ref] errors below)")

    # --- 3. Vocabulary: node kinds ---
    for nid, node in store.nodes.items():
        kind = node.kind.value if hasattr(node.kind, "value") else node.kind
        if kind not in _VALID_NODE_KINDS:
            errors.append(f"[vocab] node {nid} has invalid kind {kind!r}")

    # --- 4 (B3 / §7.4): every gear_loadout:* node has EXACTLY ONE dst=None
    #     requires edge (its composition), so composition_of is unambiguous. ---
    for nid, node in store.nodes.items():
        kind = node.kind.value if hasattr(node.kind, "value") else node.kind
        if kind == NodeKind.GEAR_LOADOUT.value:
            comp_edges = [e for e in store.edges
                          if e.type is EdgeType.REQUIRES and e.src == nid
                          and e.dst is None and e.cond_group is not None]
            if len(comp_edges) != 1:
                errors.append(f"[loadout] gear_loadout node {nid} has {len(comp_edges)} "
                              f"dst=None requires (composition) edges (must be exactly 1)")

    # --- 4 (M4 / §7.4): no duplicate node ids in the RAW serialized list. ---
    if raw_node_dicts is not None:
        seen_ids: set[str] = set()
        dup_ids: set[str] = set()
        for d in raw_node_dicts:
            rid = d.get("id")
            if rid in seen_ids:
                dup_ids.add(rid)
            seen_ids.add(rid)
        for rid in sorted(dup_ids):
            errors.append(f"[dup] duplicate node id {rid!r} in raw kg/nodes.json list")

    # --- Amendment C: global edge integer-id uniqueness ---
    if raw_edge_dicts is not None:
        seen_eids: set[int] = set()
        dup_eids: set[int] = set()
        for d in raw_edge_dicts:
            eid = d.get("id")
            if eid in seen_eids:
                dup_eids.add(eid)
            seen_eids.add(eid)
        for eid in sorted(dup_eids):
            errors.append(f"[dup] duplicate edge id {eid!r} in raw kg/edges.json list")

    # --- Amendment C: global group integer-id uniqueness ---
    if raw_group_dicts is not None:
        seen_gids: set[int] = set()
        dup_gids: set[int] = set()
        for d in raw_group_dicts:
            gid = d.get("id")
            if gid in seen_gids:
                dup_gids.add(gid)
            seen_gids.add(gid)
        for gid in sorted(dup_gids):
            errors.append(f"[dup] duplicate group id {gid!r} in raw kg/condition_groups.json list")

    referenced_groups: set[int] = set()

    # --- 2. Referential integrity: edges ---
    for e in store.edges:
        if e.src not in node_ids:
            errors.append(f"[ref] edge {e.id} src {e.src!r} resolves to no node")
        if e.dst is not None and e.dst not in node_ids:
            errors.append(f"[ref] edge {e.id} dst {e.dst!r} resolves to no node")
        if e.cond_group is not None:
            if e.cond_group not in group_ids:
                errors.append(f"[ref] edge {e.id} cond_group {e.cond_group} resolves to no group")
            else:
                referenced_groups.add(e.cond_group)

    # --- Reward-edge + goal-node invariants (quest-foundation) ---
    goal_ids = {nid for nid, n in store.nodes.items()
                if (n.kind.value if hasattr(n.kind, "value") else n.kind) == NodeKind.GOAL.value}
    for e in store.edges:
        if e.type is EdgeType.PROGRESS_TOWARDS:
            w = (e.data or {}).get("weight")
            if not isinstance(w, int) or w <= 0:
                errors.append(f"[reward] progress_towards edge {e.id} has non-positive/missing "
                              f"data.weight {w!r}")
            if e.dst is None:
                errors.append(f"[reward] progress_towards edge {e.id} has no dst "
                              f"(progress_towards must target a goal node)")
            elif e.dst not in goal_ids:
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

    # --- 2 + 3: walk groups (atom ref_node, sub-group children, ops) ---
    for gid, group in store.groups.items():
        op = group.op.value if hasattr(group.op, "value") else group.op
        if op not in _VALID_OPS:
            errors.append(f"[vocab] group {gid} has invalid op {op!r}")
        if op == Op.NOT.value and len(group.children) != 1:
            errors.append(f"[vocab] NOT group {gid} has {len(group.children)} children (must be exactly 1)")
        for child in group.children:
            if isinstance(child, ConditionAtom):
                at = child.atom_type.value if hasattr(child.atom_type, "value") else child.atom_type
                if at not in _VALID_ATOM_TYPES:
                    errors.append(f"[vocab] group {gid} atom has invalid atom_type {at!r}")
                if child.ref_node is not None and child.ref_node not in node_ids:
                    # Amendment A: dangling quest:* refs in known_missing → non-fatal (handled
                    # by check_kg_warnings); any other dangling ref stays FATAL.
                    ref = child.ref_node
                    is_known_gap = (
                        ref.startswith("quest:")
                        and ref[len("quest:"):] in known_missing_slugs
                    )
                    if not is_known_gap:
                        errors.append(
                            f"[ref] group {gid} atom ref_node {ref!r} resolves to no node"
                        )
            else:
                sub = int(child)
                if sub not in group_ids:
                    errors.append(f"[ref] group {gid} sub-group child {sub} resolves to no group")
                else:
                    referenced_groups.add(sub)

    # --- 4. No orphan groups ---
    for gid in group_ids:
        if gid not in referenced_groups:
            errors.append(f"[orphan] group {gid} is unreferenced by any edge or parent group")

    # --- 6. Completeness / freshness ---
    universe = completeness.get("universe_count")
    source_quest_names = [r["name"] for r in quests_data.get("records", [])
                          if r.get("node_type") in ("quest", "miniquest")]
    genuinely_missing = [name for name in source_quest_names
                         if name not in known_missing_names
                         and f"quest:{slugify(name)}" not in node_ids]
    if genuinely_missing:
        errors.append(f"[completeness] {len(genuinely_missing)} source quest(s) missing from KG "
                      f"(not in known_missing): {genuinely_missing[:20]}")
    if universe is not None:
        records_count = len(quests_data.get("records", []))
        if records_count != universe:
            errors.append(f"[completeness] source record_count {records_count} != "
                          f"_provenance universe_count {universe} — data drift")
    return errors


def main() -> int:
    # --- 5. Loadability ---
    try:
        from osrs_planner.engine.kg.json_store import JsonKGStore
        store = JsonKGStore.from_dir(KG_DIR)
    except Exception as exc:
        print(f"KG VALIDATION FAILED — JsonKGStore.from_dir({KG_DIR!r}) raised: {exc}")
        return 1
    with open(QUESTS_PATH) as f:
        quests_data = json.load(f)
    # Read the RAW list files (pre-dedup) for duplicate-id checks (M4, amendment C).
    with open(os.path.join(KG_DIR, "nodes.json"), encoding="utf-8") as f:
        raw_node_dicts = json.load(f)
    with open(os.path.join(KG_DIR, "edges.json"), encoding="utf-8") as f:
        raw_edge_dicts = json.load(f)
    with open(os.path.join(KG_DIR, "condition_groups.json"), encoding="utf-8") as f:
        raw_group_dicts = json.load(f)
    errors = check_kg(store, quests_data, raw_node_dicts=raw_node_dicts,
                      raw_edge_dicts=raw_edge_dicts, raw_group_dicts=raw_group_dicts)
    warnings = check_kg_warnings(store, quests_data)
    accessed = quests_data.get("_provenance", {}).get("accessed", "?")
    if warnings:
        print(f"KG VALIDATION WARNINGS — {len(warnings)} non-fatal notice(s):")
        for w in warnings:
            print("  !", w)
    if errors:
        print(f"KG VALIDATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1
    n_quests = sum(1 for n in store.nodes.values()
                   if (n.kind.value if hasattr(n.kind, "value") else n.kind) == "quest")
    print("KG VALIDATION PASSED — all graph invariants + completeness hold.")
    print(f"  nodes: {len(store.nodes)}  edges: {len(store.edges)}  groups: {len(store.groups)}")
    print(f"  quest nodes: {n_quests}")
    print(f"  quests source accessed: {accessed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
