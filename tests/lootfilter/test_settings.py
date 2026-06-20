from osrs_planner.lootfilter.emit import emit_settings

def test_settings_iron_gated_and_covers_toggles():
    out = emit_settings()
    assert "module:settings" in out
    assert out.count("apply (IRONMAN") == out.count("apply (")   # every apply iron-gated
    for macro in ("SHOW_WORLD_SPAWNS", "SHOW_UNOWNED", "SHOW_DESPAWN", "SHOW_VALUE"):
        assert f"#define {macro}" in out
    assert "showValue = true;" in out and "showDespawn = true;" in out
