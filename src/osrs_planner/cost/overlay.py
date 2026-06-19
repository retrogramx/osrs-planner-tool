# src/osrs_planner/cost/overlay.py
"""expand_for_account -- the public cost overlay entry (design spec §5).

Resolves a goal/item id for the account's FAMILY into a CostCard: all viable
routes for that family + a by_gold ranking. account-type divergence emerges
from price_routes' family filter, not from branching here. KG is optional in
v1; when given, notes carries the downstream-goal strategic-timing hook
(Task 9 fills it; empty otherwise). The composite-goal branch is added in
Task 9 -- this slice handles single item: goals.
"""
from __future__ import annotations

from osrs_planner.cost.cards import CostCard, rank_by_gold, roll_up_gold_status
from osrs_planner.cost.channels import ChannelRecord
from osrs_planner.cost.prices import PriceProvider
from osrs_planner.cost.routing import price_routes
from osrs_planner.engine.state import AccountState, account_family


def expand_for_account(
    goal_id: str,
    state: AccountState,
    provider: PriceProvider,
    index: dict[str, list[ChannelRecord]],
    kg=None,
) -> CostCard:
    family = account_family(state.mode)
    name = _resolve_name(goal_id, kg)

    if goal_id.startswith("item:"):
        routes = price_routes(goal_id, family, provider, index)
        notes: list[str] = []
        if not routes:
            notes.append(f"No {family}-allowed acquisition channel for {goal_id}.")
        return CostCard(
            item_id=goal_id, name=name, account_family=family, routes=routes,
            rankings={"by_gold": rank_by_gold(routes), "by_time": []},
            notes=notes, gold_status=roll_up_gold_status(routes),
        )

    raise NotImplementedError(
        f"composite goal {goal_id} not supported in the single-item slice"
    )


def _resolve_name(goal_id: str, kg) -> str:
    if kg is not None:
        node = kg.node(goal_id)
        if node is not None:
            return node.name
    return goal_id
