"""build_recipe_reverse_index: input_item_id -> products consuming it."""
from __future__ import annotations

from osrs_planner.income.methods import build_recipe_reverse_index


def _recipes_doc():
    return {
        "records": [
            {
                "output_item_id": "item:1135",  # green d'hide body
                "name": "Green d'hide body",
                "skill": "Crafting",
                "level": 63,
                "inputs": [{"item_id": "item:1745", "qty": 3}, {"item_id": "item:1734", "qty": 1}],
                "output_qty": 1,
            },
            {
                "output_item_id": "item:1745",  # green dragon leather (tan)
                "name": "Green dragon leather",
                "skill": None,
                "level": 1,
                "inputs": [{"item_id": "item:1753", "qty": 1}],
                "output_qty": 1,
                "service_fee_coins": 40,
            },
        ]
    }


def test_reverse_index_maps_input_to_products():
    idx = build_recipe_reverse_index(_recipes_doc())
    hide_products = idx["item:1753"]
    assert len(hide_products) == 1
    assert hide_products[0]["output_item_id"] == "item:1745"
    assert hide_products[0]["inputs"][0]["qty"] == 1
    leather_products = idx["item:1745"]
    assert leather_products[0]["output_item_id"] == "item:1135"
    assert leather_products[0]["level"] == 63
    leather_in = next(i for i in leather_products[0]["inputs"] if i["item_id"] == "item:1745")
    assert leather_in["qty"] == 3


def test_unknown_input_absent_from_index():
    idx = build_recipe_reverse_index(_recipes_doc())
    assert "item:9999" not in idx
    # a terminal product (body) is never an input -> absent as a key
    assert "item:1135" not in idx


def test_full_recipe_record_carried_through():
    idx = build_recipe_reverse_index(_recipes_doc())
    rec = idx["item:1753"][0]
    assert rec.get("service_fee_coins") == 40
    assert "output_qty" in rec and "inputs" in rec
