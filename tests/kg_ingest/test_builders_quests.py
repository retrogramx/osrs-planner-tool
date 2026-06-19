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
