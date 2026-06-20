# tests/cost/test_recipe_income_leak.py
"""Regression: income's processing records must NOT leak into the cost overlay.

data/recipes.json is SHARED by both overlays (the cost potion chain + the income
green-dragons exemplar). Cost's craft loader can only correctly price true `craft`
records: it computes cost = sum(cheapest input) and has NO slot for a SERVICE fee.
Income's tan record (output green dragon leather, realization_channel="tan",
service_fee_coins=20) is a tanner SERVICE, not a craft -- ingesting it as a craft
route silently DROPS the 20gp/hide fee and under-prices everything downstream
(green d'hide body), crossing the income/cost boundary through the shared file.

The cost loader must skip any record it cannot model correctly (realization_channel
!= "craft", or carrying a service_fee_coins the craft channel ignores). Income still
reads those records via its own recipe reverse-index (which honors the fee), so this
is cost-side only.
"""
from __future__ import annotations

import json
import os

from osrs_planner.cost.channels import build_index_from_repo, load_recipes
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.cost.routing import _cheapest_gold, price_routes

REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA = os.path.join(REPO, "data")
RECIPES = os.path.join(DATA, "recipes.json")
GE_PRICES = os.path.join(DATA, "ge_prices.json")

# income's tanner SERVICE record (green dragonhide -> green dragon leather)
TAN_OUTPUT = "item:1745"  # Green dragon leather (realization_channel="tan", fee=20)


def test_cost_loader_only_yields_true_craft_records():
    """Every ChannelRecord cost ingests is realization_channel=="craft"."""
    records = load_recipes(RECIPES)
    assert records, "expected the cost potion chain to load"
    assert all(r.realization_channel == "craft" for r in records), (
        "cost ingested a non-craft (service) record: "
        + repr([(r.item_id, r.realization_channel) for r in records])
    )


def test_tan_service_record_excluded_from_cost_loader():
    """The income tan record (realization_channel='tan' + service_fee_coins) is skipped."""
    out_ids = {r.item_id for r in load_recipes(RECIPES)}
    assert TAN_OUTPUT not in out_ids, (
        "the tan SERVICE record leaked into the cost craft loader (fee would be dropped)"
    )


def test_no_recipe_record_with_service_fee_is_ingested():
    """Belt-and-suspenders: a craft record carrying a service fee is also skipped.

    The craft channel has no fee slot, so any record with service_fee_coins (today
    only the tan record) must be skipped regardless of its realization_channel.
    """
    raw = json.load(open(RECIPES, encoding="utf-8"))["records"]
    fee_outputs = {r["output_item_id"] for r in raw if r.get("service_fee_coins") is not None}
    assert fee_outputs, "fixture expected at least one fee-bearing income record"
    ingested = {r.item_id for r in load_recipes(RECIPES)}
    assert not (fee_outputs & ingested), (
        "cost ingested a fee-bearing record (the dropped fee under-prices it): "
        + repr(fee_outputs & ingested)
    )


def test_potion_craft_chain_still_loads():
    """The legitimate cost craft records survive the filter."""
    out_ids = {r.item_id for r in load_recipes(RECIPES)}
    for legit in ("item:121", "item:91", "item:227"):  # attack potion chain
        assert legit in out_ids, f"legit craft record {legit} was wrongly filtered out"


def test_leather_has_no_cost_craft_route_after_filter():
    """In the built index, the tan output has no `craft` channel (only a synthetic ge)."""
    provider = SnapshotPriceProvider.from_file(GE_PRICES)
    index = build_index_from_repo(REPO, provider)
    channels = [r.channel for r in index.get(TAN_OUTPUT, [])]
    assert "craft" not in channels, (
        f"tan output still has a cost craft route (fee dropped): channels={channels}"
    )


def test_leather_main_cost_is_ge_not_the_fee_dropped_craft():
    """A main now prices green dragon leather via the GE (pre-tanned), not the
    under-counted fee-dropped craft route. The cheapest known route is the ge one."""
    provider = SnapshotPriceProvider.from_file(GE_PRICES)
    index = build_index_from_repo(REPO, provider)
    routes = price_routes(TAN_OUTPUT, "main", provider, index)
    known = [r for r in routes if r.gold_status == "known" and r.gold_cost is not None]
    assert known, "expected at least one known route for green dragon leather (main)"
    cheapest = _cheapest_gold(routes)
    chosen = next(r for r in known if r.gold_cost == cheapest)
    assert chosen.channel == "ge", (
        f"main leather cost should come from the GE, not a craft route; got {chosen.channel}"
    )
