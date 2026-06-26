import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType, NodeKind

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_committed_graph_has_charge_recipe_and_imported_materials():
    s = JsonKGStore.from_dir(KG)
    r = s.node("recipe:charge-scythe-of-vitur")
    assert r is not None and r.kind is NodeKind.RECIPE
    # materials auto-imported as item nodes via build_items (referenced mechanism)
    assert s.node("item:565") is not None   # Blood rune
    assert s.node("item:22446") is not None    # Vial of blood
    # consumes/produces edges present, recipe-src
    cons = {(e.src, e.dst, e.data.get("role")) for e in s.edges if e.type is EdgeType.CONSUMES}
    assert ("recipe:charge-scythe-of-vitur", "item:565", "material") in cons
    assert ("recipe:charge-scythe-of-vitur", "item:22486", "subject") in cons
    prod = {(e.src, e.dst) for e in s.edges if e.type is EdgeType.PRODUCES}
    assert ("recipe:charge-scythe-of-vitur", "item:22325") in prod
