from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for, TROPHY_GRADES, MATERIAL_COLORS

def test_grades_descend():
    assert [g[0] for g in VALUE_GRADES] == ["SS","S","A","B","C","D","E"]
    assert [g[1] for g in VALUE_GRADES] == [10_000_000,1_000_000,100_000,10_000,1_000,100,0]

def test_escalation_beam_at_S_sound_at_A():
    e = {g[0]: g[2] for g in VALUE_GRADES}
    assert e["S"]["beam"] and not e["A"]["beam"]
    assert e["A"]["sound"] and not e["B"]["sound"]

def test_style_for_renders_hue():
    s = style_for("#ff4169e1", "S")
    assert s["textColor"] == "#ff4169e1" and s["showLootbeam"] == "true" and s["lootbeamColor"] == "#ff4169e1"

def test_material_colors():
    for m in ("bronze","iron","steel","black","mithril","adamant","rune","dragon"):
        assert MATERIAL_COLORS[m].startswith("#ff") and len(MATERIAL_COLORS[m]) == 9

def test_trophy_always_beams():
    g = {x[0]: x[2] for x in TROPHY_GRADES}
    assert all(g[k]["beam"] and g[k]["sound"] for k in ("SS","S","A","B","C"))
