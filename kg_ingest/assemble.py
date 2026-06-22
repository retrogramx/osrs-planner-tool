"""Assembler: merge per-domain builders into the committed knowledge graph.

Pipeline (spec §4):
    build_quests(records) ┐
    build_supporting(ids) ├─► merge ─► stable ids ─► dedup nodes ─► write kg/*.json
    build_goals()         ┘

DETERMINISTIC IDS (K9 / spec §5,§6.6): builders mint builder-LOCAL ids; the
assembler RE-KEYS every group/edge to a global id derived ONLY from the owning
node id + a stable per-owner local index, so kg/*.json is reproducible (no churn).
    group id = GROUP_OFFSET + (sha1(f"{owner}#g{idx}") mod SPAN)
    edge  id = EDGE_OFFSET  + (sha1(f"{owner}#e{idx}") mod SPAN)
GROUP_OFFSET (4M) and EDGE_OFFSET (6M) are disjoint 2M-wide domains.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from osrs_planner.engine.kg.model import ConditionAtom, ConditionGroup, Edge, Node
from osrs_planner.engine.kg.json_store import (
    atom_to_dict as serialize_atom,
    node_to_dict as serialize_node,
    edge_to_dict as serialize_edge,
    group_to_dict as serialize_group,
)
from kg_ingest.builders.completion_goals import build_completion_goals
from kg_ingest.builders.goals import build_goals
from kg_ingest.builders.quest_rewards import build_quest_rewards
from kg_ingest.builders.quests import build_quests
from kg_ingest.builders.supporting import build_supporting

GROUP_OFFSET = 4_000_000
EDGE_OFFSET = 6_000_000
SPAN = 2_000_000


def _stable_int(key: str, offset: int) -> int:
    return offset + (int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16) % SPAN)


def stable_group_id(owner_id: str, local_index: int) -> int:
    """Deterministic GROUP id for the local_index-th group owned by owner_id."""
    return _stable_int(f"{owner_id}#g{local_index}", GROUP_OFFSET)


def stable_edge_id(owner_id: str, local_index: int) -> int:
    """Deterministic EDGE id for the local_index-th edge owned by owner_id."""
    return _stable_int(f"{owner_id}#e{local_index}", EDGE_OFFSET)


def _walk_group_ids(root_local_id: int, groups: dict[int, ConditionGroup]) -> list[int]:
    """Local group ids reachable from root (root first), stable pre-order. Int
    children are sub-group ids; ConditionAtom children are leaves."""
    order: list[int] = []
    stack = [root_local_id]
    seen: set[int] = set()
    while stack:
        gid = stack.pop(0)
        if gid in seen:
            continue
        seen.add(gid)
        order.append(gid)
        for child in groups[gid].children:
            if isinstance(child, int):
                stack.append(child)
    return order


def rekey(nodes: list[Node], edges: list[Edge],
          groups: dict[int, ConditionGroup]) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    """Re-key every edge and group to a GLOBAL deterministic id derived from the
    owning node id (the edge's src). Nodes pass through unchanged.

    TWO-TIER ID SCHEME: builders mint builder-LOCAL band ids via ids.py (so each
    builder is independently testable with stable ids); rekey re-keys all of them
    into the committed offset scheme (stable_group_id / stable_edge_id). Builder-
    local ids never reach the committed kg/*.json. Re-keyed ids are hash-derived,
    so a collision is theoretically possible — we fail fast on it (a dropped
    group/edge is unrecoverable), mirroring dedup_nodes' raise-on-conflict.
    """
    edge_local_index: dict[str, int] = {}
    local_to_new_group: dict[int, int] = {}

    new_edges: list[Edge] = []
    seen_edge_ids: dict[int, Edge] = {}
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

    new_groups: dict[int, ConditionGroup] = {}
    new_id_to_local: dict[int, int] = {}
    for local_gid, grp in groups.items():
        if local_gid not in local_to_new_group:
            raise ValueError(
                f"group {local_gid} is not reachable from any requires edge (orphan); "
                f"builders must root every group in an edge cond_group")
        new_id = local_to_new_group[local_gid]
        if new_id in new_id_to_local and new_id_to_local[new_id] != local_gid:
            raise ValueError(
                f"group id collision at {new_id}: local groups {new_id_to_local[new_id]} "
                f"and {local_gid} hash to the same global id (unrecoverable; not "
                f"silently droppable)")
        new_id_to_local[new_id] = local_gid
        new_parent = local_to_new_group[grp.parent] if grp.parent is not None else None
        new_children: list[int | ConditionAtom] = []
        for child in grp.children:
            new_children.append(local_to_new_group[child] if isinstance(child, int) else child)
        new_groups[new_id] = ConditionGroup(id=new_id, op=grp.op, parent=new_parent,
                                            children=new_children)
    return list(nodes), new_edges, new_groups


def dedup_nodes(nodes: list[Node]) -> list[Node]:
    """Collapse nodes sharing an .id (first-wins, insertion order preserved). A later
    node with the same id but DIFFERENT content is a builder bug -> raise."""
    seen: dict[str, Node] = {}
    order: list[str] = []
    for n in nodes:
        if n.id in seen:
            if seen[n.id] != n:
                raise ValueError(
                    f"conflicting node definitions for {n.id!r}: {seen[n.id]!r} vs {n!r}")
            continue
        seen[n.id] = n
        order.append(n.id)
    return [seen[i] for i in order]


# repo-root /kg dir. __file__ is kg_ingest/assemble.py -> parents[1] is the repo root.
OUT_DIR = Path(__file__).resolve().parents[1] / "kg"
QUESTS_PATH = Path(__file__).resolve().parents[1] / "data" / "quests.json"


def _collect_referenced_ids(edges: list[Edge], groups: dict[int, ConditionGroup]) -> set[str]:
    """Every ref_node mentioned by an atom, plus every edge src/non-null dst — the
    set of node ids supporting nodes must cover (Task 4)."""
    ids: set[str] = set()
    for g in groups.values():
        for child in g.children:
            if isinstance(child, ConditionAtom) and child.ref_node is not None:
                ids.add(child.ref_node)
    for e in edges:
        ids.add(e.src)
        if e.dst is not None:
            ids.add(e.dst)
    return ids


def _load_quest_records() -> list[dict]:
    return json.loads(QUESTS_PATH.read_text())["records"]


QUEST_REWARDS_PATH = Path(__file__).resolve().parents[1] / "data" / "quest_rewards.json"


def _load_reward_records() -> list[dict]:
    if not QUEST_REWARDS_PATH.exists():
        return []
    return json.loads(QUEST_REWARDS_PATH.read_text())["records"]


COMPLETION_GOALS_PATH = Path(__file__).resolve().parents[1] / "data" / "completion_goals.json"


def _load_completion_goal_records() -> list[dict]:
    if not COMPLETION_GOALS_PATH.exists():
        return []
    return json.loads(COMPLETION_GOALS_PATH.read_text())["records"]


def _write_json(path: Path, payload: list) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n")


def assemble() -> None:
    """Build the full v1 KG from data/*.json and write kg/*.json (K10). Deterministic."""
    # 1) run the builders (each returns builder-LOCAL group/edge ids).
    q_nodes, q_edges, q_groups, _diaries = build_quests(_load_quest_records())
    qr_nodes, qr_edges, qr_groups = build_quest_rewards(_load_reward_records())
    g_nodes, g_edges, g_groups = build_goals()
    cg_nodes, cg_edges, cg_groups = build_completion_goals(_load_completion_goal_records())

    # 2) re-key. Quests + quest-rewards share quest:* owners (requires + grants from the
    #    same quest), so they MUST be re-keyed in ONE call to get a continuous per-owner
    #    edge/group index (Task 3). Goals and completion-goals own disjoint ids ->
    #    re-keyed independently.
    qr_combined_nodes = q_nodes + qr_nodes
    qr_combined_edges = q_edges + qr_edges          # requires first, then grants (stable order)
    qr_combined_groups = {**q_groups, **qr_groups}
    q_nodes, q_edges, q_groups = rekey(qr_combined_nodes, qr_combined_edges, qr_combined_groups)
    g_nodes, g_edges, g_groups = rekey(g_nodes, g_edges, g_groups)
    cg_nodes, cg_edges, cg_groups = rekey(cg_nodes, cg_edges, cg_groups)

    edges = q_edges + g_edges + cg_edges
    groups = {**q_groups, **g_groups, **cg_groups}

    # 3) supporting nodes cover every ref_node / edge endpoint referenced above,
    #    minus the quest + goal nodes the builders already produced.
    #    build_supporting only handles leaf domains (skill/item/access/minigame/
    #    gear_loadout/npc/diary); quest: ids that aren't owned are known-missing
    #    quests (flagged by the validator, Task 8) — do not send them to build_supporting.
    #    goal: is not in _LEAF_DOMAINS, so progress_towards dst=goal:* resolves to
    #    the node built by build_completion_goals (not sent to build_supporting).
    _LEAF_DOMAINS = frozenset(
        {"skill", "item", "access", "minigame", "gear_loadout", "npc", "diary"}
    )
    owned_ids = {n.id for n in q_nodes} | {n.id for n in g_nodes} | {n.id for n in cg_nodes}
    referenced = {
        r for r in _collect_referenced_ids(edges, groups)
        if r.split(":")[0] in _LEAF_DOMAINS
    } - owned_ids
    s_nodes = build_supporting(referenced)

    # 4) dedup nodes by id (skills/items shared across quests + goals collapse).
    nodes = dedup_nodes(q_nodes + g_nodes + cg_nodes + s_nodes)

    # 5) serialize, sorted deterministically.
    nodes_out = [serialize_node(n) for n in sorted(nodes, key=lambda n: n.id)]
    edges_out = [serialize_edge(e) for e in sorted(edges, key=lambda e: e.id)]
    groups_out = [serialize_group(g) for g in sorted(groups.values(), key=lambda g: g.id)]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_DIR / "nodes.json", nodes_out)
    _write_json(OUT_DIR / "edges.json", edges_out)
    _write_json(OUT_DIR / "condition_groups.json", groups_out)


if __name__ == "__main__":  # pragma: no cover - manual rebuild entrypoint
    assemble()
    print(f"wrote {OUT_DIR}/nodes.json, edges.json, condition_groups.json")
