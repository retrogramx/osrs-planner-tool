"""income.filter.classify_method (reuses the engine condition-evaluator)."""
from __future__ import annotations

from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.model import Node, NodeKind
from osrs_planner.income.filter import classify_method, _skill_id, _resolve_quest_id
from osrs_planner.income.methods import MethodRecord, Requirements, Flow


def _kg() -> InMemoryKGStore:
    nodes = [
        Node(id="skill:firemaking", kind=NodeKind.SKILL, name="Firemaking", slug="firemaking"),
        Node(id="skill:agility", kind=NodeKind.SKILL, name="Agility", slug="agility"),
        Node(id="quest:dragon-slayer-ii", kind=NodeKind.QUEST, name="Dragon Slayer II", slug="dragon-slayer-ii"),
        Node(id="item:22978", kind=NodeKind.ITEM, name="Dragon hunter lance", slug="dragon-hunter-lance"),
    ]
    return InMemoryKGStore(nodes=nodes, edges=[], groups={})


def _method(**over) -> MethodRecord:
    base = dict(
        id="method:test", name="Test", category="Skilling", members=True,
        audience="main", requires_ge=False, iron_eligible=True, realization_channel="coins",
        outputs=[Flow(item_id="item:1753", is_coins=False, qty_per_hour=100.0)],
        inputs=[], requirements=Requirements(skills={}, quests=[], items=[]),
        stage=None, tags={}, processing_dependent=False, net_sign="earner",
        source="Wiki", url="https://x", accessed_at="2026-06-19",
    )
    base.update(over)
    return MethodRecord(**base)


def test_skill_id_lowercases_display_name():
    assert _skill_id("Firemaking") == "skill:firemaking"
    assert _skill_id("Magic") == "skill:magic"


def test_resolve_quest_strips_parenthetical_prose():
    kg = _kg()
    assert _resolve_quest_id("A Kingdom Divided (for thralls)", kg) is None  # not in this fixture
    assert _resolve_quest_id("Dragon Slayer II", kg) == "quest:dragon-slayer-ii"


def test_doable_now_when_levels_met():
    state = AccountState(mode="ironman", levels={"skill:firemaking": 60}, observable_families={"skill_level"})
    m = _method(requirements=Requirements(skills={"Firemaking": 50}, quests=[], items=[]))
    status, detail = classify_method(m, state, _kg())
    assert status == "doable_now"
    assert detail == {"missing": [], "unverified": []}


def test_future_gated_when_quest_missing():
    state = AccountState(mode="ironman", levels={}, observable_families={"quest"})
    m = _method(requirements=Requirements(skills={}, quests=["Dragon Slayer II"], items=[]))
    status, detail = classify_method(m, state, _kg())
    assert status == "future_gated"
    assert "quest:dragon-slayer-ii" in detail["missing"]


def test_future_gated_when_skill_below_threshold():
    state = AccountState(mode="main", levels={"skill:firemaking": 40}, observable_families={"skill_level"})
    m = _method(requirements=Requirements(skills={"Firemaking": 50}, quests=[], items=[]))
    status, detail = classify_method(m, state, _kg())
    assert status == "future_gated"
    assert "skill:firemaking" in detail["missing"]


def test_unverified_when_item_unobservable():
    state = AccountState(mode="main", levels={"skill:firemaking": 99}, observable_families={"skill_level", "quest"})
    m = _method(requirements=Requirements(skills={"Firemaking": 50}, quests=[], items=["item:22978"]))
    status, detail = classify_method(m, state, _kg())
    assert status == "unverified"
    assert "item:22978" in detail["unverified"]


def test_unverified_when_item_req_is_unresolvable_prose():
    state = AccountState(mode="ironman", levels={}, observable_families={"skill_level", "quest"})
    m = _method(requirements=Requirements(skills={}, quests=[], items=["Rogue equipment"]))
    status, detail = classify_method(m, state, _kg())
    assert status == "unverified"
    assert "Rogue equipment" in detail["unverified"]


def test_missing_dominates_unverified():
    state = AccountState(mode="main", levels={"skill:firemaking": 10}, observable_families={"skill_level"})
    m = _method(requirements=Requirements(skills={"Firemaking": 50}, quests=[], items=["item:22978"]))
    status, detail = classify_method(m, state, _kg())
    assert status == "future_gated"
    assert "skill:firemaking" in detail["missing"]
