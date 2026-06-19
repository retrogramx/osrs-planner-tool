import os

import pytest

from osrs_planner.cost.overlay import expand_for_account
from osrs_planner.cost.channels import ChannelRecord
from osrs_planner.cost.prices import PriceProvider, SnapshotPriceProvider
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.state import AccountState

SCIMITAR = "item:4587"

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class _FakeProvider(PriceProvider):
    def __init__(self, ge):
        self._ge = ge

    def ge_price(self, item_id):
        return self._ge.get(item_id)

    def high_alch(self, item_id):
        return None


def _ge_rec():
    return ChannelRecord(
        item_id=SCIMITAR, channel="ge", currency="currency:coins",
        amount=None, inputs=[], output_qty=1,
        account_allow=frozenset({"main"}), source="Grand Exchange",
        audience="main_only", pricing_basis="ge", realization_channel="ge",
        requires_ge=True,
    )


def _shop_rec():
    return ChannelRecord(
        item_id=SCIMITAR, channel="shop", currency="currency:coins",
        amount=100000, inputs=[], output_qty=1,
        account_allow=frozenset({"main", "ironman", "uim"}),
        source="Daga's Scimitar Smithy",
        audience="both", pricing_basis="shop", realization_channel="shop",
        requires_ge=False,
    )


@pytest.fixture
def index():
    return {SCIMITAR: [_ge_rec(), _shop_rec()]}


@pytest.fixture
def provider():
    return _FakeProvider({"item:4587": 60748})


def test_main_card_not_collapsed_ge_is_cheapest(index, provider):
    card = expand_for_account(SCIMITAR, AccountState(mode="main"), provider, index)
    assert card.item_id == SCIMITAR
    assert card.account_family == "main"
    assert len(card.routes) >= 2  # NOT collapsed to a single winner
    assert {r.channel for r in card.routes} == {"ge", "shop"}
    best_idx = card.rankings["by_gold"][0]
    assert card.routes[best_idx].channel == "ge"  # 60748 < 100000
    assert card.routes[best_idx].gold_cost == 60748
    assert card.gold_status == "known"
    assert "best" not in card.model_dump()


def test_ironman_card_shop_only_no_ge(index, provider):
    card = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, index)
    assert card.account_family == "ironman"
    assert {r.channel for r in card.routes} == {"shop"}
    best_idx = card.rankings["by_gold"][0]
    assert card.routes[best_idx].channel == "shop"
    assert card.routes[best_idx].gold_cost == 100000
    assert card.gold_status == "known"


def test_hardcore_ironman_collapses_to_ironman(index, provider):
    card = expand_for_account(SCIMITAR, AccountState(mode="hardcore_ironman"), provider, index)
    assert card.account_family == "ironman"
    assert {r.channel for r in card.routes} == {"shop"}


def test_no_allowed_channel_is_unavailable(provider):
    idx = {SCIMITAR: [_ge_rec()]}  # only a ge channel -> ironman has nothing
    card = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, idx)
    assert card.routes == []
    assert card.rankings["by_gold"] == []
    assert card.gold_status == "unavailable"
    assert card.notes  # explanatory note present


def test_flagship_divergence_real_data(index):
    provider = SnapshotPriceProvider.from_file(os.path.join(_REPO, "data", "ge_prices.json"))
    kg = JsonKGStore.from_dir(os.path.join(_REPO, "kg"))

    main = expand_for_account(SCIMITAR, AccountState(mode="main"), provider, index, kg=kg)
    iron = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, index, kg=kg)

    assert main.name == "Dragon scimitar"  # real kg/nodes.json item:4587
    m0 = main.routes[main.rankings["by_gold"][0]]
    assert m0.channel == "ge"
    assert m0.gold_cost == 60748  # real records[4587].price.high
    assert {r.channel for r in iron.routes} == {"shop"}
    assert iron.routes[iron.rankings["by_gold"][0]].gold_cost == 100000
