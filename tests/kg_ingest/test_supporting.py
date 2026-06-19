"""Unit tests for kg_ingest.builders.supporting.build_supporting (K9 leaf nodes)."""
from __future__ import annotations

import pytest

from osrs_planner.engine.kg.model import Node, NodeKind
from kg_ingest.builders.supporting import build_supporting


def _by_id(nodes: list[Node]) -> dict[str, Node]:
    return {n.id: n for n in nodes}


def test_skill_node_kind_and_name():
    n = _by_id(build_supporting({"skill:attack"}))["skill:attack"]
    assert n.kind is NodeKind.SKILL
    assert n.name == "Attack"
    assert n.slug == "attack"


def test_skill_name_titlecased():
    assert _by_id(build_supporting({"skill:woodcutting"}))["skill:woodcutting"].name == "Woodcutting"


def test_item_name_resolved_from_items_equipment():
    n = _by_id(build_supporting({"item:4587"}))["item:4587"]
    assert n.kind is NodeKind.ITEM
    assert n.name == "Dragon scimitar"
    assert n.slug == "4587"


def test_unknown_item_id_raises():
    with pytest.raises(KeyError, match="item:99999999"):
        build_supporting({"item:99999999"})


def test_non_numeric_item_id_raises_clear_error():
    with pytest.raises(ValueError, match="numeric item_id"):
        build_supporting({"item:dragon-scimitar"})


def test_access_node():
    n = _by_id(build_supporting({"access:fairy-rings"}))["access:fairy-rings"]
    assert n.kind is NodeKind.ACCESS
    assert n.name == "Fairy rings"
    assert n.slug == "fairy-rings"


def test_minigame_node():
    n = _by_id(build_supporting({"minigame:fight-caves"}))["minigame:fight-caves"]
    assert n.kind is NodeKind.MINIGAME
    assert n.name == "Fight caves"
    assert n.slug == "fight-caves"


def test_npc_node():
    n = _by_id(build_supporting({"npc:7221"}))["npc:7221"]
    assert n.kind is NodeKind.MONSTER
    assert n.name == "NPC 7221"
    assert n.slug == "7221"


def test_diary_node_parses_region_and_tier():
    n = _by_id(build_supporting({"diary:lumbridge:elite"}))["diary:lumbridge:elite"]
    assert n.kind is NodeKind.DIARY
    assert n.name == "Lumbridge & Draynor Elite"
    assert n.slug == "lumbridge-elite"
    assert n.data == {"region": "lumbridge", "tier": "elite"}


def test_gear_loadout_node():
    n = _by_id(build_supporting({"gear_loadout:infinity"}))["gear_loadout:infinity"]
    assert n.kind is NodeKind.GEAR_LOADOUT
    assert n.name == "Infinity"
    assert n.slug == "infinity"


def test_dedup_one_node_per_id():
    nodes = build_supporting({"skill:attack", "skill:attack", "item:4587"})
    ids = [n.id for n in nodes]
    assert ids.count("skill:attack") == 1
    assert len(nodes) == len(set(ids)) == 2


def test_deterministic_sorted_output():
    a = build_supporting({"skill:strength", "item:4587", "skill:attack"})
    b = build_supporting({"item:4587", "skill:attack", "skill:strength"})
    assert [n.id for n in a] == [n.id for n in b]
    assert [n.id for n in a] == sorted(n.id for n in a)


def test_unknown_prefix_raises():
    with pytest.raises(ValueError, match="unknown ref_node domain"):
        build_supporting({"banana:42"})


def test_quest_prefix_is_not_supporting():
    with pytest.raises(ValueError, match="unknown ref_node domain"):
        build_supporting({"quest:dragon-slayer-i"})


def test_empty_set_returns_empty_list():
    assert build_supporting(set()) == []
