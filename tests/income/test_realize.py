"""realize_income (v1 RAW realization, pre-processing-chain) over REAL prices."""
from __future__ import annotations

import math
import os

import pytest

from osrs_planner.income.methods import Flow, MethodRecord, Requirements
from osrs_planner.income.realize import realize_income
from osrs_planner.cost.prices import SnapshotPriceProvider

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GE_PRICES = os.path.join(REPO, "data", "ge_prices.json")

GREEN_HIDE = "item:1753"  # high_alch 81, ge.high 1557 (read at runtime)


@pytest.fixture(scope="module")
def provider():
    return SnapshotPriceProvider.from_file(GE_PRICES)


def _ge(provider, item_id):
    v = provider.ge_price(item_id)
    assert v is not None, f"snapshot missing ge price for {item_id}"
    return v


def _ha(provider, item_id):
    v = provider.high_alch(item_id)
    assert v is not None, f"snapshot missing high_alch for {item_id}"
    return v


def _green_dragons_method(**over):
    base = dict(
        id="method:killing-green-dragons",
        name="Killing green dragons",
        category="Combat/Mid",
        members=True,
        audience="main",
        requires_ge=False,
        iron_eligible=True,
        realization_channel="mixed",
        outputs=[
            Flow(item_id=GREEN_HIDE, is_coins=False, qty_per_hour=1000.0),
            Flow(item_id=None, is_coins=True, qty_per_hour=50000.0),
        ],
        inputs=[],
        requirements=Requirements(skills={}, quests=[], items=[]),
        stage=None, tags={}, processing_dependent=False, net_sign="earner",
        source="OSRS Wiki MMG", url="https://x", accessed_at="2026-06-19",
    )
    base.update(over)
    return MethodRecord(**base)


def test_main_realizes_outputs_at_ge_value(provider):
    gp_hr, status = realize_income(_green_dragons_method(), "main", provider, recipe_index={}, account_skills={})
    assert status == "known"
    assert gp_hr == 1000 * _ge(provider, GREEN_HIDE) + 50000


def test_ironman_realizes_raw_high_alch(provider):
    # No recipe_index -> no chain available; the hide falls to raw High-Alch.
    gp_hr, status = realize_income(_green_dragons_method(), "ironman", provider, recipe_index={}, account_skills={})
    assert status == "known"
    assert gp_hr == 1000 * _ha(provider, GREEN_HIDE) + 50000


def test_uim_realizes_same_as_ironman(provider):
    iron, _ = realize_income(_green_dragons_method(), "ironman", provider, recipe_index={}, account_skills={})
    uim, _ = realize_income(_green_dragons_method(), "uim", provider, recipe_index={}, account_skills={})
    assert uim == iron


def test_main_and_ironman_differ_and_main_higher(provider):
    main, _ = realize_income(_green_dragons_method(), "main", provider, recipe_index={}, account_skills={})
    iron, _ = realize_income(_green_dragons_method(), "ironman", provider, recipe_index={}, account_skills={})
    assert main != iron
    assert main > iron  # GE hide (~1557) >> raw alch (81)


def test_main_subtracts_ge_input_cost(provider):
    base = _green_dragons_method()
    with_input = base.model_copy(update={"inputs": [Flow(item_id=GREEN_HIDE, is_coins=False, qty_per_hour=10.0)]})
    gp_no, _ = realize_income(base, "main", provider, recipe_index={}, account_skills={})
    gp_with, _ = realize_income(with_input, "main", provider, recipe_index={}, account_skills={})
    assert gp_with == gp_no - 10 * _ge(provider, GREEN_HIDE)


def test_unpriceable_output_is_unknown(provider):
    m = _green_dragons_method(outputs=[Flow(item_id="item:99999999", is_coins=False, qty_per_hour=1.0)])
    gp_hr, status = realize_income(m, "main", provider, recipe_index={}, account_skills={})
    assert status == "unknown" and gp_hr is None


def test_null_rate_output_is_unknown(provider):
    m = _green_dragons_method(outputs=[Flow(item_id=GREEN_HIDE, is_coins=False, qty_per_hour=None)])
    gp_hr, status = realize_income(m, "main", provider, recipe_index={}, account_skills={})
    assert status == "unknown" and gp_hr is None


def test_nan_rate_output_is_unknown(provider):
    m = _green_dragons_method(outputs=[Flow(item_id=GREEN_HIDE, is_coins=False, qty_per_hour=float("nan"))])
    gp_hr, status = realize_income(m, "main", provider, recipe_index={}, account_skills={})
    assert status == "unknown" and gp_hr is None


def test_processing_dependent_iron_unknown_main_known(provider):
    m = _green_dragons_method(processing_dependent=True)
    iron_gp, iron_status = realize_income(m, "ironman", provider, recipe_index={}, account_skills={})
    assert iron_status == "unknown" and iron_gp is None
    main_gp, main_status = realize_income(m, "main", provider, recipe_index={}, account_skills={})
    assert main_status == "known" and main_gp is not None
