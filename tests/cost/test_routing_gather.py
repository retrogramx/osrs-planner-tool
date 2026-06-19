# tests/cost/test_routing_gather.py
"""Task 7: gather routing -- main prices herb via GE, iron via gather (no GE)."""
from __future__ import annotations

import os

from osrs_planner.cost.channels import build_index_from_repo
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.cost.routing import price_routes

REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _setup():
    provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
    index = build_index_from_repo(REPO, provider)
    return provider, index


def test_main_guam_has_ge_and_gather_routes():
    provider, index = _setup()
    routes = price_routes("item:249", "main", provider, index)
    channels = {r.channel for r in routes}
    assert "ge" in channels      # main may GE-buy the herb directly
    assert "gather" in channels
    ge = next(r for r in routes if r.channel == "ge")
    assert ge.gold_cost == 248   # Guam leaf GE high
    gather = next(r for r in routes if r.channel == "gather")
    # seed (item:5291) cheapest = min(ge 27, shop 25) = 25
    assert gather.gold_cost == 25
    assert gather.gold_status == "known"


def test_ironman_guam_has_no_ge_route_and_gathers_via_shop_seed():
    provider, index = _setup()
    routes = price_routes("item:249", "ironman", provider, index)
    channels = {r.channel for r in routes}
    assert "ge" not in channels  # ge is main-only
    assert "gather" in channels
    gather = next(r for r in routes if r.channel == "gather")
    # iron: seed has no GE route, only the shop (25 coins) -> gather = 25
    assert gather.gold_cost == 25
    assert gather.gold_status == "known"
