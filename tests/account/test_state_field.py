from osrs_planner.engine.state import AccountState

def test_clog_obtained_defaults_empty():
    s = AccountState(mode="ironman")
    assert s.clog_obtained == set()

def test_clog_obtained_accepts_ids():
    s = AccountState(mode="ironman", clog_obtained={"item:4151"})
    assert "item:4151" in s.clog_obtained
