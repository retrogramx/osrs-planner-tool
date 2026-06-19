"""build_recipe_reverse_index: input_item_id -> products consuming it."""
from __future__ import annotations

import json
import os

from osrs_planner.income.methods import build_recipe_reverse_index

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECIPES = os.path.join(REPO, "data", "recipes.json")


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
                "service_fee_coins": 20,  # standard tanner fee (NOT 40, which is Eodan)
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
    assert rec.get("service_fee_coins") == 20
    assert "output_qty" in rec and "inputs" in rec


def test_committed_recipes_contain_green_dragons_chain():
    with open(RECIPES, encoding="utf-8") as f:
        doc = json.load(f)
    idx = build_recipe_reverse_index(doc)
    # hide -> leather (tan, 20gp/hide -- standard tanner fee, NOT 40 (Eodan))
    leather = next(p for p in idx["item:1753"] if p["output_item_id"] == "item:1745")
    assert leather.get("service_fee_coins") == 20
    assert leather["inputs"][0]["item_id"] == "item:1753"
    assert leather["inputs"][0]["qty"] == 1
    # leather -> body (craft, 3 leather, Crafting 63)
    body = next(p for p in idx["item:1745"] if p["output_item_id"] == "item:1135")
    assert body["level"] == 63 and body["skill"] == "Crafting"
    leather_in = next(i for i in body["inputs"] if i["item_id"] == "item:1745")
    assert leather_in["qty"] == 3
