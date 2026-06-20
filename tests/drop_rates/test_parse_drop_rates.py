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


from data._raid_scaling import apply_raid_scaling


def _fixture():
    import json, os
    return json.load(open(os.path.join(REPO, "data", "raw", "dropsline_fixture.json")))

def test_superior_source_tagged_on_real_data():  # M6 — superior is a record field
    cache = _fixture()
    clog = [{"item": "Abyssal whip", "item_id": 4151, "source": "Slayer", "node_type": "activity"}]
    recs = build_records(clog, cache)
    greater = [r for r in recs if r["source"] == "Greater abyssal demon"]
    assert greater and greater[0]["source_condition"] == "superior"

def test_multi_slot_same_base_keeps_all_rates():  # M6 — no input row dropped
    cache = {"Coins": [
        {"item_name": "Coins", "drop_json": {"Dropped from": "Mithril dragon", "Rarity": "17/128", "Rolls": 1}},
        {"item_name": "Coins", "drop_json": {"Dropped from": "Mithril dragon", "Rarity": "7/128", "Rolls": 1}},
    ]}
    clog = [{"item": "Coins", "item_id": 995, "source": "x", "node_type": "other"}]
    recs = build_records(clog, cache)
    md = [r for r in recs if r["source"] == "Mithril dragon"]
    assert len(md) == 1
    rates = [md[0]["drop_rate"]] + [v["drop_rate"] for v in md[0]["variants"]]
    assert any(math.isclose(x, 17/128) for x in rates) and any(math.isclose(x, 7/128) for x in rates)

def test_apply_raid_scaling_attaches_for_cox_noop_otherwise():
    cox = {"source": "Ancient chest", "variants": []}
    assert any("scales" in v["condition"].lower() for v in apply_raid_scaling(cox)["variants"])
    other = {"source": "Abyssal demon", "variants": []}
    assert apply_raid_scaling(other)["variants"] == []
