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
