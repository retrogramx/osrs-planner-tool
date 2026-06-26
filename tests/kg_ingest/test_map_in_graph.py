import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType, NodeKind

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_varrock_acquisition_spine():
    s = JsonKGStore.from_dir(KG)
    assert s.node("place:varrock").kind is NodeKind.PLACE
    assert s.node("shop:zaffs-superior-staffs").kind is NodeKind.SHOP
    # containment: Varrock -> Misthalin -> Gielinor
    loc = {(e.src, e.dst) for e in s.edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:varrock", "place:misthalin") in loc and ("place:misthalin", "place:gielinor") in loc
    # acquisition path: battlestaff <- sells <- Zaff's shop <- operates <- Zaff ; shop located_in Varrock
    assert ("npc:zaff", "shop:zaffs-superior-staffs") in {(e.src, e.dst) for e in s.edges if e.type is EdgeType.OPERATES}
    sells = [e for e in s.edges if e.type is EdgeType.SELLS and e.dst == "item:1391"]
    assert sells and sells[0].src == "shop:zaffs-superior-staffs"
    assert s.node("item:1391") is not None        # battlestaff auto-imported
    # the gated offer carries a cond_group resolvable in the graph's groups
    gated = [e for e in sells if e.cond_group is not None]
    assert gated, "expected a What-Lies-Below-gated battlestaff sell"

def test_place_region_bridge_and_unique_ids():
    s = JsonKGStore.from_dir(KG)
    assert ("place:varrock", "region:varrock") in {(e.src, e.dst) for e in s.edges if e.type is EdgeType.SAME_ENTITY}
    ids = [e.id for e in s.edges]
    assert len(ids) == len(set(ids))
