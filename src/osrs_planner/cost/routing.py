# src/osrs_planner/cost/routing.py
"""price_routes -- the account-aware acquisition walk (design spec §4).

Enumerates an item's channels from the prebuilt index, keeps those whose
account_allow includes the family, prices each (ge via PriceProvider, shop via
the record amount, spawn = 0, craft/gather = sum of cheapest input routes), and
returns ALL routes. Cycle-safe (_visited) + depth-capped.
"""
from __future__ import annotations

from osrs_planner.cost.cards import Route
from osrs_planner.cost.channels import ChannelRecord
from osrs_planner.cost.prices import PriceProvider

DEPTH_CAP = 12
_PRODUCE_CHANNELS = {"craft", "gather"}


def _cheapest_gold(routes: list[Route]) -> int | None:
    """Smallest known gold_cost among routes, or None if none are priced."""
    known = [
        r.gold_cost
        for r in routes
        if r.gold_status == "known" and r.gold_cost is not None
    ]
    return min(known) if known else None


def price_routes(
    item_id: str,
    family: str,
    provider: PriceProvider,
    index: dict[str, list[ChannelRecord]],
    owned: frozenset[str] = frozenset(),  # SKELETON: unused in v1 (future per-account balance subtraction)
    _visited: frozenset[str] = frozenset(),
    _depth: int = 0,
) -> list[Route]:
    # Single depth backstop for the whole recursion: every _price_produce input
    # recurses via price_routes(..., _depth+1), so this entry guard terminates depth.
    if _depth > DEPTH_CAP:
        return []
    out: list[Route] = []
    for rec in index.get(item_id, []):
        if family not in rec.account_allow:
            continue
        if rec.channel == "ge":
            # GE is coins-only and main-only; price IS the coin figure.
            price = provider.ge_price(item_id)
            if price is None:
                out.append(Route(
                    channel="ge", currency=rec.currency, gold_cost=None,
                    amount=None, gold_status="unavailable", account_allowed=True,
                    source=rec.source, notes=["ge price unavailable"],
                ))
            else:
                out.append(Route(
                    channel="ge", currency=rec.currency, gold_cost=int(price),
                    amount=int(price), gold_status="known", account_allowed=True,
                    source=rec.source,
                ))
        elif rec.channel == "shop":
            # amount = the figure in rec.currency; gold_cost is coins ONLY
            # (None for tokkul etc.) so by_gold never face-compares currencies
            # (spec §11 Tokkul trap). A known non-coin buy stays gold_status
            # "known" -- it IS a known acquisition, just not coin-priced.
            is_coins = rec.currency == "currency:coins"
            out.append(Route(
                channel="shop", currency=rec.currency,
                gold_cost=rec.amount if is_coins else None,
                amount=rec.amount,
                gold_status="known" if rec.amount is not None else "unavailable",
                account_allowed=True, source=rec.source,
            ))
        elif rec.channel == "spawn":
            # Free pickup. Gate coins-only like the shop branch: a coin spawn is
            # 0 coins (rec.amount is 0 today), a future non-coin spawn -> None so
            # by_gold never face-compares currencies (spec §11). amount stays
            # as-is (the figure in rec.currency).
            is_coins = rec.currency == "currency:coins"
            out.append(Route(
                channel="spawn", currency=rec.currency,
                gold_cost=rec.amount if is_coins else None, amount=rec.amount,
                gold_status="known", account_allowed=True, source=rec.source,
            ))
        elif rec.channel in _PRODUCE_CHANNELS:
            out.append(_price_produce(
                rec, family, provider, index, owned, _visited, _depth,
            ))
    return out


def _price_produce(
    rec: ChannelRecord,
    family: str,
    provider: PriceProvider,
    index: dict[str, list[ChannelRecord]],
    owned: frozenset[str],
    _visited: frozenset[str],
    _depth: int,
) -> Route:
    """Price a craft/gather record: sum cheapest(input) * qty / output_qty."""
    sub_routes: list[Route] = []
    total = 0
    priced = True
    next_visited = _visited | {rec.item_id}
    for input_id, qty in rec.inputs:
        # Cycle guard only; depth is handled by price_routes' entry guard below.
        if input_id in next_visited:
            priced = False
            continue
        input_routes = price_routes(
            input_id, family, provider, index, owned, next_visited, _depth + 1,
        )
        cheapest = _cheapest_gold(input_routes)
        if cheapest is None:
            priced = False
        else:
            # record the cheapest priced sub-route for the breakdown
            chosen = next(
                r for r in input_routes
                if r.gold_status == "known" and r.gold_cost == cheapest
            )
            sub_routes.append(chosen)
            total += cheapest * qty
    if priced and rec.inputs:
        # Produce routes are coin-denominated: `total` is a sum of component
        # COIN costs (_cheapest_gold reads gold_cost, which is coins-only), so a
        # component whose only route is non-coin yields cheapest=None ->
        # priced=False and we fall through to the unavailable branch below
        # (can't coin-sum a non-coin input -- spec §11). amount mirrors the coin
        # gold_cost for the produce path.
        per_unit = total // rec.output_qty  # floor (batch recipe), not a rounding bug
        return Route(
            channel=rec.channel, currency=rec.currency,
            gold_cost=per_unit, amount=per_unit, gold_status="known",
            inputs=sub_routes, account_allowed=True, source=rec.source,
        )
    return Route(
        channel=rec.channel, currency=rec.currency, gold_cost=None, amount=None,
        gold_status="unavailable", inputs=sub_routes, account_allowed=True,
        source=rec.source, notes=["input not priceable"],
    )
