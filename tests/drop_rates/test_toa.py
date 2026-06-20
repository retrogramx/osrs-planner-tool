from data._toa_drop_rates import TOA_UNIQUES, apply_toa


def test_toa_attaches_invocation_disclosure():
    # dropsline already gives a flat 1/24 -> 'sourced'. apply_toa ATTACHES the
    # invocation-scaling disclosure to variants[]; it does NOT rescue a null (M4).
    rec = {"item": "Tumeken's shadow (uncharged)", "source": "Chest (Tombs of Amascut)",
           "source_node_type": "raid", "source_condition": None,
           "drop_rate": 1/24, "drop_rate_raw": "1/24", "rolls": 1,
           "drop_rate_status": "sourced", "variants": []}
    out = apply_toa(rec)
    assert out["drop_rate_status"] == "sourced" and out["drop_rate"] is not None
    assert any("invocation" in v["condition"].lower() for v in out["variants"])


def test_apply_toa_noop_for_non_toa():
    rec = {"item": "Abyssal whip", "source": "Abyssal demon", "source_node_type": "monster",
           "source_condition": None, "drop_rate": 1/512, "drop_rate_raw": "1/512",
           "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    assert apply_toa(rec) == rec
