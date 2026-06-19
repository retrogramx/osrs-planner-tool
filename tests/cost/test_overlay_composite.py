# tests/cost/test_overlay_composite.py
"""Composite-goal resolution + strategic-timing notes (cost overlay, design §5).

A composite goal (Voidwaker from 3 components; full Infinity = 5 pieces) is
resolved through the REAL knowledge graph to its item needs, each priced via
price_routes, then rolled up into one CostCard. The notes hook records the
downstream goals an item feeds (KG read-only). All numbers are read from the
committed snapshot, never hardcoded.
"""
from __future__ import annotations

import json
import os

import pytest

from osrs_planner.cost.channels import build_index_from_repo
from osrs_planner.cost.overlay import expand_for_account
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.state import AccountState

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GE_PRICES = os.path.join(REPO, "data", "ge_prices.json")
KG_DIR = os.path.join(REPO, "kg")

VOIDWAKER = "item:27690"
VW_COMPONENTS = ("item:27681", "item:27684", "item:27687")
INFINITY_GOAL = "gear_loadout_goal:infinity"
INFINITY_PIECES = ("item:6918", "item:6916", "item:6924", "item:6922", "item:6920")


@pytest.fixture(scope="module")
def provider() -> SnapshotPriceProvider:
    return SnapshotPriceProvider.from_file(GE_PRICES)


@pytest.fixture(scope="module")
def kg() -> JsonKGStore:
    return JsonKGStore.from_dir(KG_DIR)


@pytest.fixture(scope="module")
def index(provider):
    return build_index_from_repo(REPO, provider)


def _ge_high(item_id: str) -> int | None:
    num = int(item_id.split(":", 1)[1])
    with open(GE_PRICES, encoding="utf-8") as f:
        recs = json.load(f)["records"]
    rec = next((r for r in recs if r["item_id"] == num), None)
    if rec is None or not rec.get("price"):
        return None
    return rec["price"].get("high")


def test_voidwaker_main_rolls_up_three_components(provider, kg, index):
    state = AccountState(mode="main")
    card = expand_for_account(VOIDWAKER, state, provider, index, kg=kg)
    assert card.item_id == VOIDWAKER
    assert card.account_family == "main"
    assemble = [r for r in card.routes if r.inputs]
    assert assemble, "composite goal must expose an assemble-from-components route"
    inputs = assemble[0].inputs
    assert len(inputs) == len(VW_COMPONENTS)
    expected = {c: _ge_high(c) for c in VW_COMPONENTS}
    got = {comp_id: sub.gold_cost for comp_id, sub in zip(VW_COMPONENTS, inputs)}
    assert got == expected


def test_voidwaker_ironman_has_no_ge_direct_route(provider, kg, index):
    state = AccountState(mode="ironman")
    card = expand_for_account(VOIDWAKER, state, provider, index, kg=kg)
    direct_ge = [r for r in card.routes if r.channel == "ge" and not r.inputs]
    assert direct_ge == []
    assemble = [r for r in card.routes if r.inputs]
    assert assemble and len(assemble[0].inputs) == len(VW_COMPONENTS)


def test_full_infinity_rolls_up_five_pieces(provider, kg, index):
    state = AccountState(mode="main")
    card = expand_for_account(INFINITY_GOAL, state, provider, index, kg=kg)
    assemble = [r for r in card.routes if r.inputs]
    assert assemble, "loadout goal must expose a roll-up route"
    assert len(assemble[0].inputs) == len(INFINITY_PIECES)
    assert card.rankings["by_time"] == []  # skeleton stays empty
    for r in card.routes:
        assert r.time_status == "not_estimated"
    expected_total = sum(_ge_high(p) for p in INFINITY_PIECES)
    assert assemble[0].gold_cost == expected_total


def test_notes_records_downstream_goals_when_kg_passed(provider, kg, index):
    state = AccountState(mode="main")
    card = expand_for_account("item:27681", state, provider, index, kg=kg)
    assert VOIDWAKER in card.notes  # a Voidwaker component feeds the Voidwaker goal


def test_notes_empty_without_kg(provider, index):
    state = AccountState(mode="main")
    card = expand_for_account("item:4587", state, provider, index, kg=None)
    assert card.notes == []
