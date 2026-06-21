"""Detect an account's type by probing the OSRS Hiscores boards. An account
appears on every board up to its restriction (a HCIM is on hcim + ironman +
normal), so the most-restrictive board it's on IS its type."""
from __future__ import annotations

from osrs_planner.hiscores import fetch_stats, PlayerNotFoundError
from osrs_planner.models import AccountMode

# most-restrictive first; group-iron variants deferred (spec §8) -> fall through to ironman/normal
_PROBE_ORDER = [
    AccountMode.hardcore_ironman,
    AccountMode.ultimate_ironman,
    AccountMode.ironman,
    AccountMode.normal,
]

def detect_account_type(rsn: str, fetcher=fetch_stats) -> AccountMode:
    for mode in _PROBE_ORDER:
        try:
            fetcher(rsn, mode)
            return mode
        except PlayerNotFoundError:
            continue
    raise PlayerNotFoundError(f"Account '{rsn}' not found on any Hiscores board")
