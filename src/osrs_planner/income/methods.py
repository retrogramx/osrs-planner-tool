# src/osrs_planner/income/methods.py
"""Normalized money-making method model (income design §3).

One ``MethodRecord`` (frozen pydantic) unifies the two source datasets
(data/money_making.json: 377 main, HTML requirements; data/ironman_money_making.json:
49 iron, native structured requirements). gp/hr is COMPUTED at query time from
``outputs x PriceProvider`` (realize.py) -- the stored ``gp_hr`` is NOT trusted.

IDs are KG-style strings: methods ``method:<slug>``, items ``item:<n>``,
quests ``quest:<slug>``, skills ``skill:<name>``.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Flow(BaseModel):
    """One output or input stream of a method, per hour.

    ``item_id`` is a KG-style ``"item:<n>"`` string, or ``None`` for a pure
    coins flow (``is_coins=True``). A non-coin flow with ``item_id=None`` is an
    un-resolvable / aggregate stream (e.g. the "Gem drop table" pseudo-output)
    that realize.py treats as unpriceable. ``qty_per_hour`` is ``None`` when the
    rate is not modelled (realize.py surfaces that as ``unknown``, never 0).
    """

    item_id: Optional[str] = None
    is_coins: bool = False
    qty_per_hour: Optional[float] = None


class Requirements(BaseModel):
    """Structured requirements feeding the engine condition-evaluator (filter.py).

    ``skills`` maps a KG ``"skill:<name>"`` id to a required level; ``quests``
    is a list of ``"quest:<slug>"`` ids; ``items`` is a list of ``"item:<n>"``
    ids (item gates stay UNKNOWN until bank data -- absence != zero).
    """

    skills: dict[str, int] = Field(default_factory=dict)
    quests: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)


class MethodRecord(BaseModel, frozen=True):
    """A single money-making method, normalized across both datasets (§3).

    Frozen: loaded once and shared across requests (like the KG static value
    types). ``stage`` is a SOFT hint only -- the requirement check (filter.py),
    not this tag, decides doability. ``processing_dependent`` flags methods whose
    iron income needs a processing chain not yet covered, so v1 marks them
    ``gp_hr_status=unknown`` rather than under-counting.
    """

    id: str
    name: str
    category: str
    members: bool
    audience: str
    requires_ge: bool
    iron_eligible: bool
    realization_channel: str
    outputs: list[Flow] = Field(default_factory=list)
    inputs: list[Flow] = Field(default_factory=list)
    requirements: Requirements = Field(default_factory=Requirements)
    stage: Optional[str] = None
    tags: dict = Field(default_factory=dict)
    processing_dependent: bool = False
    net_sign: Literal["earner", "sink"]
    source: str
    url: str
    accessed_at: str
