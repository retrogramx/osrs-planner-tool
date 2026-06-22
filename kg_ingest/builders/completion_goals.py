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
