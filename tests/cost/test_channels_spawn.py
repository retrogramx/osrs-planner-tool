# tests/cost/test_channels_spawn.py
"""Task 8: spawn channel -- spawns.json loader + spawn ChannelRecords."""
from __future__ import annotations

import os

from osrs_planner.cost.channels import load_spawns

SPAWNS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "spawns.json"
)


def test_load_spawns_yields_spawn_records():
    records = load_spawns(SPAWNS)
    by_item = {r.item_id: r for r in records}

    hammer = by_item["item:2347"]
    assert hammer.channel == "spawn"
    assert hammer.currency == "currency:coins"
    assert hammer.amount == 0          # free spawn
    assert hammer.inputs == []         # no inputs for a spawn
    assert hammer.output_qty == 1
    assert hammer.account_allow == frozenset({"main", "ironman", "uim"})
    assert hammer.yield_ == 1
    assert hammer.time is None
