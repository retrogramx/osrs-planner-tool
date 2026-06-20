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
    assert "accountType:1" in F and F.startswith("meta {") and "module:tailoring" not in F
