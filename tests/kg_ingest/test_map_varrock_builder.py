from kg_ingest.builders.map_varrock import make_item_resolver, build_map
from osrs_planner.engine.kg.model import NodeKind, EdgeType, AtomType, Op, EdgeType as _ET

DICT = [
    {"item_id": 1391, "name": "Battlestaff", "page_name": "Battlestaff", "is_canonical": True, "is_variant": False, "members": True},
    {"item_id": 1381, "name": "Staff of air", "page_name": "Staff of air", "is_canonical": True, "is_variant": False, "members": False},
]
MAP = {
    "places": [
        {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": None},
        {"id": "place:misthalin", "place_type": "kingdom", "name": "Misthalin", "located_in": "place:gielinor", "ruled_by": "King Roald III"},
        {"id": "place:varrock", "place_type": "city", "name": "Varrock", "located_in": "place:misthalin"},
    ],
    "npcs": [
        {"id": "npc:zaff", "name": "Zaff", "role": "shopkeeper", "located_in": "place:varrock", "operates": ["shop:zaffs-superior-staffs"]},
        {"id": "npc:bystander", "name": "Bystander", "role": "citizen", "located_in": "place:varrock"},
    ],
    "shops": [
        {"id": "shop:zaffs-superior-staffs", "name": "Zaff's Superior Staffs", "shop_type": "magic",
         "located_in": "place:varrock", "operator": "npc:zaff", "currency": "coins",
         "sells": [
             {"item_name": "Staff of air", "item_id": None, "source_token": "elemental staves"},
             {"item_name": "Battlestaff", "item_id": None, "source_token": "after What Lies Below",
              "condition": {"type": "quest", "ref": "What Lies Below", "state": "in_progress"}},
             {"item_name": "Battlestaff (noted)", "item_id": None, "noted": True, "source_token": "discount",
              "condition": {"type": "achievement_diary", "ref": "Varrock Diary - Hard", "state": "completed"}},
             {"item_name": "Nonexistent Doohickey", "item_id": None, "source_token": "x"},
         ]},
    ],
}

def test_resolver_canonical_match_and_miss():
    r = make_item_resolver(DICT)
    assert r("Battlestaff") == 1391
    assert r("Battlestaff (noted)") == 1391
    assert r("Nonexistent Doohickey") is None

def test_resolver_page_name_disambiguation():
    # Two canonical "Beer" records differing only by page_name: the bare-name page wins.
    beer_dict = [
        {"item_id": 1917, "name": "Beer", "page_name": "Beer", "is_canonical": True, "is_variant": False, "members": False},
        {"item_id": 7740, "name": "Beer", "page_name": "Beer (Player-owned house)", "is_canonical": True, "is_variant": False, "members": True},
    ]
    r = make_item_resolver(beer_dict)
    assert r("Beer") == 1917                          # bare-page "Beer" disambiguates over the POH variant
    # If NO record has a bare-name page, it stays ambiguous -> None (reported residual).
    ambiguous = [
        {"item_id": 10, "name": "Widget", "page_name": "Widget (A)", "is_canonical": True, "is_variant": False, "members": False},
        {"item_id": 11, "name": "Widget", "page_name": "Widget (B)", "is_canonical": True, "is_variant": False, "members": False},
    ]
    assert make_item_resolver(ambiguous)("Widget") is None

def test_places_npcs_shops_and_located_in():
    nodes, edges, _ = build_map(MAP, make_item_resolver(DICT), {"region:varrock"})
    kinds = {n.id: n.kind for n in nodes}
    assert kinds["place:varrock"] is NodeKind.PLACE and kinds["shop:zaffs-superior-staffs"] is NodeKind.SHOP
    assert kinds["npc:zaff"] is NodeKind.NPC
    assert "npc:bystander" not in kinds          # only shop OPERATORS are emitted
    loc = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:varrock", "place:misthalin") in loc and ("shop:zaffs-superior-staffs", "place:varrock") in loc
    assert ("npc:zaff", "shop:zaffs-superior-staffs") in {(e.src, e.dst) for e in edges if e.type is EdgeType.OPERATES}
    # same_entity bridge for the place that has a legacy region node
    assert ("place:varrock", "region:varrock") in {(e.src, e.dst) for e in edges if e.type is EdgeType.SAME_ENTITY}

def test_build_map_emits_no_sells():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    m = json.loads((root / "data" / "map" / "varrock.json").read_text())
    resolve = make_item_resolver(json.loads((root / "data" / "item_dictionary.json").read_text())["records"])
    nodes, edges, groups = build_map(m, resolve, set())
    assert not any(e.type is _ET.SELLS for e in edges)   # sells now come from build_storeline
    assert groups == {}                                  # gate groups moved to build_storeline
    assert any(e.type is _ET.LOCATED_IN for e in edges)  # containment still emitted

