import json, os
from osrs_planner.account.state import build_account_state
from osrs_planner.account.temple import parse_temple_clog

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

def _obtained():
    payload = json.load(open(os.path.join(FIX, "sample_temple.json"), encoding="utf-8"))
    return parse_temple_clog(payload)["obtained"]

def test_bank_only_sets_counts_observes_item_not_clog():
    s = build_account_state("ironman", bank_tsv="995\tCoins\t100\n4151\tAbyssal whip\t1\n")
    assert s.counts == {"item:995": 100, "item:4151": 1}
    assert "item" in s.observable_families and "clog" not in s.observable_families
    assert s.clog_obtained == set()

def test_clog_only_sets_clog_observes_clog_not_item():
    s = build_account_state("ironman", clog_obtained=_obtained())
    assert s.clog_obtained == {"item:22804", "item:29889"}
    assert "clog" in s.observable_families and "item" not in s.observable_families
    assert s.counts == {}

def test_both_sources_combine():
    s = build_account_state("ironman", bank_tsv="995\tCoins\t100\n", clog_obtained=_obtained())
    assert s.counts == {"item:995": 100} and "item:22804" in s.clog_obtained
    assert {"item", "clog"} <= s.observable_families

def test_ingested_but_empty_source_still_observed():
    # an empty bank / empty clog is OBSERVED (own nothing / completed nothing), not UNKNOWN
    s = build_account_state("ironman", bank_tsv="", clog_obtained=set())
    assert s.counts == {} and s.clog_obtained == set()
    assert {"item", "clog"} <= s.observable_families

def test_neither_source_is_empty_state():
    s = build_account_state("main")
    assert s.counts == {} and s.clog_obtained == set() and s.observable_families == set()
