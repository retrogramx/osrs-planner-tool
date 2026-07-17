# tests/lootfilter/test_emit_quantities.py
from osrs_planner.lootfilter.emit import emit_quantities

IMP = [
    {"item_id": 207, "name": "Grimy ranarr weed", "family": "herb", "base_tier": "A"},
    {"item_id": 199, "name": "Grimy guam leaf",   "family": "herb", "base_tier": "E"},
    {"item_id": 561, "name": "Nature rune",       "family": "rune", "base_tier": "A"},
]

def test_module_and_floor():
    out = emit_quantities(IMP)
    assert "define:module:quantities" in out
    assert "#define QUANTITY_FLOOR 0" in out
    assert "quantity:<QUANTITY_FLOOR" in out and "apply (IRONMAN" in out   # non-terminal hide

def test_base_A_emits_ss_s_a_thresholds_descending():
    out = emit_quantities([IMP[0]])   # base A -> SS(>=100), S(>=10), A(base, no quantity clause)
    assert "id:[207]" in out
    assert "quantity:>=100" in out and "quantity:>=10)" in out   # >=10 as a full token (closed by ')')
    assert out.index("quantity:>=100") < out.index("quantity:>=10)")   # SS threshold emitted before S

def test_base_E_reaches_deep_thresholds():
    out = emit_quantities([IMP[1]])          # base E -> up to quantity:>=1000000 for SS
    assert "quantity:>=1000000" in out and "id:[199]" in out

def test_per_element_hue_used_not_family():
    out = emit_quantities([IMP[2]])          # nature rune -> per-element green #ff2e8b57, not family indigo
    assert "#ff2e8b57" in out

def test_iron_gated():
    out = emit_quantities(IMP)
    assert out.count("rule (IRONMAN") == out.count("rule (")   # every terminal rule iron-gated
