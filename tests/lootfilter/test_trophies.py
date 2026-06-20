from osrs_planner.lootfilter.emit import emit_trophies

def test_trophies_never_hide_and_graded():
    out = emit_trophies([4151, 11920, 995])
    assert "apply (IRONMAN" in out and "hidden = false;" in out
    assert "id:[995, 4151, 11920]" in out
    assert "showLootbeam = true;" in out and "value:>=10000000" in out

def test_empty_clog_safe():
    assert "module:trophies" in emit_trophies([])
