"""diary cape goal + count_satisfied completion gate (diaries Task 3)."""
from kg_ingest.builders.diary_goals import build_diary_goals
from osrs_planner.engine.kg.model import AtomType, ConditionAtom, EdgeType, NodeKind


def _rec():
    return {"id": "goal:achievement-diary-cape", "name": "Achievement diary cape",
            "counter_type": "member_count", "thresholds": [48],
            "grants": {"reward": "unlock", "category": "equipment",
                       "name": "Achievement diary cape", "access": "Achievement diary cape"}}


def test_cape_node_and_count_satisfied_gate():
    tier_ids = [f"diary:r{i}:easy" for i in range(48)]
    nodes, edges, groups = build_diary_goals([_rec()], tier_ids)
    goal = [n for n in nodes if n.kind is NodeKind.GOAL][0]
    assert goal.id == "goal:achievement-diary-cape"
    assert goal.data == {"counter_type": "member_count", "thresholds": [48]}
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    atom = groups[req.cond_group].children[0]
    assert isinstance(atom, ConditionAtom) and atom.atom_type is AtomType.COUNT_SATISFIED
    assert atom.threshold == 48 and atom.data["set_ref"] == tier_ids


def test_cape_threshold_gated_grant():
    nodes, edges, groups = build_diary_goals([_rec()], ["diary:r:easy"])
    grant = [e for e in edges if e.type is EdgeType.GRANTS][0]
    assert grant.src == "goal:achievement-diary-cape" and grant.cond_group is not None
    assert grant.data["reward"] == "unlock"
