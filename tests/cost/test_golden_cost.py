# tests/cost/test_golden_cost.py
"""Golden cost-set over REAL datasets (design §8.2 / §10).

Each test asserts the FULL route set + by_gold ranking -- never a single
collapsed winner (enforces no-auto-pick). Numeric expectations are READ from the
committed snapshot at runtime, so a price refresh never breaks the structural
contract. Datasets are hand-curated, wiki-verified source-of-truth covering the
golden-set goals + a representative sample; bulk wiki sourcing is a disclosed v1
follow-up.
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

SCIMITAR = "item:4587"
OBBY_MAUL = "item:6528"
ATTACK_POTION = "item:121"
VOIDWAKER = "item:27690"
INFINITY_GOAL = "gear_loadout_goal:infinity"


@pytest.fixture(scope="module")
def provider():
    return SnapshotPriceProvider.from_file(GE_PRICES)


@pytest.fixture(scope="module")
def kg():
    return JsonKGStore.from_dir(KG_DIR)


@pytest.fixture(scope="module")
def index(provider):
    return build_index_from_repo(REPO, provider)


def _ge_high(item_id: str):
    num = int(item_id.split(":", 1)[1])
    with open(GE_PRICES, encoding="utf-8") as f:
        recs = json.load(f)["records"]
    rec = next((r for r in recs if r["item_id"] == num), None)
    if rec is None or not rec.get("price"):
        return None
    return rec["price"].get("high")


def _route_channels(route) -> set[str]:
    """Every channel name in a route AND its nested input sub-routes."""
    found = {route.channel}
    for sub in route.inputs:
        found |= _route_channels(sub)
    return found


# --- scimitar: main lists GE + shop (GE cheapest); ironman shop-only ---


def test_scimitar_main_lists_ge_and_shop_ge_ranks_first(provider, kg, index):
    card = expand_for_account(SCIMITAR, AccountState(mode="main"), provider, index, kg=kg)
    channels = {r.channel for r in card.routes}
    assert "ge" in channels and "shop" in channels
    ge = next(r for r in card.routes if r.channel == "ge")
    shop = next(r for r in card.routes if r.channel == "shop")
    assert ge.gold_cost == _ge_high(SCIMITAR)
    assert ge.amount == ge.gold_cost  # coin route: amount mirrors gold_cost
    assert shop.gold_cost > ge.gold_cost
    assert shop.currency == "currency:coins" and shop.amount == shop.gold_cost
    assert card.routes[card.rankings["by_gold"][0]].channel == "ge"
    assert len(card.rankings["by_gold"]) == len(card.routes)


def test_scimitar_ironman_only_shop_no_ge(provider, kg, index):
    card = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, index, kg=kg)
    channels = {r.channel for r in card.routes}
    assert "ge" not in channels
    assert "shop" in channels
    shop = next(r for r in card.routes if r.channel == "shop")
    assert shop.currency == "currency:coins"
    assert shop.gold_cost > 0


# --- obby maul: ironman priced in Tokkul (non-coin currency surfaces) ---


def test_obby_maul_ironman_priced_in_tokkul(provider, kg, index):
    card = expand_for_account(OBBY_MAUL, AccountState(mode="ironman"), provider, index, kg=kg)
    channels = {r.channel for r in card.routes}
    assert "ge" not in channels
    shop = next(r for r in card.routes if r.channel == "shop")
    assert shop.currency == "currency:tokkul"  # non-coin currency surfaces
    # gold_cost is COINS only -> None for tokkul; the tokkul figure lives in
    # `amount` so by_gold never face-compares it to coins (spec §11 Tokkul trap).
    assert shop.gold_cost is None
    assert shop.amount == 75001
    assert shop.gold_status == "known"  # a tokkul shop buy IS a known acquisition
    assert shop.time_status == "not_estimated"
    # The card does not present the tokkul route as a coin price: by_gold[0] is
    # the tokkul route (only route), but it carries no coin gold_cost.
    by_gold = card.rankings["by_gold"]
    assert card.routes[by_gold[0]].channel == "shop"
    assert card.routes[by_gold[0]].gold_cost is None


def test_obby_maul_main_lists_ge_and_tokkul_shop(provider, kg, index):
    card = expand_for_account(OBBY_MAUL, AccountState(mode="main"), provider, index, kg=kg)
    channels = {r.channel for r in card.routes}
    assert "ge" in channels and "shop" in channels
    ge = next(r for r in card.routes if r.channel == "ge")
    assert ge.gold_cost == _ge_high(OBBY_MAUL)
    assert ge.amount == ge.gold_cost  # coin route: amount mirrors gold_cost
    shop = next(r for r in card.routes if r.channel == "shop")
    assert shop.currency == "currency:tokkul"
    assert shop.gold_cost is None and shop.amount == 75001  # non-coin: no coin price
    # The Tokkul trap is FIXED: by_gold[0] is the GE COIN route, NOT the 75,001
    # tokkul shop route (no cross-currency face comparison -- spec §11).
    by_gold = card.rankings["by_gold"]
    assert card.routes[by_gold[0]].channel == "ge"
    assert card.routes[by_gold[0]].gold_cost == _ge_high(OBBY_MAUL)


# --- Attack potion: craft recursion (main vs ironman); values READ at runtime ---


def test_attack_potion_craft_recurses_into_inputs_main(provider, kg, index):
    card = expand_for_account(ATTACK_POTION, AccountState(mode="main"), provider, index, kg=kg)
    # FULL route set: a main lists at least the craft recursion + a direct GE buy.
    channels = {r.channel for r in card.routes}
    assert "craft" in channels and "ge" in channels
    assert len(card.rankings["by_gold"]) == len(card.routes)
    craft = next(r for r in card.routes if r.channel == "craft")
    assert craft.inputs, "craft route must expose recursive input sub-routes"
    assert any(sub.gold_cost is not None for sub in craft.inputs)
    # Value READ from the live recursion -- never hardcoded (a price/shop-row
    # refresh must not break the structural contract).
    assert craft.gold_status == "known"
    assert craft.gold_cost > 0


def test_attack_potion_ironman_priceable_and_ge_free(provider, kg, index):
    card = expand_for_account(ATTACK_POTION, AccountState(mode="ironman"), provider, index, kg=kg)
    # The iron potion is now PRICEABLE via the non-GE secondaries (eye of newt /
    # empty-vial -> vial-of-water shop rows + the gathered Guam leaf).
    craft = next(r for r in card.routes if r.channel == "craft")
    assert craft.gold_status == "known"
    assert craft.gold_cost > 0
    # The meaningful main-vs-iron divergence: NO route anywhere in the iron
    # recursion may draw from the `ge` channel (ge is main-only). This walks the
    # FULL route + every nested input, never a collapsed winner.
    assert "ge" not in _route_channels(craft)
    # And the card as a whole exposes no ge route for an ironman.
    assert "ge" not in {r.channel for r in card.routes}
    assert len(card.rankings["by_gold"]) == len(card.routes)


# --- Voidwaker + full Infinity: composite roll-ups, full route set ---


def test_voidwaker_main_full_route_set_and_ranking(provider, kg, index):
    card = expand_for_account(VOIDWAKER, AccountState(mode="main"), provider, index, kg=kg)
    direct_ge = [r for r in card.routes if r.channel == "ge" and not r.inputs]
    assemble = [r for r in card.routes if r.inputs]
    assert direct_ge and assemble  # full set, never collapsed
    assert len(assemble[0].inputs) == 3
    assert len(card.rankings["by_gold"]) == len(card.routes)
    comps = ("item:27681", "item:27684", "item:27687")
    assert assemble[0].gold_cost == sum(_ge_high(c) for c in comps)
    assert assemble[0].amount == assemble[0].gold_cost  # coin total: amount mirrors


def test_full_infinity_five_pieces_sum(provider, kg, index):
    card = expand_for_account(INFINITY_GOAL, AccountState(mode="main"), provider, index, kg=kg)
    assemble = next(r for r in card.routes if r.inputs)
    pieces = ("item:6918", "item:6916", "item:6924", "item:6922", "item:6920")
    assert len(assemble.inputs) == 5
    assert assemble.gold_cost == sum(_ge_high(p) for p in pieces)
    assert assemble.amount == assemble.gold_cost  # coin total: amount mirrors
    assert card.rankings["by_time"] == []  # skeleton stays empty


# --- boundary guard: engine never imports cost (import-walk) ---


def test_engine_never_imports_cost():
    import importlib
    import pkgutil

    import osrs_planner.engine as eng

    bad = []
    for mod in pkgutil.walk_packages(eng.__path__, eng.__name__ + "."):
        spec = importlib.util.find_spec(mod.name)
        src_file = spec.origin if spec else None
        if not src_file or not src_file.endswith(".py"):
            continue
        with open(src_file, encoding="utf-8") as f:
            text = f.read()
        if "osrs_planner.cost" in text or "from osrs_planner import cost" in text:
            bad.append(mod.name)
    assert bad == [], f"engine modules import cost (one-way boundary violated): {bad}"
