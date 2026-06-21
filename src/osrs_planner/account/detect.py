"""Detect an account's CURRENT type from the OSRS Hiscores boards.

An account appears on every board up to its restriction, but a board can go
STALE while the account lives on: a Hardcore Ironman who dies de-ranks to a
regular Ironman yet stays *frozen* on the HCIM board at its death-time stats;
a de-ironed account freezes on the ironman board. So presence alone is wrong.

The current stats always live on the NORMAL board (every account is there).
The account's type is the most-restrictive board whose stats still MATCH the
current ones -- a frozen board won't match, so we correctly fall through."""
from __future__ import annotations

from osrs_planner.hiscores import fetch_stats, PlayerNotFoundError, HiscoresError
from osrs_planner.models import Account, AccountMode

# most-restrictive first; group-iron variants deferred (spec §8) -> fall through to ironman/normal
_RESTRICTED = [AccountMode.hardcore_ironman, AccountMode.ultimate_ironman, AccountMode.ironman]

def _total_xp(account: Account) -> int:
    return sum(s.xp for s in account.skills.values())

def detect_account_type(rsn: str, fetcher=fetch_stats) -> AccountMode:
    current = fetcher(rsn, AccountMode.normal)   # raises PlayerNotFoundError if the account doesn't exist
    current_xp = _total_xp(current)
    for mode in _RESTRICTED:
        try:
            stats = fetcher(rsn, mode)
        except (PlayerNotFoundError, HiscoresError):   # not on this board / board flaky -> skip it
            continue
        if _total_xp(stats) == current_xp:       # a frozen (dead-HC / de-ironed) board won't match
            return mode
    return AccountMode.normal
