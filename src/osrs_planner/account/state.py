# src/osrs_planner/account/state.py
"""Combine the runtime account sources into one AccountState (design §6).
Observability is SOURCE-GATED on `is not None`: a family is marked observed only
when its source was actually INGESTED (even if empty -> own/completed nothing is a
real observed zero), preserving the engine's absence-aware UNKNOWN contract for
sources that were NOT ingested. `clog_obtained` is the already-parsed obtained set
(from temple.parse_temple_clog/fetch_collection_log), so fixture + live compose."""
from __future__ import annotations

from osrs_planner.engine.state import AccountState
from osrs_planner.account.bank import parse_bank_tsv

def build_account_state(mode: str, bank_tsv: str | None = None,
                        clog_obtained: set[str] | None = None) -> AccountState:
    counts = parse_bank_tsv(bank_tsv) if bank_tsv is not None else {}
    clog = set(clog_obtained) if clog_obtained is not None else set()
    observable: set[str] = set()
    if bank_tsv is not None:
        observable.add("item")        # item-ownership now a real own/don't-own
    if clog_obtained is not None:
        observable.add("clog")
    return AccountState(mode=mode, counts=counts, clog_obtained=clog,
                        observable_families=observable)
