"""kg_ingest/builders/content_nodes.py — content-node instances for the
effect→content layer (diaries Task 6). Activity/monster/region nodes get
*existence* here (id+kind+name+slug); their facts (drops/location) are out of
scope (spec §4)."""
from __future__ import annotations

import pytest

from osrs_planner.engine.kg.model import Node, NodeKind
from kg_ingest.builders.content_nodes import build_content_nodes


def _by_id(nodes: list[Node]) -> dict[str, Node]:
    return {n.id: n for n in nodes}


def test_activity_node_kind_name_slug():
    n = _by_id(build_content_nodes([
        {"id": "activity:barrows", "kind": "activity", "name": "Barrows", "slug": "barrows"},
    ]))["activity:barrows"]
    assert n.kind is NodeKind.ACTIVITY
    assert n.name == "Barrows"
    assert n.slug == "barrows"


def test_region_and_monster_kinds():
    nodes = _by_id(build_content_nodes([
        {"id": "region:burgh-de-rott", "kind": "region", "name": "Burgh de Rott", "slug": "burgh-de-rott"},
        {"id": "monster:abyssal-demon", "kind": "monster", "name": "Abyssal demon", "slug": "abyssal-demon"},
    ]))
    assert nodes["region:burgh-de-rott"].kind is NodeKind.REGION
    assert nodes["monster:abyssal-demon"].kind is NodeKind.MONSTER


def test_optional_data_passthrough():
    n = _by_id(build_content_nodes([
        {"id": "activity:barrows", "kind": "activity", "name": "Barrows", "slug": "barrows",
         "data": {"note": "the Barrows brothers' crypts"}},
    ]))["activity:barrows"]
    assert n.data == {"note": "the Barrows brothers' crypts"}


def test_id_prefix_must_match_kind():
    with pytest.raises(ValueError, match="prefix"):
        build_content_nodes([
            {"id": "region:barrows", "kind": "activity", "name": "Barrows", "slug": "barrows"},
        ])


def test_skill_ids_are_rejected():
    # skills already exist as nodes; content_nodes does not mint them.
    with pytest.raises(ValueError, match="skill"):
        build_content_nodes([
            {"id": "skill:slayer", "kind": "skill", "name": "Slayer", "slug": "slayer"},
        ])


def test_unknown_kind_rejected():
    with pytest.raises(ValueError, match="kind"):
        build_content_nodes([
            {"id": "item:4587", "kind": "item", "name": "Dragon scimitar", "slug": "4587"},
        ])


def test_sorted_and_deduped_by_id():
    nodes = build_content_nodes([
        {"id": "region:burgh-de-rott", "kind": "region", "name": "Burgh de Rott", "slug": "burgh-de-rott"},
        {"id": "activity:barrows", "kind": "activity", "name": "Barrows", "slug": "barrows"},
        {"id": "activity:barrows", "kind": "activity", "name": "Barrows", "slug": "barrows"},
    ])
    assert [n.id for n in nodes] == ["activity:barrows", "region:burgh-de-rott"]


def test_conflicting_duplicate_raises():
    with pytest.raises(ValueError, match="conflict"):
        build_content_nodes([
            {"id": "activity:barrows", "kind": "activity", "name": "Barrows", "slug": "barrows"},
            {"id": "activity:barrows", "kind": "activity", "name": "Barrows Crypt", "slug": "barrows"},
        ])
