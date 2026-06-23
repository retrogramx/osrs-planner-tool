"""Diary completion goals (diaries Tasks 3 + 9). Mirrors completion_goals.py but
the accumulator is count_satisfied over the 48 diary tier states (member_count
cape).

Two record shapes:
  - BASE cape (goal:achievement-diary-cape): completion gate is count_satisfied
    over the 48 tier ids >= threshold; threshold-gated grant.
  - TRIMMED cape (goal:achievement-diary-cape-t, Task 9): a composite goal whose
    completion `requires` BOTH base capes (the first cross-domain goal link,
    spec §6) via dst-bearing requires edges, plus a `supersedes` edge (trimmed ≻
    untrimmed). Authored with `requires_goals` + `supersedes` keys; it carries no
    count_satisfied gate of its own (the base diary cape it requires already does),
    so its grant is ungated (fires when the goal node — gated by those requires —
    is reached).
"""
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


def _grant_edge(gid_node: str, grant: dict, slot: int, cond_group: int | None) -> Edge:
    dst = access_id(grant["access"]) if grant.get("access") else None
    data = {k: v for k, v in grant.items() if k != "access"}
    if grant.get("access"):
        data["access"] = grant["access"]
    return Edge(id=_eid(gid_node, slot), type=EdgeType.GRANTS, src=gid_node, dst=dst,
                cond_group=cond_group, data=data)


def build_diary_goals(goal_records: list[dict], tier_ids: list[str]):
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}
    for rec in goal_records:
        gid_node = rec["id"]
        thresholds = rec["thresholds"]
        nodes.append(Node(id=gid_node, kind=NodeKind.GOAL, name=rec["name"], slug=slugify(rec["name"]),
                          data={"counter_type": rec["counter_type"], "thresholds": thresholds}))
        slot = 0

        requires_goals = rec.get("requires_goals")
        if requires_goals:
            # TRIMMED cape: completion requires BOTH base capes (cross-domain link).
            for goal_dst in requires_goals:
                edges.append(Edge(id=_eid(gid_node, slot), type=EdgeType.REQUIRES,
                                  src=gid_node, dst=goal_dst, cond_group=None))
                slot += 1
        else:
            # BASE cape: completion gate is count_satisfied over the 48 tier ids.
            req_g = _gid(gid_node, slot)
            groups[req_g] = ConditionGroup(id=req_g, op=Op.AND, parent=None, children=[
                ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=thresholds[-1],
                              data={"set_ref": list(tier_ids)})])
            edges.append(Edge(id=_eid(gid_node, slot), type=EdgeType.REQUIRES,
                              src=gid_node, dst=None, cond_group=req_g))
            slot += 1

        # supersedes (trimmed ≻ untrimmed)
        supersedes = rec.get("supersedes")
        if supersedes:
            edges.append(Edge(id=_eid(gid_node, slot), type=EdgeType.SUPERSEDES,
                              src=gid_node, dst=supersedes, cond_group=None, data={}))
            slot += 1

        # the cape reward grant
        grant = rec.get("grants")
        if grant:
            if requires_goals:
                # composite goal — grant fires when the goal (gated by its requires) is reached.
                edges.append(_grant_edge(gid_node, grant, slot, cond_group=None))
            else:
                # threshold-gated grant (§5.1): count_satisfied >= final threshold.
                grant_g = _gid(gid_node, slot)
                groups[grant_g] = ConditionGroup(id=grant_g, op=Op.AND, parent=None, children=[
                    ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=thresholds[-1],
                                  data={"set_ref": list(tier_ids)})])
                edges.append(_grant_edge(gid_node, grant, slot, cond_group=grant_g))
            slot += 1
    return nodes, edges, groups
