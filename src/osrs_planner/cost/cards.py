# src/osrs_planner/cost/cards.py
"""Public cost-layer output cards (pydantic), mirroring engine/cards.py style."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Route(BaseModel):
    """One acquisition channel's quote for an item, for one account family."""

    channel: str
    currency: str
    gold_cost: int | None
    gold_status: Literal["known", "unavailable"]
    inputs: list["Route"] = Field(default_factory=list)
    time_status: str = "not_estimated"
    account_allowed: bool
    source: str
    notes: list[str] = Field(default_factory=list)


class CostCard(BaseModel):
    """Family-resolved cost roll-up for a goal/item: ALL routes + a gp ranking.

    Tags the gold-cheapest via rankings["by_gold"] but NEVER names a single
    "best" field -- selection stays with the player/advisor (design spec §5).
    """

    item_id: str
    name: str
    account_family: str
    routes: list[Route] = Field(default_factory=list)
    rankings: dict[str, list[int]] = Field(
        default_factory=lambda: {"by_gold": [], "by_time": []}
    )
    notes: list[str] = Field(default_factory=list)
    gold_status: Literal["known", "partial", "unavailable"]


def rank_by_gold(routes: list[Route]) -> list[int]:
    """Indices of routes sorted ascending by gold_cost; unavailable LAST."""

    def key(i: int):
        r = routes[i]
        unavailable = r.gold_status == "unavailable" or r.gold_cost is None
        return (1 if unavailable else 0, r.gold_cost if not unavailable else 0)

    return sorted(range(len(routes)), key=key)


def roll_up_gold_status(routes: list[Route]) -> Literal["known", "partial", "unavailable"]:
    """known = all priced; unavailable = none priced / empty; partial = mixed."""
    if not routes:
        return "unavailable"
    known = sum(1 for r in routes if r.gold_status == "known")
    if known == len(routes):
        return "known"
    if known == 0:
        return "unavailable"
    return "partial"
