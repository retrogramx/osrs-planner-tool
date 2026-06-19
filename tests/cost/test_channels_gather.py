# tests/cost/test_channels_gather.py
"""Task 7: gather channel -- gather.json loader + gather ChannelRecords."""
from __future__ import annotations

import os

from osrs_planner.cost.channels import load_gather

GATHER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "gather.json"
)


def test_load_gather_yields_gather_records():
    records = load_gather(GATHER)
    by_item = {r.item_id: r for r in records}

    guam = by_item["item:249"]
    assert guam.channel == "gather"
    assert guam.currency == "currency:coins"
    assert guam.amount is None  # cost computed from seed/bait inputs
    assert guam.inputs == [("item:5291", 1)]
    assert guam.output_qty == 1
    assert guam.account_allow == frozenset({"main", "ironman", "uim"})
    assert guam.yield_ == 1
    assert guam.time is None
