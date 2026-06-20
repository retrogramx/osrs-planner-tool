# src/osrs_planner/income/overlay.py
"""The income-layer entry point: suggest_methods(state, ...) -> IncomeCard.

Twin of cost.overlay. Given an account, realize every loaded money-making method
for the account's family and return a ranked IncomeCard. v1 (T6) does NOT filter
by doability (that is T7's filter.classify_method): when `kg` is None every
method carries a placeholder requirements_status. current_gold is WIRED BUT
UNUSED (the Option-2 shortfall seam, design §7) so the later expansion needs no
signature change.
"""
from __future__ import annotations

from osrs_planner.engine.state import AccountState, account_family
from osrs_planner.income.cards import IncomeCard, Method, rank_by_gp_hr
from osrs_planner.income.realize import realize_income


def _outputs_summary(method) -> str:
    parts = []
    for f in method.outputs:
        label = "coins" if f.is_coins else (f.item_id or "?")
        # never-fabricate in the DISPLAY string too: an unmodelled rate renders
        # "x?/hr", not "x0/hr" (0 would read as "yields nothing", a fabricated fact;
        # the rankable gp_hr independently surfaces unknown for such a method).
        rate = f"{f.qty_per_hour:g}" if f.qty_per_hour is not None else "?"
        parts.append(f"{label} x{rate}/hr")
    return ", ".join(parts) if parts else "(no outputs)"


def suggest_methods(state, provider, index, recipe_index, kg=None, current_gold=None) -> IncomeCard:
    """Ranked money-making methods for `state`'s account family.

    current_gold is accepted and IGNORED in v1 (Option-2 seam). The family is
    derived from state.mode via account_family. When `kg` is supplied (T7), each
    method is classified can-do-now; when None, requirements_status is a placeholder.
    """
    _ = current_gold  # Option-2 seam: wired, unused in v1 (do not remove).
    family = account_family(state.mode)

    # T7 wires classification; kept as a late import so T6 has no filter dependency.
    classify = None
    if kg is not None:
        from osrs_planner.income.filter import classify_method
        classify = classify_method

    methods: list[Method] = []
    for rec in index:
        # account-type exclusion: a main-only (requires_ge / not iron_eligible)
        # method is absent from iron/uim cards; mains see all.
        if family != "main" and (rec.requires_ge or not rec.iron_eligible):
            continue

        # T5 signature reconciliation: realize_income gates the iron processing
        # chain on the ACCOUNT's skill levels (keyed skill:<name>, like
        # AccountState.levels) -- killing green dragons needs no Crafting, but
        # turning the hides into bodies depends on the ACCOUNT's Crafting. So a
        # 63-Crafting iron realizes green dragons via the body chain; a low one
        # falls back to raw alch. Pass state.levels, not method.requirements.
        gp_hr, status = realize_income(rec, family, provider, recipe_index, state.levels)
        if classify is not None:
            cstatus, detail = classify(rec, state, kg)
            req_status = {"status": cstatus, "missing": detail["missing"], "unverified": detail["unverified"]}
        else:
            req_status = {"status": "doable_now", "missing": [], "unverified": []}

        methods.append(
            Method(
                id=rec.id, name=rec.name, category=rec.category, members=rec.members,
                gp_hr=gp_hr, gp_hr_status=status, realization_channel=rec.realization_channel,
                requirements_status=req_status, tags=dict(rec.tags), net_sign=rec.net_sign,
                outputs_summary=_outputs_summary(rec), source=rec.source, url=rec.url,
            )
        )

    return IncomeCard(
        account_family=family,
        methods=methods,
        rankings={"by_gp_hr": rank_by_gp_hr(methods)},
        notes=[
            f"account_family={family}; gp/hr realized per family (main=GE, iron/uim=coins+High-Alch).",
            "current_gold is reserved for the Option-2 shortfall hand-off (unused in v1).",
        ],
    )
