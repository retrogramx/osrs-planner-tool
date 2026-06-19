# src/osrs_planner/cost/channels.py
"""Channel taxonomy, the shared ChannelRecord, per-channel loaders, and the
in-memory item->channels index for the cost layer.

A "channel" is one way to acquire an item (ge, shop, craft, gather, spawn, and
the deferred drop/quest_reward/activity_reward). Every channel normalizes to one
ChannelRecord so routing.price_routes never branches per type. The index
(item_id -> [ChannelRecord]) is built in memory at load from the committed
datasets + the snapshot's set of GE-priced item ids (the ge channel is
synthetic -- priced live via PriceProvider in routing, never a dataset row).

Account-allow rule (spec §3.5): ge -> {"main"} only; every other channel ->
{"main","ironman","uim"}. Iron-gate discipline: the synthetic ge record carries
requires_ge=True / audience="main_only"; all other rows are audience="both".

This module imports nothing from prices.py at load time: build_index takes the
set of GE-priced item ids as a parameter, so channels stays independently
testable and the engine->cost one-way boundary is preserved. The convenience
build_index_from_repo is the single place a PriceProvider is touched.
"""
from __future__ import annotations

import json
import os

from pydantic import BaseModel, ConfigDict, Field

# --- taxonomy: the 8 channel names (spec §3.2) ---
CHANNELS: frozenset[str] = frozenset(
    {"ge", "shop", "craft", "gather", "spawn", "drop", "quest_reward", "activity_reward"}
)

# account-allow rule (spec §3.5)
GE_ALLOW: frozenset[str] = frozenset({"main"})
ALL_ALLOW: frozenset[str] = frozenset({"main", "ironman", "uim"})


class ChannelRecord(BaseModel):
    """One acquisition channel for one item, normalized across all 8 channels.

    Frozen/immutable so records are hashable and de-dup-safe in the index.
    amount is the direct cost in `currency` (shop) or None (ge: priced live;
    craft/gather: computed from inputs by routing). inputs is (item_id, qty)
    pairs for craft/gather; empty for buy/spawn. yield_/time are DEFINED-but-
    unused skeleton slots (spec §9). The four gate fields mirror the iron-gate
    discipline (data/validate_iron_gate.py).
    """

    model_config = ConfigDict(frozen=True)

    item_id: str
    channel: str
    currency: str
    amount: int | None = None
    inputs: list[tuple[str, int]] = Field(default_factory=list)
    output_qty: int = 1
    account_allow: frozenset[str]
    yield_: int = 1  # SKELETON
    time: None = None  # SKELETON
    source: str
    audience: str
    pricing_basis: str
    realization_channel: str
    requires_ge: bool


def ge_record(item_id: str) -> ChannelRecord:
    """Build the SYNTHETIC ge channel for an item (main-only, priced live).

    The ge channel is never a dataset row: its gold cost is provider.ge_price()
    at routing time, so amount stays None here. Iron-gate discipline: ge is
    main-only and requires_ge=True (an iron cannot use the GE).
    """
    return ChannelRecord(
        item_id=item_id,
        channel="ge",
        currency="currency:coins",
        amount=None,
        account_allow=GE_ALLOW,
        source="Grand Exchange",
        audience="main_only",
        pricing_basis="ge",
        realization_channel="ge",
        requires_ge=True,
    )


def load_shop(path: str) -> list[ChannelRecord]:
    """Load shop channel records from data/shop_prices.json.

    Shop is allowed for all three account families (spec §3.5). The dataset's
    gate fields are carried through verbatim; shop rows are audience="both",
    requires_ge=False by curation.
    """
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    records: list[ChannelRecord] = []
    for r in doc["records"]:
        records.append(
            ChannelRecord(
                item_id=r["item_id"],
                channel="shop",
                currency=r["currency"],
                amount=r["amount"],
                account_allow=ALL_ALLOW,
                source=r["shop"],
                audience=r["audience"],
                pricing_basis=r["pricing_basis"],
                realization_channel=r["realization_channel"],
                requires_ge=r["requires_ge"],
            )
        )
    return records


def load_recipes(path: str) -> list[ChannelRecord]:
    """Load data/recipes.json into `craft` ChannelRecords.

    Cost is computed from inputs at routing time (amount=None). Inputs are
    (item_id, qty) tuples; output_qty divides the summed input cost.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    records: list[ChannelRecord] = []
    for r in payload["records"]:
        records.append(
            ChannelRecord(
                item_id=r["output_item_id"],
                channel="craft",
                currency=r["currency"],
                amount=None,
                inputs=[(i["item_id"], i["qty"]) for i in r["inputs"]],
                output_qty=r["output_qty"],
                account_allow=frozenset({"main", "ironman", "uim"}),
                source=r["source"],
                audience=r["audience"],
                pricing_basis=r["pricing_basis"],
                realization_channel=r["realization_channel"],
                requires_ge=r["requires_ge"],
            )
        )
    return records


def load_gather(path: str) -> list[ChannelRecord]:  # replaced in Task 7
    return []


def load_spawns(path: str) -> list[ChannelRecord]:  # replaced in Task 8
    return []


def build_index(
    *,
    shop_records: list[ChannelRecord] | None = None,
    recipe_records: list[ChannelRecord] | None = None,
    gather_records: list[ChannelRecord] | None = None,
    spawn_records: list[ChannelRecord] | None = None,
    ge_item_ids: frozenset[str] = frozenset(),
    extra_records: list[ChannelRecord] | None = None,
) -> dict[str, list[ChannelRecord]]:
    """Build the in-memory item_id -> [ChannelRecord] acquisition index.

    Merges dataset-backed channel records (shop now; craft/gather/spawn wired
    below as later tasks add their loaders) with synthetic `ge` records for
    every GE-priced item id the caller passes (the snapshot's keys). Built
    fresh in memory at load -- there is no committed derived artifact, so no
    freshness guard is needed; data/validate_cost.py (Task 10) is the gate.
    """
    index: dict[str, list[ChannelRecord]] = {}

    def add(rec: ChannelRecord) -> None:
        index.setdefault(rec.item_id, []).append(rec)

    for group in (
        shop_records,
        recipe_records,
        gather_records,
        spawn_records,
        extra_records,
    ):
        for rec in group or []:
            add(rec)
    for item_id in ge_item_ids:
        add(ge_record(item_id))

    return index


def build_index_from_repo(repo_root: str, provider) -> dict[str, list[ChannelRecord]]:
    """Load every committed channel dataset + derive ge_item_ids from the
    provider's snapshot, then call build_index.

    The single place a PriceProvider is touched at index-build time. Datasets
    that do not yet exist (later tasks add recipes/gather/spawns) are skipped.
    """
    data = os.path.join(repo_root, "data")

    def _maybe(loader, fname):
        p = os.path.join(data, fname)
        return loader(p) if os.path.exists(p) else []

    shop = _maybe(load_shop, "shop_prices.json")
    recipes = _maybe(load_recipes, "recipes.json")
    gather = _maybe(load_gather, "gather.json")
    spawns = _maybe(load_spawns, "spawns.json")
    ge_item_ids = frozenset(f"item:{iid}" for iid in provider._records.keys())
    return build_index(
        shop_records=shop,
        recipe_records=recipes,
        gather_records=gather,
        spawn_records=spawns,
        ge_item_ids=ge_item_ids,
    )
