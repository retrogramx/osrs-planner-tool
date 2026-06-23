"""Diary completion goals (diaries Task 3). Mirrors completion_goals.py but the
accumulator is count_satisfied over the 48 diary tier states (member_count cape)."""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, access_id, slugify

_GROUP_BAND = 0xB0000000
_EDGE_BAND = 0xB8000000


def _gid(owner: str, slot: int) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner}#dgoal-group#{slot}")


def _eid(owner: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{owner}#dgoal-edge#{slot}")


def build_diary_goals(goal_records: list[dict], tier_ids: list[str]):
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}
    for rec in goal_records:
        gid_node = rec["id"]
        thresholds = rec["thresholds"]
        nodes.append(Node(id=gid_node, kind=NodeKind.GOAL, name=rec["name"], slug=slugify(rec["name"]),
                          data={"counter_type": rec["counter_type"], "thresholds": thresholds}))
        # completion gate: count_satisfied over the diary tiers >= final threshold
        req_g = _gid(gid_node, 0)
        groups[req_g] = ConditionGroup(id=req_g, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=thresholds[-1],
                          data={"set_ref": list(tier_ids)})])
        edges.append(Edge(id=_eid(gid_node, 0), type=EdgeType.REQUIRES, src=gid_node, dst=None, cond_group=req_g))
        # threshold-gated grant (the cape reward)
        grant = rec.get("grants")
        if grant:
            grant_g = _gid(gid_node, 1)
            groups[grant_g] = ConditionGroup(id=grant_g, op=Op.AND, parent=None, children=[
                ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=thresholds[-1],
                              data={"set_ref": list(tier_ids)})])
            dst = access_id(grant["access"]) if grant.get("access") else None
            data = {k: v for k, v in grant.items() if k != "access"}
            if grant.get("access"):
                data["access"] = grant["access"]
            edges.append(Edge(id=_eid(gid_node, 1), type=EdgeType.GRANTS, src=gid_node, dst=dst,
                              cond_group=grant_g, data=data))
    return nodes, edges, groups
