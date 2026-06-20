import json, os
from osrs_planner.account.temple import collection_log_url, parse_temple_clog, fetch_collection_log

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample_temple.json")

def test_url_targets_temple_clog_api():
    u = collection_log_url("Tiger0295")
    assert "templeosrs.com/api/collection-log/player_collection_log.php" in u
    assert "player=Tiger0295" in u and "categories=all" in u

def test_parse_obtained_only_count_ge_1():
    payload = json.load(open(FIX, encoding="utf-8"))
    c = parse_temple_clog(payload)
    assert c["obtained"] == {"item:22804", "item:29889"}   # count 0 item EXCLUDED
    assert c["finished"] == 2 and c["available"] == 1701 and c["game_mode"] == 1

def test_fetch_uses_injected_fetcher():
    payload = json.load(open(FIX, encoding="utf-8"))
    c = fetch_collection_log("TestIron", fetcher=lambda url: payload)
    assert "item:22804" in c["obtained"]
