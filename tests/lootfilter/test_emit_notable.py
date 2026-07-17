from osrs_planner.lootfilter.emit import emit_notable

def test_notable_module_layers():
    out = emit_notable(recommended_ids=[10, 11], rare_ids=[20])
    assert "define:module:notable" in out
    assert "id:[10, 11]" in out          # recommended list
    assert "id:[20]" in out              # rare list beams
    assert "value:>=500000" in out       # value safety-net beam
    # recommended-only rule must NOT carry a beam; the rare + value rules must
    assert out.count("showLootbeam = true") >= 2
