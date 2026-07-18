from osrs_planner.lootfilter.emit import (
    _quoted_list, emit_enumlist_input, emit_number_input, emit_style_def)
from osrs_planner.lootfilter.palette import style_for, FAMILY_HUES

def test_quoted_list_quotes_and_escapes():
    assert _quoted_list(["Ranarr seed", "Guam seed"]) == '["Ranarr seed", "Guam seed"]'

def test_enumlist_input_declares_enum_and_default():
    out = emit_enumlist_input("seeds", "Items", "SS tier",
                              ["Ranarr seed", "Guam seed"], "SEEDS_SS_NAMES", ["Ranarr seed"])
    assert "type: enumlist" in out
    assert 'enum: ["Ranarr seed", "Guam seed"]' in out
    assert 'label: "Items"' in out and 'group: "SS tier"' in out
    assert "#define SEEDS_SS_NAMES [\"Ranarr seed\"]" in out

def test_number_input():
    out = emit_number_input("seeds", "Minimum quantity", "SS tier", "SEEDS_SS_MIN", 1)
    assert "type: number" in out and 'label: "Minimum quantity"' in out
    assert "#define SEEDS_SS_MIN 1" in out

def test_style_def_has_no_rule():
    out = emit_style_def("seeds", "Colour", "SS tier", "SEEDS_SS_STYLE", style_for(FAMILY_HUES["seed"], "A"))
    assert "type: style" in out and "#define SEEDS_SS_STYLE" in out
    assert "rule (" not in out and "apply (" not in out
