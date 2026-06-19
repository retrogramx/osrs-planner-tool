# tests/cost/test_prices.py
"""SnapshotPriceProvider over the committed data/ge_prices.json.

Real values asserted (read from data/ge_prices.json, records list):
  item:4587  (Dragon scimitar)  price.high  = 60748, high_alch = 60000
  item:30682 (Accumulation charm) price.high = None  (untraded), high_alch = 6000
  item:99999999  absent from records entirely
"""
from __future__ import annotations

import os

import pytest

from osrs_planner.cost.prices import PriceProvider, SnapshotPriceProvider

GE_PRICES = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "ge_prices.json"
)


@pytest.fixture
def provider() -> SnapshotPriceProvider:
    return SnapshotPriceProvider.from_file(GE_PRICES)


def test_is_a_price_provider(provider: SnapshotPriceProvider) -> None:
    assert isinstance(provider, PriceProvider)


def test_ge_price_returns_snapshot_high(provider: SnapshotPriceProvider) -> None:
    # Dragon scimitar price.high in the committed snapshot.
    assert provider.ge_price("item:4587") == 60748


def test_ge_price_strips_item_prefix(provider: SnapshotPriceProvider) -> None:
    # IDs are KG-style "item:<n>" in the cost layer; provider strips internally.
    assert provider.ge_price("item:4587") == provider._records[4587]["price"]["high"]


def test_ge_price_untraded_is_none(provider: SnapshotPriceProvider) -> None:
    # Accumulation charm is mapped but has no GE price (high is null).
    assert provider.ge_price("item:30682") is None


def test_ge_price_missing_item_is_none(provider: SnapshotPriceProvider) -> None:
    # Item id absent from the records list entirely.
    assert provider.ge_price("item:99999999") is None


def test_high_alch_lookup(provider: SnapshotPriceProvider) -> None:
    assert provider.high_alch("item:4587") == 60000


def test_high_alch_present_even_when_ge_price_missing(
    provider: SnapshotPriceProvider,
) -> None:
    # high_alch is on the mapping, independent of a live GE price.
    assert provider.ge_price("item:30682") is None
    assert provider.high_alch("item:30682") == 6000


def test_high_alch_missing_item_is_none(provider: SnapshotPriceProvider) -> None:
    assert provider.high_alch("item:99999999") is None


def test_abstract_base_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        PriceProvider()  # type: ignore[abstract]
