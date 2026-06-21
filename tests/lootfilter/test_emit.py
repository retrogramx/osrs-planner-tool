from osrs_planner.lootfilter.emit import emit_meta, emit_rule, style_str, emit_fallback, emit_preamble

def test_meta():
    assert 'name = "Gilded Tome — Iron";' in emit_meta("Gilded Tome — Iron", "x")

def test_style_str():
    assert style_str({"textColor": "#ff4169e1", "showLootbeam": "true"}) == '{ textColor = "#ff4169e1"; showLootbeam = true; }'

def test_emit_rule_terminal_and_apply():
    assert emit_rule("IRONMAN && value:>=1000", {"textColor": "#ffffffff"}).startswith("rule (")
    assert emit_rule("ownership:2", {"hidden": "true"}, terminal=False).startswith("apply (")

def test_core_macros_in_first_module_not_orphaned():
    from osrs_planner.lootfilter.emit import emit_settings
    s = emit_settings()
    assert "#define IRONMAN accountType:1" in s and "#define HIDE_FLOOR 0" in s  # in the FIRST module's body
    assert emit_preamble() == ""   # empty -> filter STARTS with a module declaration (FilterScape needs this)

def test_modules_carry_filterscape_fields():
    from osrs_planner.lootfilter.emit import emit_module
    m = emit_module("demo", "Demo", "rule (x) {}")     # web customizer requires name+subtitle+description
    assert "name: Demo" in m and "subtitle:" in m and "description: |" in m

def test_fallback_iron_gated_with_hide_floor():
    fb = emit_fallback()
    assert fb.count("rule (IRONMAN") == 8                 # 7 grades + 1 HIDE_FLOOR cut
    assert "value:<HIDE_FLOOR" in fb and "value:>=10000000" in fb and "value:>=0" in fb

def test_clue_tiers_seal_colour_plus_parchment_border():
    from osrs_planner.lootfilter.emit import emit_untradeables
    out = emit_untradeables()
    assert '"Clue scroll (hard)"' in out and "#ffa83cc6" in out      # hard = purple seal
    assert '"Reward casket (master)"' in out and "#ffc4342a" in out  # master = red seal
    # parchment border is the shared clue signature -- in all 6 clue STYLE MACROS, nowhere else
    parch = [l for l in out.splitlines() if "#ffc8b088" in l]
    assert len(parch) == 6 and all(l.startswith("#define CLUE_") for l in parch)

def test_categories_are_editable_style_inputs():
    from osrs_planner.lootfilter.emit import emit_categories
    out = emit_categories()
    # every group is a FilterScape colour picker: type:style input + #define + rule-applies-macro
    assert "type: style" in out and "#define CAT_" in out and "{ CAT_" in out
    assert "group: Potions" in out and "group: Gear" in out    # organised into collapsible groups
