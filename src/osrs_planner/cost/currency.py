# src/osrs_planner/cost/currency.py
"""Currency reference table (design spec §3.1).

A currency is a cost DENOMINATION, not a prerequisite — a reference table, not
a KG node-kind (research/currency-model.md). ``self_earned_only`` is the
convergence mechanism: a currency with no market has no cheaper main route, so
items priced in it converge main-vs-iron structurally.

``earn_rate_per_hour`` is a wired-but-empty skeleton in v1 (design spec §9);
it stays ``None`` until skill/minigame rate baselines land.
"""
from __future__ import annotations

import json

from pydantic import BaseModel


class Currency(BaseModel):
    """One currency / cost denomination. Fields mirror design spec §3.1."""

    id: str
    name: str
    category: str  # physical_tradeable | physical_untradeable | physical_fare | virtual
    is_item: bool
    ge_tradeable: bool
    observable: str  # hiscores | plugin | plugin_or_unknown | none
    source_activity: str | None
    earn_rate_per_hour: int | None = None  # SKELETON (null in v1)
    self_earned_only: bool
    example_sinks: list[dict]


def load_currencies(path: str) -> dict[str, Currency]:
    """Load ``data/currencies.json`` -> ``{currency_id: Currency}``."""
    with open(path, encoding="utf-8") as f:
        envelope = json.load(f)
    return {rec["id"]: Currency(**rec) for rec in envelope["records"]}
