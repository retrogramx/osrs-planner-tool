from osrs_planner.cost.routing import price_routes


def test_price_routes_is_importable():
    assert callable(price_routes)


import pytest

from osrs_planner.cost.channels import ChannelRecord
from osrs_planner.cost.prices import PriceProvider


class _FakeProvider(PriceProvider):
    """Returns the REAL data/ge_prices.json high for the scimitar (60748)."""

    def __init__(self, ge: dict[str, int]):
        self._ge = ge

    def ge_price(self, item_id: str) -> int | None:
        return self._ge.get(item_id)

    def high_alch(self, item_id: str) -> int | None:
        return None


SCIMITAR = "item:4587"


def _scimitar_ge_record() -> ChannelRecord:
    return ChannelRecord(
        item_id=SCIMITAR, channel="ge", currency="currency:coins",
        amount=None, inputs=[], output_qty=1,
        account_allow=frozenset({"main"}), source="Grand Exchange",
        audience="main_only", pricing_basis="ge", realization_channel="ge",
        requires_ge=True,
    )


def _scimitar_shop_record() -> ChannelRecord:
    return ChannelRecord(
        item_id=SCIMITAR, channel="shop", currency="currency:coins",
        amount=100000, inputs=[], output_qty=1,
        account_allow=frozenset({"main", "ironman", "uim"}),
        source="Daga's Scimitar Smithy",
        audience="both", pricing_basis="shop", realization_channel="shop",
        requires_ge=False,
    )


@pytest.fixture
def scimitar_index() -> dict[str, list[ChannelRecord]]:
    return {SCIMITAR: [_scimitar_ge_record(), _scimitar_shop_record()]}


@pytest.fixture
def provider() -> _FakeProvider:
    return _FakeProvider({"item:4587": 60748})


def test_main_gets_ge_and_shop_routes(scimitar_index, provider):
    routes = price_routes(SCIMITAR, "main", provider, scimitar_index)
    assert {r.channel for r in routes} == {"ge", "shop"}
    ge = next(r for r in routes if r.channel == "ge")
    shop = next(r for r in routes if r.channel == "shop")
    assert ge.gold_cost == 60748
    assert ge.gold_status == "known"
    assert ge.currency == "currency:coins"
    assert ge.account_allowed is True
    assert shop.gold_cost == 100000
    assert shop.gold_status == "known"
    assert shop.currency == "currency:coins"


def test_ironman_has_no_ge_route(scimitar_index, provider):
    routes = price_routes(SCIMITAR, "ironman", provider, scimitar_index)
    assert {r.channel for r in routes} == {"shop"}
    shop = routes[0]
    assert shop.gold_cost == 100000
    assert shop.gold_status == "known"
    assert shop.account_allowed is True


from osrs_planner.engine.state import account_family


def test_family_is_engine_account_family(scimitar_index, provider):
    fam = account_family("hardcore_ironman")  # collapses to "ironman"
    assert fam == "ironman"
    routes = price_routes(SCIMITAR, fam, provider, scimitar_index)
    assert {r.channel for r in routes} == {"shop"}


def _spawn_record(item_id: str) -> ChannelRecord:
    return ChannelRecord(
        item_id=item_id, channel="spawn", currency="currency:coins",
        amount=0, inputs=[], output_qty=1,
        account_allow=frozenset({"main", "ironman", "uim"}),
        source="Free item spawn", audience="both", pricing_basis="spawn",
        realization_channel="spawn", requires_ge=False,
    )


def test_spawn_is_zero_gold():
    item = "item:1965"
    index = {item: [_spawn_record(item)]}
    routes = price_routes(item, "main", _FakeProvider({}), index)
    assert len(routes) == 1
    assert routes[0].channel == "spawn"
    assert routes[0].gold_cost == 0
    assert routes[0].gold_status == "known"


def test_ge_missing_price_is_unavailable():
    index = {SCIMITAR: [_scimitar_ge_record()]}
    routes = price_routes(SCIMITAR, "main", _FakeProvider({}), index)
    assert len(routes) == 1
    ge = routes[0]
    assert ge.channel == "ge"
    assert ge.gold_cost is None
    assert ge.gold_status == "unavailable"


def test_unknown_item_returns_empty(provider):
    assert price_routes("item:999999", "main", provider, {}) == []


def test_self_referential_craft_does_not_recurse_forever():
    item = "item:777"
    rec = ChannelRecord(
        item_id=item, channel="craft", currency="currency:coins",
        amount=None, inputs=[(item, 1)], output_qty=1,
        account_allow=frozenset({"main", "ironman", "uim"}),
        source="craft:self", audience="both", pricing_basis="inputs",
        realization_channel="craft", requires_ge=False,
    )
    index = {item: [rec]}
    routes = price_routes(item, "main", _FakeProvider({}), index)
    assert len(routes) == 1
    assert routes[0].channel == "craft"
    assert routes[0].gold_status == "unavailable"


import os

from osrs_planner.cost.prices import SnapshotPriceProvider

_GE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ge_prices.json")


def test_main_ge_route_matches_real_snapshot(scimitar_index):
    real = SnapshotPriceProvider.from_file(_GE)
    routes = price_routes(SCIMITAR, "main", real, scimitar_index)
    ge = next(r for r in routes if r.channel == "ge")
    # data/ge_prices.json records[item_id=4587].price.high == 60748
    assert ge.gold_cost == 60748
    assert ge.gold_status == "known"


import pathlib


def test_engine_does_not_import_cost():
    engine_dir = pathlib.Path(__file__).resolve().parents[2] / "src" / "osrs_planner" / "engine"
    offenders = []
    for py in engine_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "osrs_planner.cost" in text or "from ..cost" in text or "from .cost" in text:
            offenders.append(str(py))
    assert offenders == [], f"engine imports cost: {offenders}"
