from osrs_planner.lootfilter.emit import emit_gear

def test_gear_module_tiers_by_slot():
    recs = [
        {"item_id": 100, "slot": "body", "stats": {"stab_defence_bonus": 200}},  # top
        {"item_id": 101, "slot": "body", "stats": {"stab_defence_bonus": 10}},   # low
    ]
    out = emit_gear(recs)
    assert "define:module:gear" in out
    assert "id:[100]" in out and "id:[101]" in out
    # top item must be in a higher grade rule than the low item (S before C in emit order)
    assert out.index("id:[100]") < out.index("id:[101]")
