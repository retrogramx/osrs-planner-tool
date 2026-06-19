"""Quest-domain builder (K2,K3,K4,K6,K9; spec §6.1,§6.3,§6.5,§6.6).

build_quests(records) -> (nodes, edges, groups, diary_records)
- node_type 'quest'|'miniquest' -> NodeKind.QUEST gate node (miniquests carry
  data['miniquest']=True). RFD subquests are plain records: each its own node +
  reqs; the parent's prereqs point at subquests -> transitive (K2).
- node_type 'diary' records -> returned as diary_records (validator flags), not modeled.
- each quest/miniquest gets ONE requires edge (dst=None) whose cond_group is an AND
  of a quest atom per prereq (state from stage, default 'completed') (K3) + a
  skill_level atom per skill_req (threshold=level, data.boostable) (K3,K6);
  ironman skill_reqs wrapped OR(account_type==main, req) (K4); all non-mains (ironman-family + UIM) see the req.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import slugify, quest_id, skill_id, group_id, edge_id

_DEFAULT_STAGE = "completed"
_MAIN_FAMILY = "main"  # K4/K5: OR wrapper keys on the 'main' family — all non-mains (ironman-family + UIM) fail it


def build_quests(
    records: list[dict],
) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup], list[dict]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}
    diary_records: list[dict] = []

    for rec in records:
        node_type = rec["node_type"]
        if node_type == "diary":
            diary_records.append(rec)
            continue
        if node_type not in ("quest", "miniquest"):
            raise ValueError(
                f"build_quests: unexpected node_type {node_type!r} for {rec['name']!r}")

        name = rec["name"]
        nid = quest_id(name)
        data: dict = {}
        if node_type == "miniquest":
            data["miniquest"] = True
        nodes.append(Node(id=nid, kind=NodeKind.QUEST, name=name, slug=slugify(name), data=data))

        # --- the requires edge's root AND group (sub_index 0) ---
        root_gid = group_id(nid, 0)
        children: list = []

        # one quest atom per prereq (K3): state from stage, default 'completed'.
        for prereq in rec["prereqs"]:
            stage = prereq.get("stage") or _DEFAULT_STAGE
            children.append(ConditionAtom(
                atom_type=AtomType.QUEST, ref_node=quest_id(prereq["quest"]),
                data={"state": stage}))

        # one skill_level atom per skill_req (K3,K6). ironman:true reqs (K4) are
        # wrapped as a plain 2-child OR(account_type=="main", req); each wrapper
        # consumes ONE deterministic sub-group id (the OR group), allocated from a
        # per-node counter so multiple ironman reqs on one quest never collide.
        # No NOT group is used — mains satisfy account_type=="main" directly;
        # all non-mains (ironman-family + UIM) fail it and reduce to the real req.
        sub_index = 1  # 0 is the root AND group
        for skill_req in rec["skill_reqs"]:
            atom = ConditionAtom(
                atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id(skill_req["skill"]),
                threshold=skill_req["level"],
                data={"boostable": bool(skill_req.get("boostable", False))})
            if not skill_req.get("ironman", False):
                children.append(atom)
                continue
            # K4 wrapper: OR( account_type == "main", atom )
            or_gid = group_id(nid, sub_index)
            sub_index += 1
            acct_atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE,
                                      data={"value": _MAIN_FAMILY})
            groups[or_gid] = ConditionGroup(id=or_gid, op=Op.OR, parent=root_gid,
                                            children=[acct_atom, atom])
            children.append(or_gid)

        groups[root_gid] = ConditionGroup(id=root_gid, op=Op.AND, parent=None, children=children)
        edges.append(Edge(id=edge_id(nid), type=EdgeType.REQUIRES, src=nid,
                          dst=None, cond_group=root_gid))

    return nodes, edges, groups, diary_records
