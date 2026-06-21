import pytest
from osrs_planner.account.detect import detect_account_type
from osrs_planner.models import Account, AccountMode, Skill
from osrs_planner.hiscores import PlayerNotFoundError

def _acct(total_xp):
    return Account(rsn="X", mode=AccountMode.normal,
                   skills={"Attack": Skill(name="Attack", level=1, xp=total_xp)})

def _fetcher(board_xp):
    """board_xp maps AccountMode -> the board's total xp (omit a board = account not on it)."""
    def fetcher(rsn, mode):
        if mode not in board_xp:
            raise PlayerNotFoundError("not on this board")
        return _acct(board_xp[mode])
    return fetcher

def test_detects_regular_ironman():
    f = _fetcher({AccountMode.normal: 5000, AccountMode.ironman: 5000})
    assert detect_account_type("X", fetcher=f) == AccountMode.ironman

def test_detects_live_hardcore():
    # live HCIM: all boards carry the same current xp -> most restrictive wins
    f = _fetcher({AccountMode.normal: 5000, AccountMode.ironman: 5000, AccountMode.hardcore_ironman: 5000})
    assert detect_account_type("X", fetcher=f) == AccountMode.hardcore_ironman

def test_dead_hardcore_falls_to_ironman():
    # de-ranked HCIM: hcim board is FROZEN at death-time xp (5000) while the account played on as an
    # iron (normal+ironman = current 9000). hcim no longer matches -> correctly resolves to Ironman.
    f = _fetcher({AccountMode.normal: 9000, AccountMode.ironman: 9000, AccountMode.hardcore_ironman: 5000})
    assert detect_account_type("X", fetcher=f) == AccountMode.ironman

def test_de_ironed_falls_to_main():
    # de-ironed account: both iron boards frozen (5000), only normal is current (9000)
    f = _fetcher({AccountMode.normal: 9000, AccountMode.ironman: 5000, AccountMode.hardcore_ironman: 5000})
    assert detect_account_type("X", fetcher=f) == AccountMode.normal

def test_detects_main():
    f = _fetcher({AccountMode.normal: 5000})
    assert detect_account_type("X", fetcher=f) == AccountMode.normal

def test_unknown_account_raises():
    f = _fetcher({})  # not even on the normal board
    with pytest.raises(PlayerNotFoundError):
        detect_account_type("X", fetcher=f)
