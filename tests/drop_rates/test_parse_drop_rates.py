import json, math, os
from data.parse_drop_rates import split_source, build_records

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_split_source_strips_hash_variant():
    assert split_source("Abyssal demon#Wilderness Slayer Cave") == ("Abyssal demon", "Wilderness Slayer Cave")
    assert split_source("Gargoyle") == ("Gargoyle", None)

def test_build_records_resolves_whip_to_abyssal_demon():
    cache = json.load(open(os.path.join(REPO, "data", "raw", "dropsline_fixture.json")))
    clog = [{"item": "Abyssal whip", "item_id": 4151, "source": "Slayer", "node_type": "activity"}]
    recs = build_records(clog, cache)
    # at least one record: Abyssal whip @ Abyssal demon = 1/512, sourced
    ad = [r for r in recs if r["source"] == "Abyssal demon"]
    assert ad, "expected an Abyssal demon record for the whip"
    assert ad[0]["item_id"] == 4151
    assert ad[0]["drop_rate_status"] == "sourced"
    assert math.isclose(ad[0]["drop_rate"], 1/512, rel_tol=1e-6)
    assert ad[0]["drop_rate_raw"] == "1/512"
    assert ad[0]["rolls"] >= 1
