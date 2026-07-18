import os
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
F = open(os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"), encoding="utf-8").read()
def test_mithril_gear_blue():
    assert '"Mithril platebody"' in F and "#ff4169e1" in F
def test_no_fake_items():
    assert "Bronze ore" not in F and "Rune bar" not in F and "Rune *" not in F
def test_trophy_and_ladder_and_floor():
    assert "module:trophies" in F and "value:>=10000000" in F and "#define HIDE_FLOOR 0" in F
def test_iron_gated_generic_has_no_tailoring():
    # starts with a module decl (FilterScape needs this); meta{} present but last; no tailoring
    assert "accountType:1" in F and F.startswith("/*@ define:module:") and "meta {" in F and "module:tailoring" not in F
def test_new_layers_present():
    # Verify the itemization layers (custom, notable, gear, and a per-family module) and the
    # value safety-net beam are present
    for mod in ("custom", "notable", "gear", "seeds"):
        assert f"define:module:{mod}" in F, f"Module {mod} not found in filter"
    assert "value:>=500000" in F, "Value safety-net beam (>=500000) not found in filter"
def test_family_modules_present():
    for mid in ["seeds", "herbs", "runes", "ores", "bars", "logs", "planks", "gems", "ammo", "food", "prayer", "essence"]:
        assert f"define:module:{mid}" in F
    assert "define:module:quantities" not in F     # retired
    assert "define:module:families" not in F       # retired
