from osrs_planner.lootfilter.categories import categorize
from osrs_planner.lootfilter.palette import MATERIAL_COLORS, RUNE_COLORS

def test_mithril_gear_is_metal():
    assert categorize("Mithril platebody")["id"] == "gear"
    assert categorize("Mithril platebody")["hue"] == MATERIAL_COLORS["mithril"]

def test_rune_ammo_and_essence_not_gear():
    assert categorize("Rune arrow") is None
    assert categorize("Rune essence") is None
    assert categorize("Runite ore")["id"] == "ores"     # ore, not gear

def test_black_mask_not_gear_dragon_bones_is_bones():
    assert categorize("Black mask") is None                  # slayer unique, not 'black gear'
    assert categorize("Dragon bones")["id"] == "bones"       # prayer supply -> bones, not 'dragon gear'
    assert categorize("Rune thrownaxe") is None              # ranged ammo, not melee 'axe' gear

def test_fire_rune_is_rune():
    c = categorize("Fire rune")
    assert c["id"] == "runes" and c["hue"] == RUNE_COLORS["fire"]

def test_grimy_herb_is_herb():
    assert categorize("Grimy ranarr weed")["id"] == "herbs"

def test_crystal_seed_not_seed_category():
    assert categorize("Crystal weapon seed") is None     # high-value unique, not a green seed
    assert categorize("Ranarr seed")["id"] == "seeds"

def test_twisted_bow_falls_through():
    assert categorize("Twisted bow") is None
