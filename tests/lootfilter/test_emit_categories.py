from osrs_planner.lootfilter.emit import emit_categories
from osrs_planner.lootfilter.categories import category_rules

def test_no_bare_metal_glob():
    pats = [p for row in category_rules() for p in row[2]]   # row[2] = patterns (rows are 5- or 6-tuples)
    assert "Rune *" not in pats and "Mithril *" not in pats   # explicit lists only
    assert "Mithril platebody" in pats and "Mithril scimitar" in pats

def test_ore_bar_rune_rows_moved_to_quantities():
    # ores/bars/runes/gems/essence/ammo/logs/herbs/seeds/bones/food are TRIMMED out of category_rules
    # (design §4): they now live in the per-family modules (emit_family_module), ranked by
    # loot_importance.json. category_rules() keeps only the non-bulk remainder (gear-metal,
    # teleports, charged jewellery, potions).
    ids = {row[0] for row in category_rules()}
    assert ids == {"gear", "teleports", "charged_jewellery", "potions"}
    pats = [p for row in category_rules() for p in row[2]]
    assert "Runite ore" not in pats and "Adamantite bar" not in pats and "Coal" not in pats
    assert "Fire rune" not in pats and "Crystal weapon seed" not in " ".join(pats)

def test_emit_has_mithril_blue_and_gear_only_categories():
    out = emit_categories()
    assert '"Mithril platebody"' in out and "#ff4169e1" in out
    assert out.count("module:categories") == 1 and "IRONMAN &&" in out
    # ores/bars/runes/seeds no longer live in the categories module
    assert '"Fire rune"' not in out and "Coal" not in out and "Crystal weapon seed" not in out

def test_divine_icy_border_in_output():
    out = emit_categories()
    # divine potions emit their base hue + the icy crystal-dust border (the 6th tuple elem)
    assert '"Divine super combat potion(*"' in out and "#ffaee8ff" in out
    assert '"Divine ranging potion(*"' in out
