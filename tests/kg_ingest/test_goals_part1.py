"""Engine-level acceptance for build_goals() part 1 (K8 goals 1-3):
Dragon scimitar, fairy rings, Tzhaar-ket-om — through the real Engine."""
from __future__ import annotations

from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.engine import Engine

from kg_ingest.builders.goals import build_goals

_SUPPORT_NODES = [
    Node(id="quest:monkey-madness-i", kind=NodeKind.QUEST,
         name="Monkey Madness I", slug="monkey-madness-i", data={}),
    Node(id="quest:fairytale-ii-cure-a-queen", kind=NodeKind.QUEST,
         name="Fairytale II - Cure a Queen", slug="fairytale-ii-cure-a-queen", data={}),
    Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={}),
    Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength", data={}),
]
_OBSERVED = {"skill_level", "item", "quest", "achievement_diary"}


def _store() -> InMemoryKGStore:
    nodes, edges, groups = build_goals()
    return InMemoryKGStore(nodes=nodes + _SUPPORT_NODES, edges=edges, groups=groups)


def _status(store, state, node_id) -> str:
    return Engine(store).is_unlocked(state, node_id).card.status


def test_dragon_scimitar_met():
    met = AccountState(mode="normal", levels={"skill:attack": 60},
                       counts={"item:4587": 1},
                       quest_state={"quest:monkey-madness-i": "completed"},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, "item:4587") == "unlocked"


def test_dragon_scimitar_unmet_missing_quest():
    unmet = AccountState(mode="normal", levels={"skill:attack": 60},
                         counts={"item:4587": 1},
                         quest_state={"quest:monkey-madness-i": "not_started"},
                         observable_families=_OBSERVED)
    assert _status(_store(), unmet, "item:4587") == "locked"


def test_dragon_scimitar_unmet_low_attack():
    unmet = AccountState(mode="normal", levels={"skill:attack": 59},
                         counts={"item:4587": 1},
                         quest_state={"quest:monkey-madness-i": "completed"},
                         observable_families=_OBSERVED)
    assert _status(_store(), unmet, "item:4587") == "locked"


def test_fairy_rings_met():
    met = AccountState(mode="normal",
                       quest_state={"quest:fairytale-ii-cure-a-queen": "in_progress"},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, "access:fairy-rings") == "unlocked"


def test_fairy_rings_met_when_completed():
    met = AccountState(mode="normal",
                       quest_state={"quest:fairytale-ii-cure-a-queen": "completed"},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, "access:fairy-rings") == "unlocked"


def test_fairy_rings_unmet_not_started():
    unmet = AccountState(mode="normal",
                         quest_state={"quest:fairytale-ii-cure-a-queen": "not_started"},
                         observable_families=_OBSERVED)
    assert _status(_store(), unmet, "access:fairy-rings") == "locked"


def test_obby_maul_met():
    met = AccountState(mode="normal", levels={"skill:strength": 60},
                       counts={"item:6528": 1}, observable_families=_OBSERVED)
    assert _status(_store(), met, "item:6528") == "unlocked"


def test_obby_maul_unmet_low_strength():
    unmet = AccountState(mode="normal", levels={"skill:strength": 59},
                         counts={"item:6528": 1}, observable_families=_OBSERVED)
    assert _status(_store(), unmet, "item:6528") == "locked"


def test_obby_maul_unmet_not_owned():
    unmet = AccountState(mode="normal", levels={"skill:strength": 60},
                         counts={}, observable_families=_OBSERVED)
    assert _status(_store(), unmet, "item:6528") == "locked"


def test_build_goals_emits_three_goal_nodes_and_edges():
    nodes, edges, groups = build_goals()
    node_ids = {n.id for n in nodes}
    assert {"item:4587", "access:fairy-rings", "item:6528"} <= node_ids
    goal_srcs = {e.src for e in edges if e.type is EdgeType.REQUIRES}
    assert {"item:4587", "access:fairy-rings", "item:6528"} <= goal_srcs
    for e in edges:
        if e.type is EdgeType.REQUIRES and e.src in {"item:4587", "access:fairy-rings", "item:6528"}:
            assert e.dst is None
            assert e.cond_group in groups
