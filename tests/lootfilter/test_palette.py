from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for, TROPHY_GRADES, MATERIAL_COLORS

def test_grades_descend():
    assert [g[0] for g in VALUE_GRADES] == ["SS","S","A","B","C","D","E"]
    assert [g[1] for g in VALUE_GRADES] == [10_000_000,1_000_000,100_000,10_000,1_000,100,0]

def test_escalation_beam_at_S_sound_at_A():
    e = {g[0]: g[2] for g in VALUE_GRADES}
    assert e["S"]["beam"] and not e["A"]["beam"]
    assert e["A"]["sound"] and not e["B"]["sound"]

def test_style_for_renders_hue():
    s = style_for("#ff4169e1", "S")  # S grade: solid hue PANEL + beam (text is auto-contrast, not the hue)
    assert s["backgroundColor"] == "#ff4169e1" and s["showLootbeam"] == "true" and s["lootbeamColor"] == "#ff4169e1"

def test_style_for_border_override():
    # divine potions pass an icy border that overrides the auto-contrast border
    assert style_for("#ff2a7a14", "C", border="#ffaee8ff")["borderColor"] == "#ffaee8ff"

def test_style_for_low_value_is_text_only():
    # D/E (cheap uncategorised loot) is plain text -- no panel -> keeps the screen calm
    assert "backgroundColor" not in style_for("#ff52e052", "E")

def test_material_colors():
    for m in ("bronze","iron","steel","black","mithril","adamant","rune","dragon"):
        assert MATERIAL_COLORS[m].startswith("#ff") and len(MATERIAL_COLORS[m]) == 9

def test_trophy_always_beams():
    g = {x[0]: x[2] for x in TROPHY_GRADES}
    assert all(g[k]["beam"] and g[k]["sound"] for k in ("SS","S","A","B","C"))

def test_style_for_beam_comes_from_table_not_hardcode():
    # Flip the S-grade table row's beam off; style_for must reflect the TABLE.
    orig = dict(next(e for g,_m,e in VALUE_GRADES if g == "S"))
    row = next(e for g,_m,e in VALUE_GRADES if g == "S")
    row["beam"] = False
    try:
        s = style_for("#ff40e0d0", "S")
        assert "showLootbeam" not in s, "beam must be driven by the table's `beam` flag"
    finally:
        row.clear(); row.update(orig)

def test_style_for_beam_on_by_table():
    s = style_for("#ff40e0d0", "SS")
    assert s.get("showLootbeam") == "true" and s["lootbeamColor"] == "#ff40e0d0"
