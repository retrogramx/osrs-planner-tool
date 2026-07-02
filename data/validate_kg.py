#!/usr/bin/env python3
"""KG invariant + completeness guard (spec §7).

Mirrors data/validate_iron_gate.py: a committed, deterministic check that exits
non-zero on any violation (gates CI / pre-merge). Loads the committed kg/*.json
via JsonKGStore and asserts the six §7 invariant families (see module body).

Usage:  ./venv/bin/python data/validate_kg.py
"""
from __future__ import annotations

import enum
import json
import os
import sys
from collections import namedtuple

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
SCHEMA_PATH = os.path.join(KG_DIR, "schema.json")

_VALID_ATOM_TYPES = {a.value for a in AtomType}
_VALID_NODE_KINDS = {k.value for k in NodeKind}
_VALID_OPS = {o.value for o in Op}


# ---------------------------------------------------------------------------
# Schema-driven domain/range invariant + severity tiers (v2 ontology, spec §8)
#
# kg/schema.json is the LOCKED v2 ontology-as-data (Going Meta principle 1): a
# single source of truth that drives the builders, the LLM-extraction prompt, and
# the generic check below. The check enforces a CLOSED vocabulary (every node
# kind / edge type / atom type / op used in the graph must be declared) and the
# domain/range of every edge, grading each finding by severity so that partial /
# in-migration data warns or informs rather than blocking (decision 9 / §8).
# ---------------------------------------------------------------------------

class Severity(str, enum.Enum):
    """Schema-finding severity tiers (spec §8). Only VIOLATION affects exit code."""
    VIOLATION = "VIOLATION"  # hard failure: undeclared kind/edge/atom/op or domain/range breach
    WARNING = "WARNING"      # tracked, non-fatal (e.g. disclosed known-gap / mis-filed record)
    INFO = "INFO"            # informational, non-fatal (migration/coverage signal: legacy usage)


# One severity-graded result of the schema-driven check: `severity` is a Severity,
# `code` a short machine tag (vocab|domain|range|dst|legacy), `message` human text.
# A functional namedtuple (not a dataclass) so the module exec's cleanly under the
# importlib-from-file loading the tests use (it is not registered in sys.modules).
Finding = namedtuple("Finding", ["severity", "code", "message"])


