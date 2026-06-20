# src/osrs_planner/account/bank.py
"""Bank Memory TSV ingestion + bank value (design §4). Personal data is a RUNTIME
input; never committed. IDs are KG-style 'item:<n>' to match AccountState.counts."""
from __future__ import annotations

def parse_bank_tsv(text: str) -> dict[str, int]:
    """Bank Memory 'Copy item data to clipboard' TSV -> {'item:<id>': qty}.

    Layout is `id <tab> name(space-padded) <tab..> qty`; tab count varies, so we
    take the FIRST non-empty field as the id and the LAST as the quantity. Blank /
    unparseable rows are skipped, not fabricated."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("\t")]
        nonempty = [c for c in cells if c]
        if len(nonempty) < 2:
            continue
        try:
            item_id = int(nonempty[0])
            qty = int(nonempty[-1].replace(",", ""))
        except ValueError:
            continue
        key = f"item:{item_id}"
        out[key] = out.get(key, 0) + qty
    return out

# Currencies the GE snapshot does not price -> count at face. Plat tokens are how
# large coin stacks are stored, so omitting them badly understates spend-now gold.
_CURRENCY = {"item:995": 1, "item:13204": 1000}   # coins=1gp, platinum token=1000gp
_NO_GE = 2_000_000_000  # ge_prices.json uses int-max (2147483647) as a "no real GE price" sentinel

def bank_value(counts: dict[str, int], provider, family: str) -> dict:
    """Iron-realizable (currency + High-Alch of TRADEABLE items) + total GE value
    of a bank (design §4). An item with no live GE price is untradeable -> it yields
    no realizable gold (its nominal High-Alch is unusable), so it is counted in
    unpriced_count, NOT added to iron_realizable. Never fabricates value."""
    iron = 0
    ge = 0
    per_item: dict[str, dict] = {}
    unpriced = 0
    for item_id, qty in counts.items():
        if item_id in _CURRENCY:
            face = qty * _CURRENCY[item_id]
            iron += face
            ge += face
            continue
        gp = provider.ge_price(item_id)
        if not gp or gp >= _NO_GE:           # untradeable / no real GE price -> not realizable
            unpriced += 1
            continue
        ha = provider.high_alch(item_id) or 0
        ge += gp * qty
        iron += ha * qty                     # an iron realizes a TRADEABLE item via High-Alch
        per_item[item_id] = {"ge": gp * qty, "ha": ha * qty}
    headline = ge if family == "main" else iron
    return {"iron_realizable": iron, "ge_value": ge, "headline": headline,
            "per_item": per_item, "unpriced_count": unpriced}
