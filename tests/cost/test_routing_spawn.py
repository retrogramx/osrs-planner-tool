# tests/cost/test_routing_spawn.py
"""Task 8: spawn routing -- a spawn route's gold_cost is 0."""
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


def test_spawn_route_gold_cost_is_zero_for_both_families():
    provider, index = _setup()
    for family in ("main", "ironman"):
        routes = price_routes("item:2347", family, provider, index)
        spawn = next(r for r in routes if r.channel == "spawn")
        assert spawn.gold_cost == 0
        assert spawn.gold_status == "known"
        assert spawn.account_allowed is True


def test_main_hammer_also_has_ge_route_but_spawn_is_free():
    provider, index = _setup()
    routes = price_routes("item:2347", "main", provider, index)
    ge = next(r for r in routes if r.channel == "ge")
    assert ge.gold_cost == 177       # Hammer GE high
    spawn = next(r for r in routes if r.channel == "spawn")
    assert spawn.gold_cost == 0      # spawn is the free alternative
