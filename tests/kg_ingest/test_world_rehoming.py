from kg_ingest.builders.world import is_excluded, build_world
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
