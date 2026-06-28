from kg_ingest.builders.world import _norm, classify, parent_for, members_of

def test_classify_priority():
    assert classify({"Raids", "Dungeons"}) == ("dungeon", "raid")          # raid beats dungeon
    assert classify({"Dungeons"}) == ("dungeon", "dungeon")
    assert classify({"Guilds"}) == ("point_of_interest", "guild")          # guild -> POI
    assert classify({"Minigames"}) == ("point_of_interest", "minigame")
    assert classify({"Settlements"}) == ("settlement", "settlement")
    assert classify({"Banks"}) is None                                     # OUT category -> not a place

def test_parent_region_category_then_name_heuristic():
    name2id = {"kandarin": "place:kandarin", "brimhaven": "place:brimhaven"}
    # region-category match (deepest)
    pid, flag = parent_for("Catacombs of Kourend", {"Kandarin"}, name2id)
    assert pid == "place:kandarin" and not flag
    # name-suffix fallback: "Brimhaven Dungeon" -> Brimhaven
    pid, flag = parent_for("Brimhaven Dungeon", {"Caves"}, name2id)
    assert pid == "place:brimhaven" and not flag
    # nothing matches -> flagged, parent gielinor
    pid, flag = parent_for("Mystery Spot", set(), name2id)
    assert pid == "place:gielinor" and flag

def test_members_flag():
    assert members_of("Lletya", {"Catherby"}, {"Lletya"}) is True
    assert members_of("Lumbridge", {"Lumbridge"}, {"Darkmeyer"}) is False
    assert members_of("Nowhere", {"X"}, {"Y"}) is None
