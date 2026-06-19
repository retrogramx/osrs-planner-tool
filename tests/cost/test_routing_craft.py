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


def test_main_craft_unf_gold_is_summed_cheapest_inputs():
    provider, index = _setup()
    routes = price_routes("item:91", "main", provider, index)
    craft = [r for r in routes if r.channel == "craft"]
    assert len(craft) == 1
    # craft gold = sum of the CHEAPEST route of each input.
    # Guam leaf (item:249): Task 7's gather route (Guam seed @ cheapest 25) now beats
    # GE 248, so the leaf input is gathered, not ge-bought: gather 25.
    # + Vial of water (item:227): the empty-vial shop row (item:229 @ 2) -> vial-of-water
    # craft (free fill) now beats GE 4, so the vial input costs 2 (was GE 4 = 29 before
    # the iron-acquirable secondaries were added). unf = 25 + 2 = 27.
    assert craft[0].gold_cost == 27
    assert craft[0].gold_status == "known"
    assert len(craft[0].inputs) == 2  # recursive sub-routes recorded


def test_main_craft_attack_potion_recurses_one_level():
    provider, index = _setup()
    routes = price_routes("item:121", "main", provider, index)
    craft = [r for r in routes if r.channel == "craft"]
    assert len(craft) == 1
    # Recurses into the unf, which now itself uses the cheaper gather route for Guam
    # leaf (Task 7) AND the empty-vial -> vial-of-water shop chain: unf cheapest =
    # min(ge 434, craft 27) = 27 ; + eye of newt (item:221) now via its shop row (3,
    # cheaper than GE 5) = 30 (was 257 -> 34 before the iron-acquirable secondaries).
    assert craft[0].gold_cost == 30
    assert craft[0].gold_status == "known"
