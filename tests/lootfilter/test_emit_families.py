from osrs_planner.lootfilter.emit import emit_families

def test_emit_families_skips_gear_and_emits_module():
    family_ids = {
        "gear": [1, 2, 3],       # must be skipped -- handled by emit_gear (stat-tiered)
        "herb": [100, 101],
        "ore": [200],
        "not_a_real_family": [999],  # no FAMILY_HUES entry -> skipped
        "ammo": [],                  # empty id-list -> skipped
    }
    out = emit_families(family_ids)
    assert "define:module:families" in out
    assert "id:[1, 2, 3]" not in out and "FAM_GEAR" not in out   # gear skipped entirely
    assert "id:[100, 101]" in out and "Herb" in out
    assert "id:[200]" in out and "Ore" in out
    assert "999" not in out
