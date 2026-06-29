from kg_ingest.builders.npcs import build_npcs
from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType

PLACES = [Node(id="place:al-kharid", kind=NodeKind.PLACE, name="Al Kharid", slug="al-kharid", data={}),
          Node(id="place:burthorpe", kind=NodeKind.PLACE, name="Burthorpe", slug="burthorpe", data={})]

def _loc(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}

def _build(name, locations):
    recs = [{"sold_by": "S"}]
    shop_ib = {"S": {"owner": [f"[[{name}]]"]}}
    npc_ib = {name: {"locations": locations, "is_npc": True}}
    return build_npcs(recs, shop_ib, npc_ib, PLACES, set(), set())

def test_single_location_emits_located_in():
    nodes, edges, _ = _build("Ali the Kebab seller", ["[[Al Kharid]]"])
    assert ("npc:ali-the-kebab-seller", "place:al-kharid") in _loc(edges)

def test_multi_location_defers_no_edge_flag():
    nodes, edges, _ = _build("Wanderer", ["[[Al Kharid]]", "[[Burthorpe]]"])
    assert _loc(edges) == set()
    assert next(n for n in nodes if n.id == "npc:wanderer").data["multi_location"] is True

def test_zero_resolution_flag_no_edge():
    nodes, edges, _ = _build("Ghost", ["[[Nowhere]]"])
    assert _loc(edges) == set()
    assert "multi_location" not in next(n for n in nodes if n.id == "npc:ghost").data
