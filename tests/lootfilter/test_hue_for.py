from osrs_planner.lootfilter.emit import hue_for
from osrs_planner.lootfilter.palette import FAMILY_HUES

def test_per_name_hue_wins():
    assert hue_for("Coal", "ore") == "#ff2b2b2b"            # categorize() ore per-name (dark), not family
    assert hue_for("Nature rune", "rune") == "#ff2e8b57"    # per-element rune hue
    assert hue_for("Magic logs", "log") == "#ff5090d0"      # per-tree log hue

def test_family_fallback():
    # an item categorize() does not resolve (e.g. an essence name) falls to the family hue
    assert hue_for("Pure essence", "essence") == "#ff7d7da0"  # categorize essence hue OR FAMILY? essence categorizes
    # a family with no per-name hue and no categorize match uses FAMILY_HUES
    assert hue_for("Nonexistent thing", "seed") == FAMILY_HUES["seed"]

def test_unknown_family_grey():
    assert hue_for("???", "not_a_family") == "#ff9e9e9e"
