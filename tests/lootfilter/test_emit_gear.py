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

def test_gear_module_negative_score_does_not_crash():
    # gear_score sums defence bonuses, so one negative stat can make a score negative even when
    # another item in the same slot has a positive top score. GEAR_TIERS bottoms out at 0.0, so an
    # unclamped negative fraction matches no tier -> uncaught StopIteration. emit_gear must not crash.
    recs = [
        {"item_id": 1, "slot": "shield", "stats": {"stab_defence_bonus": 50}},
        {"item_id": 2, "slot": "shield", "stats": {"stab_defence_bonus": -20}},
    ]
    out = emit_gear(recs)
    assert "id:[1]" in out and "id:[2]" in out
    # the negative-score item must land in the LOWEST grade (C), which is emitted last (S..C order)
    assert out.index("id:[1]") < out.index("id:[2]")
    assert "Gear shield C" in out
