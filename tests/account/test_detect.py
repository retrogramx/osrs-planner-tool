import pytest
from osrs_planner.account.detect import detect_account_type
from osrs_planner.models import AccountMode
from osrs_planner.hiscores import PlayerNotFoundError

def _fake_fetcher(on_boards):
    """Return a fetcher that 'finds' the account only on the given AccountModes."""
    def fetcher(rsn, mode):
        if mode in on_boards:
            return object()  # detect_account_type ignores the payload, only success/raise matters
        raise PlayerNotFoundError("not on this board")
    return fetcher

def test_detects_regular_ironman():
    f = _fake_fetcher({AccountMode.ironman, AccountMode.normal})
    assert detect_account_type("X", fetcher=f) == AccountMode.ironman

def test_detects_hardcore_over_ironman():
    # HCIM appears on hcim + ironman + normal -> most restrictive wins
    f = _fake_fetcher({AccountMode.hardcore_ironman, AccountMode.ironman, AccountMode.normal})
    assert detect_account_type("X", fetcher=f) == AccountMode.hardcore_ironman

def test_detects_main():
    f = _fake_fetcher({AccountMode.normal})
    assert detect_account_type("X", fetcher=f) == AccountMode.normal

def test_unknown_account_raises():
    f = _fake_fetcher(set())  # on no board at all
    with pytest.raises(PlayerNotFoundError):
        detect_account_type("X", fetcher=f)
