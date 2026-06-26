from kg_ingest.builders.map_varrock import make_item_resolver, build_map
from osrs_planner.engine.kg.model import NodeKind, EdgeType, AtomType, Op

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
    assert r("Nonexistent Doohickey") is None

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

def test_sells_resolution_skip_and_conditional_gate():
    nodes, edges, groups = build_map(MAP, make_item_resolver(DICT), set())
    sells = {e.dst: e for e in edges if e.type is EdgeType.SELLS}
    assert "item:1391" in sells and "item:1381" in sells     # resolved
    assert all(e.src == "shop:zaffs-superior-staffs" for e in edges if e.type is EdgeType.SELLS)
    assert len([e for e in edges if e.type is EdgeType.SELLS]) == 3   # the unresolvable one is SKIPPED
    # the gated Battlestaff sell carries a cond_group -> a group with a QUEST atom
    gated = sells["item:1391"]
    assert gated.cond_group is not None
    g = groups[gated.cond_group]
    assert g.op is Op.AND and g.children[0].atom_type is AtomType.QUEST
    assert g.children[0].ref_node == "quest:what-lies-below" and g.children[0].data["state"] == "in_progress"
    # the diary-gated noted sell -> ACHIEVEMENT_DIARY atom, ref diary:varrock:hard
    diary = groups[[e for e in edges if e.type is EdgeType.SELLS and e.data.get("noted")][0].cond_group]
    assert diary.children[0].atom_type is AtomType.ACHIEVEMENT_DIARY and diary.children[0].ref_node == "diary:varrock:hard"
