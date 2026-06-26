from kg_ingest.builders.recipes import build_recipes
from osrs_planner.engine.kg.model import EdgeType, NodeKind

REC = [{
    "slug": "charge-scythe-of-vitur", "name": "Charge Scythe of vitur",
    "produces": {"item_id": 22325, "qty": 1},
    "subject":  {"item_id": 22486, "qty": 1},
    "materials": [{"item_id": 565, "qty": 200, "name": "Blood rune"},
                  {"item_id": 22446, "qty": 1, "name": "Vial of blood"}],
    "charge_yield": 100, "charge_capacity": 20000,
}]

def test_recipe_node_consumes_and_produces():
    nodes, edges, groups = build_recipes(REC)
    assert groups == {}
    n = {x.id: x for x in nodes}["recipe:charge-scythe-of-vitur"]
    assert n.kind is NodeKind.RECIPE and n.name == "Charge Scythe of vitur"
    assert n.data == {"charge_yield": 100, "charge_capacity": 20000}
    consumes = [(e.dst, e.data["qty"], e.data["role"]) for e in edges if e.type is EdgeType.CONSUMES]
    assert ("item:565", 200, "material") in consumes
    assert ("item:22446", 1, "material") in consumes
    assert ("item:22486", 1, "subject") in consumes      # the uncharged variant, role=subject
    produces = [(e.dst, e.data["qty"]) for e in edges if e.type is EdgeType.PRODUCES]
    assert produces == [("item:22325", 1)]
    assert all(e.src == "recipe:charge-scythe-of-vitur" for e in edges)   # all edges recipe-src

def test_recipe_edges_are_deterministic():
    e1 = build_recipes(REC)[1]
    e2 = build_recipes(REC)[1]
    assert [(e.id, e.type, e.dst) for e in e1] == [(e.id, e.type, e.dst) for e in e2]
