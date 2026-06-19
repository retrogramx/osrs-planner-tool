# src/osrs_planner/income/realize.py
"""Per-family income realization (v1 RAW realization).

realize_income(method, family, provider, recipe_index) -> (gp_hr, gp_hr_status)
computes a method's COINS-ONLY gp/hr at query time, the inverse of cost's price
walk. v1 ships the RAW realization:

  main      -> sum over outputs of GE value (provider.ge_price; coins face) * rate
               MINUS sum over inputs of GE cost * rate.
  iron/uim  -> sum over outputs of (coins face) + High-Alch of the RAW drop
               (provider.high_alch) * rate. The multi-step tan->craft->alch walk
               lands in T5 (best_realization), wired via recipe_index.

NEVER fabricate (design §4): a missing price, a null/NaN rate, or (for iron) a
processing_dependent method whose chain isn't covered -> gp_hr_status="unknown",
gp_hr=None. A non-coin output that can't be valued in coins makes the whole
method unknown (no partial fabricated number). recipe_index is accepted now (the
T5 seam) but UNUSED in v1 raw realization.

family is one of {"main","ironman","uim"} (from engine.state.account_family).
"""
from __future__ import annotations

import math

from osrs_planner.cost.prices import PriceProvider
from osrs_planner.income.methods import Flow, MethodRecord

_IRON_FAMILIES = frozenset({"ironman", "uim"})


def _bad_rate(rate) -> bool:
    """A rate is unusable when absent or NaN (a null/NaN rate = not modelled)."""
    return rate is None or (isinstance(rate, float) and math.isnan(rate))


def _coin_value_of_output(flow: Flow, family: str, provider: PriceProvider) -> int | None:
    """Coin value of ONE output unit for the family, or None if unpriceable.

    Coins -> face (1). main -> GE price. iron/uim -> RAW High-Alch (the
    multi-step process-then-alch walk is T5).
    """
    if flow.is_coins:
        return 1
    if flow.item_id is None:
        return None
    if family in _IRON_FAMILIES:
        return provider.high_alch(flow.item_id)
    return provider.ge_price(flow.item_id)


def _coin_cost_of_input(flow: Flow, provider: PriceProvider) -> int | None:
    """Coin cost of ONE input unit (GE-priced; coins face), or None.

    v1 values method-level inputs at GE for all families (GE-input iron methods
    are excluded upstream by the iron-gate). An unpriceable input -> None ->
    method unknown.
    """
    if flow.is_coins:
        return 1
    if flow.item_id is None:
        return None
    return provider.ge_price(flow.item_id)


def realize_income(method: MethodRecord, family: str, provider: PriceProvider,
                   recipe_index: dict[str, list[dict]]) -> tuple[int | None, str]:
    """Return (gp_hr_coins_only, gp_hr_status) for `method` realized for `family`.

    gp_hr_status in {"known","unknown"}. Any unpriceable output/input or bad rate
    -> ("unknown", None). For iron/uim, a processing_dependent method is unknown
    in v1 (its real number needs the T5 chain walk; disclosing beats
    under-counting). recipe_index is the T5 seam; unused here.
    """
    is_iron = family in _IRON_FAMILIES

    if is_iron and method.processing_dependent:
        return (None, "unknown")

    total = 0.0
    for out in method.outputs:
        rate = out.qty_per_hour
        unit = _coin_value_of_output(out, family, provider)
        if _bad_rate(rate) or unit is None:
            return (None, "unknown")
        total += unit * rate

    for inp in method.inputs:
        rate = inp.qty_per_hour
        unit = _coin_cost_of_input(inp, provider)
        if _bad_rate(rate) or unit is None:
            return (None, "unknown")
        total -= unit * rate

    return (int(total), "known")
