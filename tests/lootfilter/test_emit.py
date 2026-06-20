from osrs_planner.lootfilter.emit import emit_meta, emit_rule, style_str, emit_fallback, emit_preamble

def test_meta():
    assert 'name = "Gilded Tome — Iron";' in emit_meta("Gilded Tome — Iron", "x")

def test_style_str():
    assert style_str({"textColor": "#ff4169e1", "showLootbeam": "true"}) == '{ textColor = "#ff4169e1"; showLootbeam = true; }'

def test_emit_rule_terminal_and_apply():
    assert emit_rule("IRONMAN && value:>=1000", {"textColor": "#ffffffff"}).startswith("rule (")
    assert emit_rule("ownership:2", {"hidden": "true"}, terminal=False).startswith("apply (")

def test_preamble_defines_macros():
    p = emit_preamble()
    assert "#define IRONMAN accountType:1" in p and "#define HIDE_FLOOR 0" in p

def test_fallback_iron_gated_with_hide_floor():
    fb = emit_fallback()
    assert fb.count("rule (IRONMAN") == 8                 # 7 grades + 1 HIDE_FLOOR cut
    assert "value:<HIDE_FLOOR" in fb and "value:>=10000000" in fb and "value:>=0" in fb
