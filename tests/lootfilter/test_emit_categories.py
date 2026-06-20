from osrs_planner.lootfilter.emit import emit_categories
from osrs_planner.lootfilter.categories import category_rules

def test_no_bare_metal_glob():
    pats = [p for row in category_rules() for p in row[2]]   # row[2] = patterns (rows are 5- or 6-tuples)
    assert "Rune *" not in pats and "Mithril *" not in pats   # explicit lists only
    assert "Mithril platebody" in pats and "Mithril scimitar" in pats

def test_real_ore_bar_names_only():
    pats = [p for row in category_rules() for p in row[2]]
    assert "Runite ore" in pats and "Adamantite bar" in pats and "Coal" in pats
    assert "Bronze ore" not in pats and "Rune bar" not in pats  # non-existent items

def test_emit_has_mithril_blue_fire_red_and_seed_exclusion():
    out = emit_categories()
    assert '"Mithril platebody"' in out and "#ff4169e1" in out
    assert '"Fire rune"' in out and "#ffff4500" in out
    assert "Crystal weapon seed" in out and "!name:" in out     # seed exclusion present
    assert out.count("module:categories") == 1 and "IRONMAN &&" in out

def test_ore_bar_hue_identity():
    out = emit_categories()
    # Coal reads dark, Gold reads gold -- NOT borrowed gear-metal steel/dragon hues
    assert '"Coal"' in out and "#ff2b2b2b" in out               # Coal dark, not steel grey
    assert "#ffd8b01a" in out                                   # Gold ore/bar gold, not dragon red

def test_divine_icy_border_in_output():
    out = emit_categories()
    # divine potions emit their base hue + the icy crystal-dust border (the 6th tuple elem)
    assert '"Divine super combat potion(*"' in out and "#ffaee8ff" in out
    assert '"Divine ranging potion(*"' in out
