import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType, NodeKind

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_varrock_acquisition_spine():
    s = JsonKGStore.from_dir(KG)
    assert s.node("place:varrock").kind is NodeKind.PLACE
    assert s.node("shop:zaffs-superior-staffs").kind is NodeKind.SHOP
    # containment: Varrock -> Misthalin -> Mainland -> Gielinor (backbone now in world.json)
    loc = {(e.src, e.dst) for e in s.edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:varrock", "place:misthalin") in loc
    assert ("place:misthalin", "place:mainland") in loc
    assert ("place:mainland", "place:gielinor") in loc
    # containment + operates: Zaff operates his shop, shop is in Varrock
    assert ("npc:zaff", "shop:zaffs-superior-staffs") in {(e.src, e.dst) for e in s.edges if e.type is EdgeType.OPERATES}
    # battlestaff auto-imported via sells (confirmed in test_storeline_in_graph.py)
    assert s.node("item:1391") is not None

def test_place_region_bridge_and_unique_ids():
    s = JsonKGStore.from_dir(KG)
    assert ("place:varrock", "region:varrock") in {(e.src, e.dst) for e in s.edges if e.type is EdgeType.SAME_ENTITY}
    ids = [e.id for e in s.edges]
    assert len(ids) == len(set(ids))
