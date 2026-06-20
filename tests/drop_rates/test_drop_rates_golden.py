import json, math, os
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECS = json.load(open(os.path.join(REPO, "data", "drop_rates.json")))["records"]

def _find(item, source):
    hits = [r for r in RECS if r["item"] == item and r["source"] == source]
    assert len(hits) == 1, f"{item}@{source}: expected 1, got {len(hits)}"
    return hits[0]

def test_whip_from_abyssal_demon():  # note-1 proof on real data
    r = _find("Abyssal whip", "Abyssal demon")
    assert math.isclose(r["drop_rate"], 1/512, rel_tol=1e-6) and r["drop_rate_raw"] == "1/512"

def test_granite_maul_resolves_to_a_real_monster():
    hits = [r for r in RECS if r["item"] == "Granite maul" and r["drop_rate_status"] == "sourced"]
    assert hits, "Granite maul did not resolve to any sourced monster rate"

def test_comma_denominator_unique_parsed():  # M3 — a rare unique with a comma rate
    pk = [r for r in RECS if r["item"] == "Pet kraken" and r["source"] == "Kraken"]
    assert pk and pk[0]["drop_rate_status"] == "sourced"
    assert math.isclose(pk[0]["drop_rate"], 1/3000, rel_tol=1e-6)  # raw "1/3,000"

def test_superior_condition_present_somewhere():  # M6 — superior tagging survived to data
    assert any(r.get("source_condition") == "superior" for r in RECS)

def test_wyrm_harpoon_alt_rarity_is_honest():  # alt-rarity on real serialized data
    r = _find("Dragon harpoon", "Wyrm")
    assert math.isclose(r["drop_rate"], 1/10000, rel_tol=1e-6)  # base = unconditional
    alt = [v for v in r["variants"] if v["drop_rate_raw"] == "1/2,000"]
    assert alt and math.isclose(alt[0]["drop_rate"], 1/2000, rel_tol=1e-6)
    c = alt[0]["condition"].lower()
    assert "conditional boost" in c and "not specified" in c  # honest, non-fabricated
    assert c != "on slayer task"  # the reverted fabrication must not reappear

def test_no_fabricated_rates():  # base AND variant numbers must carry a raw
    for r in RECS:
        if r["drop_rate"] is not None:
            assert r["drop_rate_raw"], f"fabricated base: {r['item']}@{r['source']}"
        for v in r["variants"]:
            if v.get("drop_rate") is not None:
                assert v.get("drop_rate_raw"), f"fabricated variant: {r['item']}@{r['source']}"

def test_every_null_has_a_reason():
    for r in RECS:
        if r["drop_rate"] is None:
            assert r["drop_rate_status"] not in (None, "", "sourced")
