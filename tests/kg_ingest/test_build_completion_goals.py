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
