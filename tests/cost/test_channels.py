# tests/cost/test_channels.py
"""Tests for osrs_planner.cost.channels — taxonomy, ChannelRecord, loaders, index."""
from __future__ import annotations

import json
import os

import pytest

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
SHOP_PRICES = os.path.join(DATA, "shop_prices.json")


def test_shop_prices_dataset_has_proof_rows_with_gate_fields():
    with open(SHOP_PRICES, encoding="utf-8") as f:
        doc = json.load(f)
    by_item = {r["item_id"]: r for r in doc["records"]}

    scim = by_item["item:4587"]
    assert scim["amount"] == 100000
    assert scim["currency"] == "currency:coins"
    assert scim["shop"] == "Daga's Scimitar Smithy"

    maul = by_item["item:6528"]
    assert maul["amount"] == 75001
    assert maul["currency"] == "currency:tokkul"

    for r in doc["records"]:
        assert r["audience"] == "both"
        assert r["requires_ge"] is False
        for f in ("audience", "pricing_basis", "realization_channel", "requires_ge"):
            assert f in r, f"shop row {r['item_id']} missing gate field {f}"


def test_channel_taxonomy_is_the_eight_strings():
    from osrs_planner.cost.channels import CHANNELS

    assert CHANNELS == frozenset(
        {"ge", "shop", "craft", "gather", "spawn", "drop", "quest_reward", "activity_reward"}
    )


def test_channel_record_shape_and_defaults():
    from osrs_planner.cost.channels import ChannelRecord

    rec = ChannelRecord(
        item_id="item:4587",
        channel="shop",
        currency="currency:coins",
        amount=100000,
        account_allow=frozenset({"main", "ironman", "uim"}),
        source="Daga's Scimitar Smithy",
        audience="both",
        pricing_basis="shop",
        realization_channel="shop",
        requires_ge=False,
    )
    assert rec.item_id == "item:4587"
    assert rec.channel == "shop"
    assert rec.amount == 100000
    # skeleton fields DEFINED-but-unused with their defaults
    assert rec.inputs == []
    assert rec.output_qty == 1
    assert rec.yield_ == 1
    assert rec.time is None
    # frozen / immutable
    with pytest.raises(Exception):
        rec.amount = 5


def test_load_shop_records_from_dataset():
    from osrs_planner.cost.channels import ALL_ALLOW, load_shop

    recs = load_shop(SHOP_PRICES)
    by_item = {r.item_id: r for r in recs}

    scim = by_item["item:4587"]
    assert scim.channel == "shop"
    assert scim.amount == 100000
    assert scim.currency == "currency:coins"
    assert scim.source == "Daga's Scimitar Smithy"
    assert scim.account_allow == ALL_ALLOW
    assert scim.requires_ge is False
    assert scim.audience == "both"

    maul = by_item["item:6528"]
    assert maul.amount == 75001
    assert maul.currency == "currency:tokkul"


def test_ge_channel_factory_is_main_only():
    from osrs_planner.cost.channels import GE_ALLOW, ge_record

    rec = ge_record("item:4587")
    assert rec.channel == "ge"
    assert rec.currency == "currency:coins"
    assert rec.amount is None  # priced live via PriceProvider in routing
    assert rec.account_allow == GE_ALLOW
    assert rec.account_allow == frozenset({"main"})  # MAIN ONLY
    assert rec.requires_ge is True
    assert rec.audience == "main_only"
    assert rec.pricing_basis == "ge"
    assert rec.realization_channel == "ge"


def test_build_index_yields_ge_and_shop_for_scimitar():
    from osrs_planner.cost.channels import build_index, load_shop

    shop = load_shop(SHOP_PRICES)
    ge_ids = frozenset({"item:4587", "item:6528"})
    index = build_index(shop_records=shop, ge_item_ids=ge_ids)

    scim_channels = {r.channel for r in index["item:4587"]}
    assert scim_channels == {"ge", "shop"}

    by_channel = {r.channel: r for r in index["item:4587"]}
    assert by_channel["ge"].account_allow == frozenset({"main"})
    assert by_channel["shop"].account_allow == frozenset({"main", "ironman", "uim"})
    assert by_channel["shop"].amount == 100000
    assert by_channel["shop"].currency == "currency:coins"


def test_build_index_yields_tokkul_shop_for_obby_maul():
    from osrs_planner.cost.channels import build_index, load_shop

    index = build_index(
        shop_records=load_shop(SHOP_PRICES),
        ge_item_ids=frozenset({"item:4587", "item:6528"}),
    )
    by_channel = {r.channel: r for r in index["item:6528"]}
    assert by_channel["shop"].currency == "currency:tokkul"
    assert by_channel["shop"].amount == 75001
    assert by_channel["ge"].account_allow == frozenset({"main"})


def test_build_index_ge_only_when_not_in_shop():
    from osrs_planner.cost.channels import build_index, load_shop

    index = build_index(
        shop_records=load_shop(SHOP_PRICES),
        ge_item_ids=frozenset({"item:4587", "item:6528", "item:1215"}),
    )
    assert {r.channel for r in index["item:1215"]} == {"ge"}


def test_build_index_shop_only_when_not_ge_priced():
    from osrs_planner.cost.channels import build_index, load_shop

    index = build_index(
        shop_records=load_shop(SHOP_PRICES),
        ge_item_ids=frozenset(),
    )
    assert {r.channel for r in index["item:4587"]} == {"shop"}
    assert {r.channel for r in index["item:6528"]} == {"shop"}


def test_build_index_from_repo_real_datasets():
    # The convenience loader builds the whole index from committed data + a
    # provider's snapshot (ge_item_ids derived from the provider).
    from osrs_planner.cost.channels import build_index_from_repo
    from osrs_planner.cost.prices import SnapshotPriceProvider

    repo = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    provider = SnapshotPriceProvider.from_file(os.path.join(repo, "data", "ge_prices.json"))
    index = build_index_from_repo(repo, provider)
    # scimitar (GE-priced + shop row) yields both channels
    assert {r.channel for r in index["item:4587"]} == {"ge", "shop"}