def load_schema(path: str = SCHEMA_PATH) -> dict:
    """Load kg/schema.json (the locked v2 ontology-as-data)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _kind_str(node) -> str | None:
    """node.kind as a plain string (enum .value or raw str), or None for a missing node."""
    if node is None:
        return None
    return node.kind.value if hasattr(node.kind, "value") else node.kind


def check_schema(store: KGStore, schema: dict) -> list[Finding]:
    """Generic, schema-driven domain/range + closed-vocabulary invariant (spec §8).

    Returns severity-graded Findings ([] of VIOLATION == schema-valid):
      - VIOLATION: a node kind / edge type / atom type / op not declared in the
        schema, or an edge whose src.kind ∉ domain, dst.kind ∉ range, or a
        required dst missing.
      - INFO: usage of a *legacy* (v1) node kind or atom type that is tolerated
        for byte-stable, link-don't-merge migration (aggregated, one line each).

    Pure and store/schema-injectable so it is unit-testable in isolation.
    """
    findings: list[Finding] = []

    node_kinds = schema["node_kinds"]
    legacy_node_kinds = schema["legacy_node_kinds"]
    edge_kinds = schema["edge_kinds"]
    legacy_edge_kinds = schema.get("legacy_edge_kinds", {})
    atom_types = schema["atom_types"]
    legacy_atom_types = schema["legacy_atom_types"]
    valid_ops = set(schema["ops"])
    declared_node_kinds = set(node_kinds) | set(legacy_node_kinds)
    declared_atom_types = set(atom_types) | set(legacy_atom_types)

    def kind_of(nid: str | None) -> str | None:
        return _kind_str(store.nodes.get(nid) if nid is not None else None)

    # --- node-kind vocabulary (closed) + legacy usage as aggregated INFO ---
    legacy_kind_counts: dict[str, int] = {}
    for nid, node in store.nodes.items():
        k = _kind_str(node)
        if k not in declared_node_kinds:
            findings.append(Finding(Severity.VIOLATION, "vocab",
                f"node {nid!r} has kind {k!r} not declared in schema "
                f"(node_kinds / legacy_node_kinds)"))
        elif k in legacy_node_kinds:
            legacy_kind_counts[k] = legacy_kind_counts.get(k, 0) + 1
    for k in sorted(legacy_kind_counts):
        succ = legacy_node_kinds[k].get("successor", "?")
        findings.append(Finding(Severity.INFO, "legacy",
            f"{legacy_kind_counts[k]} node(s) on legacy kind {k!r} "
            f"(v2 successor: {succ}) — pending migration"))

    # --- edge-type vocabulary (closed) + domain/range/dst invariant ---
    legacy_edge_counts: dict[str, int] = {}
    for e in store.edges:
        t = e.type.value if hasattr(e.type, "value") else e.type
        spec = edge_kinds.get(t)
        if spec is None:
            if t in legacy_edge_kinds:
                legacy_edge_counts[t] = legacy_edge_counts.get(t, 0) + 1
            else:
                findings.append(Finding(Severity.VIOLATION, "vocab",
                    f"edge {e.id} has type {t!r} not declared in schema "
                    f"(edge_kinds / legacy_edge_kinds)"))
            continue
        src_kind = kind_of(e.src)
        domain = spec["domain"]
        # A missing src node (kind None) is referential integrity's job (check_kg
        # reports it as [ref]); don't ALSO mislabel it a domain breach here.
        if src_kind is not None and domain != "*" and src_kind not in domain:
            findings.append(Finding(Severity.VIOLATION, "domain",
                f"edge {e.id} ({t}) src {e.src!r} kind {src_kind!r} not in domain {domain}"))
        dst_policy = spec.get("dst")
        if e.dst is None:
            if dst_policy == "required":
                findings.append(Finding(Severity.VIOLATION, "dst",
                    f"edge {e.id} ({t}) has dst=None but schema requires a dst"))
        elif dst_policy == "forbidden":
            findings.append(Finding(Severity.VIOLATION, "dst",
                f"edge {e.id} ({t}) carries dst {e.dst!r} but schema forbids a dst"))
        else:
            dst_kind = kind_of(e.dst)
            rng = spec["range"]
            if dst_kind is not None and rng != "*" and dst_kind not in rng:
                findings.append(Finding(Severity.VIOLATION, "range",
                    f"edge {e.id} ({t}) dst {e.dst!r} kind {dst_kind!r} not in range {rng}"))
    for t in sorted(legacy_edge_counts):
        succ = legacy_edge_kinds[t].get("successor", "?")
        findings.append(Finding(Severity.INFO, "legacy",
            f"{legacy_edge_counts[t]} edge(s) of legacy type {t!r} "
            f"(v2 successor: {succ}) — pending migration"))

    # --- op + atom-type vocabulary (closed) + legacy atom usage as INFO ---
    legacy_atom_counts: dict[str, int] = {}
    for gid, group in store.groups.items():
        op = group.op.value if hasattr(group.op, "value") else group.op
        if op not in valid_ops:
            findings.append(Finding(Severity.VIOLATION, "vocab",
                f"group {gid} has op {op!r} not declared in schema.ops"))
        for child in group.children:
            if isinstance(child, ConditionAtom):
                a = child.atom_type.value if hasattr(child.atom_type, "value") else child.atom_type
                if a not in declared_atom_types:
                    findings.append(Finding(Severity.VIOLATION, "vocab",
                        f"group {gid} atom has atom_type {a!r} not declared in schema "
                        f"(atom_types / legacy_atom_types)"))
                elif a in legacy_atom_types:
                    legacy_atom_counts[a] = legacy_atom_counts.get(a, 0) + 1
    for a in sorted(legacy_atom_counts):
        succ = legacy_atom_types[a].get("successor", "?")
        findings.append(Finding(Severity.INFO, "legacy",
            f"{legacy_atom_counts[a]} atom(s) of legacy type {a!r} "
            f"(v2 successor: {succ}) — pending migration"))

    return findings


def _unreachable_place_ids(store: KGStore) -> list[str]:
    """Return place: node ids that cannot reach place:gielinor via located_in (cycle/dangling).

    Mirrors verify_world._unreachable_places but operates on the committed store so the
    gate covers ALL place builders (build_world, build_map, future builders), not just the
    standalone build_world re-derive. Called from check_kg as a structural VIOLATION.
    """
    place_ids = [nid for nid in store.nodes if nid.startswith("place:")]
    if not place_ids:
        return []
    par: dict[str, str | None] = {}
    for e in store.edges:
        t = e.type.value if hasattr(e.type, "value") else e.type
        if t == "located_in":
            par[e.src] = e.dst
    out = []
    for pid in place_ids:
        if pid == "place:gielinor":
            continue
        seen: set[str] = set()
        cur: str | None = pid
        while cur != "place:gielinor":
            if cur is None or cur in seen:
                out.append(pid)
                break
            seen.add(cur)
            cur = par.get(cur)
    return out


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

    # --- 1b. located_in acyclicity gate: every place: node must reach place:gielinor ---
    # Covers ALL committed place builders (build_world + build_map + future).
    # verify_world.py gates the standalone build_world re-derive; this gates the committed graph.
    for pid in _unreachable_place_ids(store):
        errors.append(f"[located_in] place node {pid!r} cannot reach place:gielinor "
                      f"(cycle or dangling located_in chain)")

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

    # --- Diary-domain invariants (achievement-diaries brick) ---
    def _kind_of(nid: str | None) -> str | None:
        n = store.nodes.get(nid) if nid is not None else None
        if n is None:
            return None
        return n.kind.value if hasattr(n.kind, "value") else n.kind

    _CONTENT_KINDS = {NodeKind.SKILL.value, NodeKind.ACTIVITY.value, NodeKind.MONSTER.value,
                      NodeKind.REGION.value, NodeKind.ITEM.value}
    _EFFECT_KINDS = {"stat_multiplier", "rate_multiplier", "capacity_change", "fee_waiver",
                     "behavior_toggle", "recurring_resource", "access"}
    for e in store.edges:
        if e.type is EdgeType.SUPERSEDES:
            # the upgrade/cross-cape ladder: item ≻ item, or goal ≻ goal.
            for end, label in ((e.src, "src"), (e.dst, "dst")):
                k = _kind_of(end)
                if k not in (NodeKind.ITEM.value, NodeKind.GOAL.value):
                    errors.append(f"[diary] supersedes edge {e.id} {label} {end!r} is kind "
                                  f"{k!r} (must be item or goal)")
        elif e.type is EdgeType.EFFECT and e.dst is not None:
            # The diary effect→content contract: a dst-bearing effect targets a
            # content node and carries an enum effect_kind. (quest-brick effects
            # leave dst=None and are exempt.)
            k = _kind_of(e.dst)
            if k not in _CONTENT_KINDS:
                errors.append(f"[diary] effect edge {e.id} dst {e.dst!r} is kind {k!r} "
                              f"(must be a content node: {sorted(_CONTENT_KINDS)})")
            ek = (e.data or {}).get("effect_kind")
            if ek not in _EFFECT_KINDS:
                errors.append(f"[diary] effect edge {e.id} has invalid/missing "
                              f"data.effect_kind {ek!r}")

    # Every diary tier node carries its region + tier.
    for nid, node in store.nodes.items():
        kind = node.kind.value if hasattr(node.kind, "value") else node.kind
        if kind == NodeKind.DIARY.value:
            data = node.data or {}
            if not data.get("region") or not data.get("tier"):
                errors.append(f"[diary] tier node {nid} missing data.region/data.tier")

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


def check_recipe_id_registry(store: KGStore) -> list[str]:
    """Recipe-id stability invariant (spec 2026-07-01 §6): every committed roster
    recipe id is sourced from data/recipe_slug_registry.json, the registry is a
    bijection on slugs, and no committed recipe slug is duplicated. Charge recipes
    (data.charge_capacity) are excluded — they have hand-authored stable slugs."""
    errors: list[str] = []
    reg_path = os.path.join(ROOT, "data", "recipe_slug_registry.json")
    if not os.path.exists(reg_path):
        return ["[recipe-id] data/recipe_slug_registry.json is missing"]
    with open(reg_path, encoding="utf-8") as f:
        reg = json.load(f).get("recipes", {})

    slug_of: dict[str, str] = {}                      # slug -> identity hash (bijection check)
    for h, entry in reg.items():
        for s in entry.get("slugs", []):
            if s in slug_of:
                errors.append(f"[recipe-id] slug {s!r} registered under two identities "
                              f"{slug_of[s]} and {h}")
            slug_of[s] = h

    committed: set[str] = set()
    for n in store.nodes.values():
        nid = n.id if hasattr(n, "id") else None
        if not (isinstance(nid, str) and nid.startswith("recipe:")):
            continue
        slug = n.slug
        if slug in committed:
            errors.append(f"[recipe-id] duplicate committed recipe slug {slug!r}")
        committed.add(slug)
        if "charge_capacity" in (n.data or {}):
            continue                                  # charge recipe -> not registry-backed
        if slug not in slug_of:
            errors.append(f"[recipe-id] committed recipe slug {slug!r} is not in the registry "
                          f"(id not content-derived — run data/update_recipe_registry.py)")
    return errors


def collect_findings(store: KGStore, quests_data: dict, schema: dict | None,
                     raw_node_dicts: list[dict] | None = None,
                     raw_edge_dicts: list[dict] | None = None,
                     raw_group_dicts: list[dict] | None = None) -> list[Finding]:
    """Unify every check into one severity-graded Finding list (spec §8).

    The legacy structural/completeness checks (check_kg) are VIOLATIONs; the
    disclosed-gap notices (check_kg_warnings) are WARNINGs; the schema-driven
    domain/range + closed-vocabulary check contributes its own severities. A
    missing/invalid schema is itself a VIOLATION (the schema is required from
    build step 1 on)."""
    findings: list[Finding] = []
    for msg in check_kg(store, quests_data, raw_node_dicts=raw_node_dicts,
                        raw_edge_dicts=raw_edge_dicts, raw_group_dicts=raw_group_dicts):
        findings.append(Finding(Severity.VIOLATION, "invariant", msg))
    for msg in check_kg_warnings(store, quests_data):
        findings.append(Finding(Severity.WARNING, "known-gap", msg))
    for msg in check_recipe_id_registry(store):
        findings.append(Finding(Severity.VIOLATION, "recipe-id", msg))
    if schema is None:
        findings.append(Finding(Severity.VIOLATION, "schema",
            f"kg/schema.json could not be loaded (required from build step 1)"))
    else:
        findings.extend(check_schema(store, schema))
    return findings


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
    try:
        schema = load_schema()
    except (OSError, ValueError) as exc:
        print(f"KG VALIDATION — schema load failed: {exc}")
        schema = None

    findings = collect_findings(store, quests_data, schema, raw_node_dicts=raw_node_dicts,
                                raw_edge_dicts=raw_edge_dicts, raw_group_dicts=raw_group_dicts)
    violations = [f for f in findings if f.severity is Severity.VIOLATION]
    warnings = [f for f in findings if f.severity is Severity.WARNING]
    infos = [f for f in findings if f.severity is Severity.INFO]
    accessed = quests_data.get("_provenance", {}).get("accessed", "?")

    # Some findings (the legacy check_kg/check_kg_warnings strings) are already
    # self-tagged with a leading "[...]"; only prefix [code] when they are not.
    def _fmt(f: Finding) -> str:
        return f.message if f.message.startswith("[") else f"[{f.code}] {f.message}"

    for tier, items in (("INFO", infos), ("WARNING", warnings)):
        if items:
            print(f"KG VALIDATION {tier} — {len(items)} {tier.lower()} notice(s):")
            for f in items:
                print("  ", _fmt(f))
    if violations:
        print(f"KG VALIDATION FAILED — {len(violations)} violation(s):")
        for f in violations[:50]:
            print("  -", _fmt(f))
        if len(violations) > 50:
            print(f"  ... and {len(violations) - 50} more")
        return 1
    n_quests = sum(1 for n in store.nodes.values()
                   if (n.kind.value if hasattr(n.kind, "value") else n.kind) == "quest")
    print("KG VALIDATION PASSED — all graph invariants + schema + completeness hold.")
    print(f"  nodes: {len(store.nodes)}  edges: {len(store.edges)}  groups: {len(store.groups)}")
    print(f"  quest nodes: {n_quests}")
    print(f"  schema: v{schema['schema_version'] if schema else '?'} "
          f"({len(schema['node_kinds']) if schema else 0} node kinds, "
          f"{len(schema['edge_kinds']) if schema else 0} edge kinds)")
    print(f"  notices: {len(warnings)} warning(s), {len(infos)} info (migration/coverage)")
    print(f"  quests source accessed: {accessed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
