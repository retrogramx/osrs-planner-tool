"""Unit tests for kg_ingest.ids and kg_ingest.builders.quests (Task 3)."""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import (
    slugify, quest_id, skill_id, item_id, access_id, gear_loadout_id,
    group_id, edge_id,
)


def test_slugify_lowercases_and_dashes():
    assert slugify("Animal Magnetism") == "animal-magnetism"


def test_slugify_strips_punctuation_and_apostrophes():
    assert slugify("Cook's Assistant") == "cooks-assistant"
    assert slugify("Recipe for Disaster/Another Cook's Quest") == \
        "recipe-for-disaster-another-cooks-quest"


def test_id_helpers_use_locked_prefixes():
    assert quest_id("Animal Magnetism") == "quest:animal-magnetism"
    assert skill_id("Crafting") == "skill:crafting"
    assert item_id(4587) == "item:4587"
    assert item_id("6528") == "item:6528"
    assert access_id("Fairy rings") == "access:fairy-rings"
    assert gear_loadout_id("Infinity") == "gear_loadout:infinity"


def test_group_id_is_deterministic_and_offset_per_owner():
    a = group_id("quest:animal-magnetism", 0)
    assert a == group_id("quest:animal-magnetism", 0)
    assert a != group_id("quest:animal-magnetism", 1)
    assert a != group_id("quest:another-quest", 0)


def test_edge_id_is_deterministic_per_owner():
    assert edge_id("quest:animal-magnetism") == edge_id("quest:animal-magnetism")
    assert edge_id("quest:animal-magnetism") != edge_id("quest:another-quest")


from kg_ingest.builders.quests import build_quests


def _sample_records() -> list[dict]:
    return [
        {"name": "Animal Magnetism", "node_type": "quest",
         "prereqs": [{"quest": "Ernest the Chicken", "stage": "completed"}],
         "skill_reqs": [
             {"skill": "Crafting", "level": 19, "ironman": False, "boostable": False},
             {"skill": "Prayer", "level": 31, "ironman": True, "boostable": True}]},
        {"name": "Alfred Grimhand's Barcrawl", "node_type": "miniquest",
         "prereqs": [], "skill_reqs": []},
        {"name": "Recipe for Disaster/Another Cook's Quest", "node_type": "quest",
         "prereqs": [{"quest": "Cook's Assistant", "stage": "completed"}], "skill_reqs": []},
        {"name": "Easy Ardougne Diary", "node_type": "diary", "prereqs": [], "skill_reqs": []},
    ]


def _node_by_id(nodes, node_id):
    matches = [n for n in nodes if n.id == node_id]
    assert len(matches) == 1, f"expected exactly one {node_id}, got {len(matches)}"
    return matches[0]


def test_build_quests_returns_four_tuple_with_diaries_routed():
    nodes, edges, groups, diary_records = build_quests(_sample_records())
    node_ids = {n.id for n in nodes}
    assert "quest:animal-magnetism" in node_ids
    assert "quest:alfred-grimhands-barcrawl" in node_ids
    assert "quest:recipe-for-disaster-another-cooks-quest" in node_ids
    assert "diary:easy-ardougne-diary" not in node_ids
    assert all(not n.id.startswith("diary:") for n in nodes)
    assert diary_records == [r for r in _sample_records() if r["node_type"] == "diary"]


def test_build_quests_node_kinds_and_miniquest_flag():
    nodes, _e, _g, _d = build_quests(_sample_records())
    am = _node_by_id(nodes, "quest:animal-magnetism")
    assert am.kind is NodeKind.QUEST
    assert am.name == "Animal Magnetism"
    assert am.slug == "animal-magnetism"
    assert am.data.get("miniquest") is not True
    mini = _node_by_id(nodes, "quest:alfred-grimhands-barcrawl")
    assert mini.kind is NodeKind.QUEST
    assert mini.data.get("miniquest") is True
