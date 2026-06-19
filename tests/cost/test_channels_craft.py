# tests/cost/test_channels_craft.py
"""Task 6: craft channel -- recipes.json loader + craft ChannelRecords."""
from __future__ import annotations

import os

from osrs_planner.cost.channels import load_recipes

RECIPES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "recipes.json"
)


def test_load_recipes_yields_craft_records():
    records = load_recipes(RECIPES)
    by_item = {r.item_id: r for r in records}

    atk = by_item["item:121"]
    assert atk.channel == "craft"
    assert atk.currency == "currency:coins"
    assert atk.amount is None  # craft cost computed from inputs, not a face amount
    assert atk.inputs == [("item:91", 1), ("item:221", 1)]
    assert atk.output_qty == 1
    assert atk.account_allow == frozenset({"main", "ironman", "uim"})
    assert atk.yield_ == 1
    assert atk.time is None

    unf = by_item["item:91"]
    assert unf.channel == "craft"
    assert unf.inputs == [("item:249", 1), ("item:227", 1)]
    assert unf.output_qty == 1
