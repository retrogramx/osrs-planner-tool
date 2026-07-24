from osrs_planner.lootfilter.emit import emit_family_module

ROWS = [
    {"item_id": 5295, "name": "Ranarr seed",  "family": "seed", "base_tier": "A"},
    {"item_id": 5318, "name": "Potato seed",  "family": "seed", "base_tier": "E"},
    {"item_id": 5319, "name": "Potato seed",  "family": "seed", "base_tier": "E"},  # dup name
]

def test_module_has_plain_labels_and_tier_groups():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    assert 'name: "Seeds"' in m and 'subtitle: "Farming seeds"' in m
    assert 'group: "A tier"' in m and 'group: "E tier"' in m
    assert 'label: "Items"' in m and 'label: "Minimum quantity"' in m and 'label: "Colour"' in m
    assert "—" not in m                                          # no AI-sounding em-dash anywhere
    # no colon INSIDE any label value (the `label: "..."` separator is fine; the quoted text is not)
    import re as _re
    for val in _re.findall(r'label: "([^"]*)"', m):
        assert ":" not in val, f"label has a colon: {val!r}"

def test_enum_is_full_family_default_is_tier():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    assert 'enum: ["Potato seed", "Ranarr seed"]' in m           # full family, sorted, deduped
    assert '#define SEEDS_A_NAMES ["Ranarr seed"]' in m           # A default
    assert '#define SEEDS_E_NAMES ["Potato seed"]' in m           # E default, deduped

def test_ss_tier_group_exists_as_escalation_target():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    assert "#define SEEDS_SS_STYLE" in m                          # SS colour exists even with no SS members

def test_escalation_promotes_A_to_higher_tier_by_count():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    # A base: >=10 -> S colour, >=100 -> SS colour, base -> A colour
    assert "name:SEEDS_A_NAMES && quantity:>=100) { SEEDS_SS_STYLE }" in m
    assert "name:SEEDS_A_NAMES && quantity:>=10) { SEEDS_S_STYLE }" in m
    assert "name:SEEDS_A_NAMES && quantity:<SEEDS_A_MIN)" in m
    assert m.index("quantity:>=100) { SEEDS_SS_STYLE }") < m.index("quantity:>=10) { SEEDS_S_STYLE }")

def test_every_rule_iron_gated():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    rule_lines = [l for l in m.splitlines() if l.startswith("rule (") or l.startswith("apply (")]
    assert rule_lines and all("IRONMAN" in l for l in rule_lines)

def test_empty_tier_items_and_min_inputs_have_rules():
    # Re-tiering an item into an empty tier (SS/S) via the FilterScape dropdown must WORK:
    # every emitted NAMES/MIN macro needs at least one rule referencing it.
    import re as _re
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    rule_text = "\n".join(l for l in m.splitlines() if l.startswith("rule ("))
    for macro in _re.findall(r"#define (SEEDS_\w+_(?:NAMES|MIN)) ", m):
        assert macro in rule_text, f"input macro {macro} is defined but no rule references it"

def test_min_quantity_hide_rule_precedes_escalation():
    # "Minimum quantity" must mean what it says for MIN > 10: the hide rule has to sit
    # ABOVE the x10 escalation decades or a 10..MIN-1 pile escalates instead of hiding.
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    hide = m.index("name:SEEDS_A_NAMES && quantity:<SEEDS_A_MIN")
    assert hide < m.index("name:SEEDS_A_NAMES && quantity:>=100")
    assert hide < m.index("name:SEEDS_A_NAMES && quantity:>=10)")
