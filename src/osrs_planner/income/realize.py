# src/osrs_planner/income/realize.py
"""Per-family income realization (best-realization, with the iron processing chain).

realize_income(method, family, provider, recipe_index, account_skills) ->
(gp_hr, gp_hr_status) computes a method's COINS-ONLY gp/hr at query time, the
inverse of cost's price walk:

  main      -> sum over outputs of GE value (provider.ge_price; coins face) * rate
               MINUS sum over inputs of GE cost * rate.
  iron/uim  -> sum over outputs of best_realization(output) * rate. Each non-coins
               iron output is valued at max(RAW High-Alch, process-then-alch via
               the tan->craft->alch walk over recipe_index), gated by the ACCOUNT's
               skills (``account_skills``, not the method's requirements -- killing
               green dragons needs no Crafting, but turning the hides into bodies
               does), minus internal costs (per-hide tan service fee + secondary
               inputs). Green dragons: 1539/hide via the body chain (a 63-Crafting
               account) vs 81 raw alch (a low-Crafting account).

NEVER fabricate (design §4): a missing price, a null/NaN rate, or (for iron) a
processing_dependent method whose chain isn't covered -> gp_hr_status="unknown",
gp_hr=None. A NORMAL non-coin item output (item_id set) that can't be valued in
coins makes the whole method unknown (no partial fabricated number).

AGGREGATE/BUNDLE outputs (item_id is None AND not is_coins -- e.g. an unitemized
"gem drop table") are SKIPPED: they contribute 0 and do NOT force unknown, for
BOTH families. These bundles are excluded from v1 income -- a DISCLOSED honest
under-count (the safe direction), not a fabricated value. Valuing them is a v2
follow-up. Without this skip, any method carrying a bundle output (like the real
green-dragons record) would falsely return unknown for every family.

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
                   recipe_index: dict[str, list[dict]],
                   account_skills: dict[str, int]) -> tuple[int | None, str]:
    """Return (gp_hr_coins_only, gp_hr_status) for `method` realized for `family`.

    gp_hr_status in {"known","unknown"}. Any unpriceable output/input or bad rate
    -> ("unknown", None). For iron/uim, a processing_dependent method is unknown
    in v1 (its real number needs the T5 chain walk; disclosing beats
    under-counting).

    ``account_skills`` is the PLAYER's skill levels, keyed like
    ``AccountState.levels`` (``skill:<name>`` slugs, e.g. ``{"skill:crafting": 63}``).
    It -- NOT ``method.requirements.skills`` -- gates the iron processing chain:
    income is account-specific, and whether a hide can be turned into a body
    depends on the ACCOUNT's Crafting level, not on whether the kill method
    happens to require Crafting (it doesn't). Threaded into ``best_realization``;
    the main/coins/input paths ignore it. (Accepted deviation from the plan's
    "skills-source" decision -- T6 ``suggest_methods`` passes ``state.levels``.)
    """
    is_iron = family in _IRON_FAMILIES

    if is_iron and method.processing_dependent:
        return (None, "unknown")

    total = 0.0
    for out in method.outputs:
        rate = out.qty_per_hour
        if _bad_rate(rate):
            return (None, "unknown")
        if out.is_coins:
            unit = 1
        elif out.item_id is None:
            # AGGREGATE/BUNDLE output (item_id None, not coins -- e.g. an
            # unitemized "gem drop table"). Excluded from v1 income: SKIP it
            # (contributes 0; does NOT force unknown), for BOTH families. A
            # disclosed honest under-count, the SAFE direction -- never a
            # fabricated value. (A NORMAL item output that can't be valued
            # still forces unknown below; only unitemized bundles are skipped.)
            continue
        elif is_iron:
            # DISCLOSED v1 over-count: best_realization values ANY alchable output
            # at its High-Alch floor, including items an iron would realistically use
            # for XP/consumables, not alch -- Prayer fodder (dragon bones ~96 alch but
            # gilded-altar Prayer is worth far more), ensouled heads, herblore
            # secondaries (grimy herbs). So iron gp/hr slightly over-counts gold and
            # omits those items' true (XP) value. Proper handling (bones -> Prayer XP,
            # gold contribution 0) is the deferred {gold,xp,resources} accounting +
            # a "non-income fodder" tag. (design §4)
            unit, ostatus = best_realization(
                out.item_id, provider, recipe_index, account_skills
            )
            if ostatus != "known" or unit is None:
                return (None, "unknown")
        else:
            unit = provider.ge_price(out.item_id)
            if unit is None:
                return (None, "unknown")
        total += unit * rate

    for inp in method.inputs:
        rate = inp.qty_per_hour
        unit = _coin_cost_of_input(inp, provider)
        if _bad_rate(rate) or unit is None:
            return (None, "unknown")
        total -= unit * rate

    return (int(total), "known")


def _skill_key(skill: str) -> str:
    """Normalize a recipe's DISPLAY skill name to the account key convention.

    Recipes carry display names ("Crafting"); the account's levels (and the KG)
    key skills as ``skill:<name>`` slugs, lowercased (``AccountState.levels`` ==
    ``{"skill:crafting": 63}``). Bridge the two so the gate lookup matches.
    """
    return f"skill:{skill.strip().lower()}"


def _level_ok(recipe: dict, skills: dict) -> bool:
    """The account meets the recipe's skill gate.

    A recipe with no skill (null) is always craftable. A skill gate requires the
    ACCOUNT's level for that skill (``skills[skill:<name>]``) >= the recipe level.
    ``skills`` is the player's levels, keyed like ``AccountState.levels``
    (``skill:<name>`` slugs); an absent skill is treated as below the gate. The
    recipe's display skill name ("Crafting") is normalized to that key
    (``skill:crafting``) so the two conventions match.
    """
    skill = recipe.get("skill")
    if not skill:
        return True
    return int(skills.get(_skill_key(skill), 0)) >= int(recipe.get("level") or 1)


def best_realization(item_id: str, provider: PriceProvider,
                     recipe_index: dict[str, list[dict]], skills: dict,
                     _seen: frozenset[str] | None = None) -> tuple[int | None, str]:
    """Best coins-realization for a single iron output, in coins.

    Only ever reached on the iron/uim path (the main path values outputs at GE in
    realize_income), so it takes no ``family`` -- the iron-vs-main branch lives in
    the caller.

    Compares: high_alch(raw) vs every process-then-realize route walking
    recipe_index (raw -> product), recursively, gated by the ACCOUNT's skills,
    subtracting internal costs (per-unit service_fee_coins + secondary inputs).
    ``skills`` is the player's levels keyed like ``AccountState.levels``
    (``skill:<name>`` slugs); ``_level_ok`` normalizes each recipe's display skill
    name to that key. Returns (best_coins_per_unit_of_item_id, status). status ==
    "unknown" only when NOTHING is priceable (no alch, no covered chain). _seen
    guards cycles.
    """
    _seen = _seen or frozenset()
    if item_id in _seen:
        return None, "unknown"
    seen = _seen | {item_id}

    candidates: list[int] = []

    raw = provider.high_alch(item_id)
    if raw is not None:
        candidates.append(int(raw))

    for recipe in recipe_index.get(item_id, []):
        if not _level_ok(recipe, skills):
            continue
        out_id = recipe["output_item_id"]
        out_qty = int(recipe.get("output_qty") or 1)
        inputs = recipe.get("inputs") or []
        this_in = next((i for i in inputs if i["item_id"] == item_id), None)
        if this_in is None:
            continue
        # `or 1.0` masks a 0/missing qty as 1 to avoid a divide-by-zero below; no
        # committed recipe has qty 0, so this is a defensive default, not live math.
        consumed = float(this_in["qty"]) or 1.0

        prod_val, prod_status = best_realization(out_id, provider, recipe_index, skills, seen)
        if prod_status != "known" or prod_val is None:
            continue

        service_fee = float(recipe.get("service_fee_coins") or 0) * consumed
        secondary_cost = 0.0
        ok = True
        for inp in inputs:
            if inp["item_id"] == item_id:
                continue
            # DISCLOSED v1 under-cost (T5): a secondary input is charged at its
            # best-REALIZATION value (what an iron could turn it back into, e.g.
            # thread @ high_alch=1), NOT its acquisition cost (thread @ GE=7). For
            # the only v1 chain this is ~1 coin/body (~0.13% of 1539/hide), the
            # UNSAFE direction (under-cost), and is dwarfed by the SAFE-direction
            # GE-costing of method-level inputs upstream. Proper acquisition-cost
            # valuation of secondaries is a v2 follow-up.
            sec_val, sec_status = best_realization(inp["item_id"], provider, recipe_index, skills, seen)
            if sec_status != "known" or sec_val is None:
                ok = False
                break
            secondary_cost += sec_val * float(inp["qty"])
        if not ok:
            continue

        net_per_product = prod_val * out_qty - service_fee - secondary_cost
        per_this_item = net_per_product / consumed
        candidates.append(int(per_this_item))  # floor to whole coins (alch/GE are integer)

    if not candidates:
        return None, "unknown"
    return max(candidates), "known"
