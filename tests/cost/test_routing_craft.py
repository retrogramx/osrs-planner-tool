# tests/cost/test_routing_craft.py
"""Task 6: routing recursion -- craft route gold = summed priced inputs."""
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


def test_main_craft_unf_gold_is_summed_ge_inputs():
    provider, index = _setup()
    routes = price_routes("item:91", "main", provider, index)
    craft = [r for r in routes if r.channel == "craft"]
    assert len(craft) == 1
    # Guam leaf (item:249) GE 248 + Vial of water (item:227) GE 4 = 252
    assert craft[0].gold_cost == 252
    assert craft[0].gold_status == "known"
    assert len(craft[0].inputs) == 2  # recursive sub-routes recorded


def test_main_craft_attack_potion_recurses_one_level():
    provider, index = _setup()
    routes = price_routes("item:121", "main", provider, index)
    craft = [r for r in routes if r.channel == "craft"]
    assert len(craft) == 1
    # unf cheapest = min(ge 434, craft 252) = 252 ; + eye of newt (item:221) ge 5 = 257
    assert craft[0].gold_cost == 257
    assert craft[0].gold_status == "known"
