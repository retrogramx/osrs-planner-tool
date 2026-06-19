# tests/cost/test_currency.py
"""Currency reference-table model + loader (design spec §3.1).

A currency is a cost DENOMINATION, not a prerequisite. The committed seed
covers coins (universal baseline) plus the non-coin currencies the golden-set
channels reference (tokkul for the obby maul) + a couple more from
research/currency-model.md so the category taxonomy is exercised.
"""
from __future__ import annotations

import os

import pytest

from osrs_planner.cost.currency import Currency, load_currencies

CURRENCIES = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "currencies.json"
)


@pytest.fixture
def currencies() -> dict[str, Currency]:
    return load_currencies(CURRENCIES)


def test_load_returns_dict_keyed_by_id(currencies: dict[str, Currency]) -> None:
    assert "currency:coins" in currencies
    assert "currency:tokkul" in currencies
    for cid, cur in currencies.items():
        assert cur.id == cid  # key == record id


def test_values_are_currency_models(currencies: dict[str, Currency]) -> None:
    assert all(isinstance(c, Currency) for c in currencies.values())


def test_coins_is_tradeable_universal(currencies: dict[str, Currency]) -> None:
    coins = currencies["currency:coins"]
    assert coins.name == "Coins"
    assert coins.category == "physical_tradeable"
    assert coins.is_item is True
    assert coins.ge_tradeable is True
    assert coins.self_earned_only is False  # universal; main vs iron diverge in HOW


def test_tokkul_is_self_earned_only(currencies: dict[str, Currency]) -> None:
    tokkul = currencies["currency:tokkul"]
    assert tokkul.category == "physical_untradeable"
    assert tokkul.is_item is True
    assert tokkul.ge_tradeable is False
    assert tokkul.self_earned_only is True  # no market -> converges main vs iron
    assert tokkul.source_activity == "activity:tzhaar"


def test_tokkul_has_obby_maul_sink(currencies: dict[str, Currency]) -> None:
    # research/currency-model.md: Tzhaar-ket-om = 75,001 Tokkul at the TzHaar store.
    tokkul = currencies["currency:tokkul"]
    sinks = {s["item"]: s for s in tokkul.example_sinks}
    assert "item:6528" in sinks
    assert sinks["item:6528"]["amount"] == 75001


def test_all_required_fields_present(currencies: dict[str, Currency]) -> None:
    required = {
        "id", "name", "category", "is_item", "ge_tradeable", "observable",
        "source_activity", "earn_rate_per_hour", "self_earned_only",
        "example_sinks",
    }
    for cur in currencies.values():
        assert required <= set(cur.model_dump().keys())


def test_earn_rate_is_skeleton_null(currencies: dict[str, Currency]) -> None:
    # earn_rate_per_hour is a wired-but-empty skeleton in v1 (design spec §9).
    assert all(c.earn_rate_per_hour is None for c in currencies.values())


def test_category_values_are_in_taxonomy(currencies: dict[str, Currency]) -> None:
    allowed = {
        "physical_tradeable", "physical_untradeable", "physical_fare", "virtual",
    }
    assert all(c.category in allowed for c in currencies.values())


def test_observable_values_are_in_taxonomy(currencies: dict[str, Currency]) -> None:
    allowed = {"hiscores", "plugin", "plugin_or_unknown", "none"}
    assert all(c.observable in allowed for c in currencies.values())
