from osrs_planner.lootfilter.emit import emit_custom_highlights

def test_custom_module_has_free_and_hide_slots():
    out = emit_custom_highlights(free=6)
    assert "define:module:custom" in out
    assert out.count("type: stringlist") >= 6          # >=6 free-color name lists
    assert "type: style" in out                        # each free slot has a style picker
    assert "Hide" in out                               # hide bank present
