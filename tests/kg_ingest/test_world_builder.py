from kg_ingest.builders.world import _norm, classify, parent_for, members_of, build_world
from osrs_planner.engine.kg.model import EdgeType

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


BACKBONE = {"places": [
    {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": "",
     "source_url": "https://oldschool.runescape.wiki/w/Gielinor"},
    {"id": "place:mainland", "place_type": "continent", "name": "Mainland", "located_in": "place:gielinor",
     "source_url": "https://oldschool.runescape.wiki/w/Gielinor"},
    {"id": "place:kandarin", "place_type": "kingdom", "name": "Kandarin", "located_in": "place:mainland",
     "ruled_by": "King Lathas", "members": True, "source_url": "https://oldschool.runescape.wiki/w/Kandarin",
     "same_entity": "region:kandarin"},
    {"id": "place:brimhaven", "place_type": "town", "name": "Brimhaven", "located_in": "place:kandarin",
     "source_url": "https://oldschool.runescape.wiki/w/Brimhaven"},
]}
SNAP = {"categories": {"Dungeons": ["Brimhaven Dungeon", "Catacombs of Kourend"], "Banks": ["Brimhaven bank"]},
        "free_to_play": [], "members": ["Brimhaven Dungeon", "Catacombs of Kourend"],
        "page_categories": {"Brimhaven Dungeon": ["Dungeons", "Karamja"], "Catacombs of Kourend": ["Dungeons", "Kandarin"]}}

def test_build_world_backbone_plus_ingest():
    nodes, edges, groups = build_world(BACKBONE, SNAP, {"region:kandarin"})
    ids = {n.id for n in nodes}
    assert "place:gielinor" in ids and "place:brimhaven" in ids   # backbone emitted
    assert "place:brimhaven-dungeon" in ids                        # ingested dungeon
    assert "place:brimhaven-bank" not in ids                       # Banks is OUT
    # ingested dungeon typed + parented (name-heuristic -> Brimhaven)
    d = next(n for n in nodes if n.id == "place:brimhaven-dungeon")
    assert d.data["place_type"] == "dungeon" and d.data["content_kind"] == "dungeon"
    li = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:brimhaven-dungeon", "place:brimhaven") in li    # parented
    assert ("place:kandarin", "place:mainland") in li              # backbone located_in
    # same_entity bridge only where region node exists
    se = {(e.src, e.dst) for e in edges if e.type is EdgeType.SAME_ENTITY}
    assert ("place:kandarin", "region:kandarin") in se
    assert d.data["members"] is True                               # members flag

def test_catacombs_parents_to_kandarin_via_region_category():
    nodes, edges, groups = build_world(BACKBONE, SNAP, set())
    li = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:catacombs-of-kourend", "place:kandarin") in li
