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
