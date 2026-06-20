from osrs_planner.lootfilter.categories import categorize
from osrs_planner.lootfilter.palette import MATERIAL_COLORS, RUNE_COLORS

def test_mithril_gear_is_metal():
    assert categorize("Mithril platebody")["id"] == "gear"
    assert categorize("Mithril platebody")["hue"] == MATERIAL_COLORS["mithril"]

def test_rune_ammo_and_essence_not_gear():
    assert categorize("Rune arrow")["id"] == "ammo"     # ammo, NOT rune gear
    assert categorize("Rune essence")["id"] == "essence"  # essence, NOT rune gear
    assert categorize("Runite ore")["id"] == "ores"     # ore, not gear

def test_black_mask_not_gear_dragon_bones_is_bones():
    assert categorize("Black mask") is None                  # slayer unique, not 'black gear'
    assert categorize("Dragon bones")["id"] == "bones"       # prayer supply -> bones, not 'dragon gear'
    assert categorize("Rune thrownaxe")["id"] == "ammo"      # ranged ammo, NOT melee 'axe' gear

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

def test_potion_liquids_are_distinct():
    # combat potions read their TRUE in-game liquid -- NOT a shared red
    assert categorize("Super combat potion(4)")["hue"] == "#ff2a7a14"   # dark green
    assert categorize("Attack potion(4)")["hue"] == "#ff5acce0"         # cyan
    assert categorize("Super strength(4)")["hue"] == "#ffe9e2d6"        # pale cream (not orange!)
    assert categorize("Antipoison(4)")["hue"] == "#ff8ee838"            # lime
    assert categorize("Saradomin brew(4)")["hue"] == "#ffe8e840"        # lemon yellow

def test_divine_takes_base_liquid():
    # divine = its base potion's colour (the icy border is added in emit, not the hue)
    assert categorize("Divine super combat potion(4)")["hue"] == categorize("Super combat potion(4)")["hue"]
    assert categorize("Divine ranging potion(4)")["hue"] == categorize("Ranging potion(4)")["hue"]

def test_niche_potion_falls_to_teal():
    assert categorize("Guthix balance(4)")["hue"] == "#ff20bfa0"        # no family -> apothecary teal
