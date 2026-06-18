# tests/engine/test_fixture_smoke.py
"""Smoke test: the hand-authored KG fixture loads and matches the worked examples."""

from osrs_planner.engine.conditions import evaluate
from osrs_planner.engine.kg.model import EdgeType, NodeKind
from osrs_planner.engine.kleene import Tri
from tests.engine.fixtures.kg_fixture import (
    G_SCURRIUS_OR,
    G_VOID_SET,
    build_store,
    fresh_main,
    iron_75atk_60str_novoid,
    main_70atk_70str,
    main_full_void,
)


def test_store_loads_core_nodes():
    kg = build_store()
    scurrius = kg.node("npc:7221")
    assert scurrius is not None
    assert scurrius.kind is NodeKind.MONSTER
    assert scurrius.name == "Scurrius"
    # the four void slots + three helms + skills + access all present
    for nid in ("access:scurrius-lair", "gear_loadout:void", "item:8839",
                "item:8840", "item:8842", "item:11663", "skill:attack"):
        assert kg.node(nid) is not None, nid


def test_scurrius_requires_access_and_flagship_condition():
    kg = build_store()
    req_edges = [e for e in kg.edges
                 if e.type is EdgeType.REQUIRES and e.src == "npc:7221"]
    # one hard access prereq (dst set) + one dst=None flagship condition edge
    assert any(e.dst == "access:scurrius-lair" for e in req_edges)
    assert any(e.dst is None and e.cond_group == G_SCURRIUS_OR for e in req_edges)


def test_void_composition_resolves_via_store():
    kg = build_store()
    # composition_of resolves the gear_loadout's dst=None requires edge to its cond_group
    assert kg.composition_of("gear_loadout:void") == G_VOID_SET


def test_flagship_false_for_iron_75_60_no_void():
    # OR( AND(75>=70=T, 60>=70=F)=F, gear_loadout:void=F ) -> FALSE  (kg-schema worked result)
    kg = build_store()
    assert evaluate(G_SCURRIUS_OR, iron_75atk_60str_novoid(), kg) is Tri.FALSE


def test_flagship_true_for_main_70_70():
    # the stats branch satisfies the OR -> TRUE
    kg = build_store()
    assert evaluate(G_SCURRIUS_OR, main_70atk_70str(), kg) is Tri.TRUE


def test_flagship_true_for_main_full_void():
    # gear_loadout branch (60/60 att/str, full Void) satisfies the OR -> TRUE
    # proves D3: gear_loadout atom recurses into the composition tree via composition_of()
    kg = build_store()
    assert evaluate(G_SCURRIUS_OR, main_full_void(), kg) is Tri.TRUE


def test_fresh_main_flagship_is_false():
    # fresh_main has no levels and no items; conditions.py treats absent skill levels
    # as level 1 (always-observable default) and absent items as count 0 (bank-observable).
    # Both branches evaluate to FALSE -> OR is FALSE.
    # NOTE: the plan's comment claimed UNKNOWN here, but conditions.py's SKILL_LEVEL and
    # ITEM branches never return UNKNOWN -- they hardcode absence as 1/0 respectively.
    kg = build_store()
    assert evaluate(G_SCURRIUS_OR, fresh_main(), kg) is Tri.FALSE
