from kg_ingest.builders.shops import build_place_name_index, resolve_shop_places, build_shops
from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType

PLACES = [Node(id="place:al-kharid", kind=NodeKind.PLACE, name="Al Kharid", slug="al-kharid", data={}),
          Node(id="place:burthorpe", kind=NodeKind.PLACE, name="Burthorpe", slug="burthorpe", data={}),
          Node(id="place:draynor-village", kind=NodeKind.PLACE, name="Draynor Village", slug="draynor-village", data={})]

def test_name_index_maps_norm_name_to_id():
    idx = build_place_name_index(PLACES)
    assert idx["alkharid"] == "place:al-kharid"

def test_resolve_distinct_ordered():
    idx = build_place_name_index(PLACES)
    assert resolve_shop_places(["[[Burthorpe]]", "[[Draynor Village]]", "[[Burthorpe]]"], idx) == \
        ["place:burthorpe", "place:draynor-village"]

def _locedges(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}

def _shop(recs_name, locations):
    recs = [{"sold_by": recs_name, "sold_item": "Pot"}]
    ib = {recs_name: {"locations": locations, "members": "No", "owner": [], "icon": None}}
    return build_shops(recs, ib, PLACES, [], set())

def test_single_location_emits_located_in():
    nodes, edges, _ = _shop("Al Kharid General Store", ["[[Al Kharid]]"])
    assert ("shop:al-kharid-general-store", "place:al-kharid") in _locedges(edges)

def test_multi_location_defers_no_edge_flag_set():
    nodes, edges, _ = _shop("Slayer Rewards", ["[[Burthorpe]]", "[[Draynor Village]]"])
    assert _locedges(edges) == set()                          # NO arbitrary primary
    n = next(n for n in nodes if n.id == "shop:slayer-rewards")
    assert n.data["multi_location"] is True

def test_zero_resolution_flagged_no_edge():
    nodes, edges, _ = _shop("Mystery Shop", ["[[Nowheresville]]"])
    assert _locedges(edges) == set()
    n = next(n for n in nodes if n.id == "shop:mystery-shop")
    assert "multi_location" not in n.data                     # unparented FLAG, not multi
