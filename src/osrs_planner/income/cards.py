# src/osrs_planner/income/cards.py
"""Public income-layer output cards (pydantic), twin of cost/cards.py.

rank_by_gp_hr sorts DESCENDING (higher gp/hr first); unknown-rate methods and
net_sign=="sink" methods sort LAST. NEVER a single "best"/"recommended" field --
the card lists all viable methods ranked; selection stays with the player/advisor.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Method(BaseModel):
    """One money-making method, realized + classified for one account family."""

    id: str
    name: str
    category: str
    members: bool
    gp_hr: int | None  # coins-only gp/hr for THIS family; None when status unknown
    gp_hr_status: str  # "known" | "unknown"
    realization_channel: str
    requirements_status: dict = Field(default_factory=dict)  # {status, missing[], unverified[]}
    tags: dict = Field(default_factory=dict)
    net_sign: str  # "earner" | "sink"
    outputs_summary: str = ""
    source: str
    url: str


class IncomeCard(BaseModel):
    """Family-resolved ranked roll-up of money-making methods.

    rankings["by_gp_hr"] holds indices into `methods`. NEVER names a single best
    -- mirrors CostCard.rankings (structural twin for the Option-2 hand-off).
    """

    account_family: str
    methods: list[Method] = Field(default_factory=list)
    rankings: dict[str, list[int]] = Field(default_factory=lambda: {"by_gp_hr": []})
    notes: list[str] = Field(default_factory=list)


# T7 refines this with a status tier; v1 ranks earners (known gp) first, then
# unknown gp, then sinks. STATUS_RANK keys are tolerated-absent in v1 (placeholder
# requirements_status has status "doable_now").
_STATUS_RANK = {"doable_now": 0, "future_gated": 1, "unverified": 1}


def rank_by_gp_hr(methods: list[Method]) -> list[int]:
    """Indices DESCENDING by gp_hr, with status + sink/unknown tiers.

    Sort key (ascending tuple -> lower = ranked earlier):
      tier 0: known gp & earner & status doable_now
      tier 1: known gp & earner & status future_gated/unverified
      tier 2: unknown gp_hr (any status, earner) -- no rankable number
      tier 3: net_sign == "sink" -- never an earner ranking
    Within a tier, higher gp_hr first (negated for ascending). Ties -> id.
    """

    def key(i: int):
        m = methods[i]
        if m.net_sign == "sink":
            tier = 3
        elif m.gp_hr is None or m.gp_hr_status != "known":
            tier = 2
        else:
            tier = _STATUS_RANK.get(m.requirements_status.get("status"), 0)
        gp = m.gp_hr if m.gp_hr is not None else 0
        return (tier, -gp, m.id)

    return sorted(range(len(methods)), key=key)
