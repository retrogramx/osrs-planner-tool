#!/usr/bin/env python3
"""Cost-layer demo: golden goals x account family (read-only over committed data).

Run: ./venv/bin/python scripts/cost_demo.py
Prints the full CostCard route set + by_gold ranking for each golden goal under
both a main and an ironman -- the flagship divergences, no auto-pick.
"""
from __future__ import annotations

import os

from osrs_planner.cost.channels import build_index_from_repo
from osrs_planner.cost.overlay import expand_for_account
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.state import AccountState

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOALS = [
    ("Dragon scimitar", "item:4587"),
    ("Tzhaar-ket-om (obby maul)", "item:6528"),
    ("Attack potion(3)", "item:121"),
    ("Voidwaker", "item:27690"),
    ("Full Infinity", "gear_loadout_goal:infinity"),
]


def is_coin_route(r):
    """A route with a coin-comparable figure (gold_cost is coins-only; None for
    non-coin or unpriced routes -- spec §11)."""
    return r.gold_cost is not None


def fmt_gold(r):
    # Coin route: show the coin figure. Non-coin but known: show amount +
    # currency, flagged (non-coin) so it is never read as a coin price (spec
    # §11). Otherwise: status only (unavailable / unpriced).
    if is_coin_route(r):
        return f"{r.gold_cost:,} {r.currency}"
    if r.gold_status == "known" and r.amount is not None:
        return f"{r.amount:,} {r.currency} (non-coin)"
    return f"{r.gold_status} ({r.currency})"


def main():
    provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
    kg = JsonKGStore.from_dir(os.path.join(REPO, "kg"))
    index = build_index_from_repo(REPO, provider)
    for name, goal_id in GOALS:
        print(f"\n=== {name} ({goal_id}) ===")
        for mode in ("main", "ironman"):
            card = expand_for_account(goal_id, AccountState(mode=mode), provider, index, kg=kg)
            print(f"  [{mode}] gold_status={card.gold_status} routes={len(card.routes)}")
            for rank, i in enumerate(card.rankings["by_gold"]):
                r = card.routes[i]
                # "cheapest gold" only for the rank-0 route that actually has a
                # coin gold_cost -- a non-coin route (gold_cost None) is never
                # labelled cheapest gold even if it sorts first (spec §11).
                tag = " (cheapest gold)" if rank == 0 and is_coin_route(r) else ""
                extra = f"  inputs={len(r.inputs)}" if r.inputs else ""
                print(f"    - {r.channel:>5}: {fmt_gold(r)}{extra}{tag}")
            if card.notes:
                print(f"    notes (downstream goals): {card.notes}")


if __name__ == "__main__":
    main()
