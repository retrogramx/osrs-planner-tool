from kg_ingest.builders.world import is_excluded, build_world, parent_for
from osrs_planner.engine.kg.model import EdgeType


def test_is_excluded_list_index_and_discontinued():
    # (a) "List of ..." index pages
    assert is_excluded("List of dungeons", ["Dungeons"]) is True
    # (b) a title equal to an IN-category name (self-referential index page)
    assert is_excluded("Minigames", ["Minigames"]) is True
    assert is_excluded("Guilds", ["Guilds"]) is True
    # (c) discontinued / non-existent
    assert is_excluded("Duel Arena", ["Minigames", "Discontinued content"]) is True
    assert is_excluded("Isle of Garmr", ["Islands", "Locations that do not appear in-game"]) is True
    # a real place is NOT excluded
    assert is_excluded("Brimhaven Dungeon", ["Dungeons", "Karamja"]) is False


NOISE_SNAP = {
    "categories": {"Dungeons": ["Brimhaven Dungeon", "List of dungeons"], "Minigames": ["Minigames"]},
    "free_to_play": [], "members": [],
    "page_categories": {"Brimhaven Dungeon": ["Dungeons", "Karamja"],
                        "List of dungeons": ["Dungeons"], "Minigames": ["Minigames"]},
}
NOISE_BACKBONE = {"places": [
    {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": ""},
    {"id": "place:karamja", "place_type": "island", "name": "Karamja", "located_in": "place:gielinor"},
]}


def test_build_world_skips_noise_pages():
    nodes, edges, _ = build_world(NOISE_BACKBONE, NOISE_SNAP, set())
    ids = {n.id for n in nodes}
    assert "place:brimhaven-dungeon" in ids          # real place kept
    assert "place:list-of-dungeons" not in ids        # list index page dropped
    assert "place:minigames" not in ids               # self-referential index dropped


def test_parent_for_returns_signal_and_rungs():
    name_index = {"kandarin": "place:kandarin", "brimhaven": "place:brimhaven"}
    # rung 2: category-match
    assert parent_for("Catacombs of Kourend", {"Kandarin"}, name_index) == ("place:kandarin", "category")
    # rung 3: name-suffix
    assert parent_for("Brimhaven Dungeon", {"Caves"}, name_index) == ("place:brimhaven", "name-suffix")
    # rung 5: FLAG
    assert parent_for("Mystery Spot", set(), name_index) == ("place:gielinor", "FLAG")


# content place (an ingested island) must be eligible as a parent
CONTENT_SNAP = {
    "categories": {"Islands": ["Ardougne"], "Mines": ["Ardougne Sewers mine"]},
    "free_to_play": [], "members": [],
    "page_categories": {"Ardougne": ["Islands"], "Ardougne Sewers mine": ["Mines", "Ardougne"]},
}
CONTENT_BACKBONE = {"places": [
    {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": ""},
]}


def test_content_place_is_eligible_parent():
    nodes, edges, _ = build_world(CONTENT_BACKBONE, CONTENT_SNAP, set())
    li = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    # the mine parents to the INGESTED island 'place:ardougne' (not the root)
    assert ("place:ardougne-sewers-mine", "place:ardougne") in li


def test_category_rung_prefers_backbone_over_content():
    # A page with BOTH a content category (alphabetically first) and a backbone category
    # must parent to the BACKBONE place — content eligibility must not silently re-parent
    # a page that already has a backbone home. (Sulphur Mine regression: {Blast Mine, Lovakengj}
    # where Lovakengj is backbone and Blast Mine is content-inside-Sulphur-Mine.)
    name_index = {"lovakengj": "place:lovakengj", "blastmine": "place:blast-mine"}
    backbone_names = {"lovakengj"}
    assert parent_for("Sulphur Mine", {"Blast Mine", "Lovakengj"}, name_index,
                      backbone_names=backbone_names) == ("place:lovakengj", "category")
    # with NO backbone category, content still wins (genuine re-home preserved)
    assert parent_for("Ardougne Sewers mine", {"Mines", "Ardougne"},
                      {"ardougne": "place:ardougne"}, backbone_names=set()) == ("place:ardougne", "category")
