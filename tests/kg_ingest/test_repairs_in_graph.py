import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_repairs_edges_and_barrelchest_autoimport():
    s = JsonKGStore.from_dir(KG)
    # Dharok's helm broken -> undamaged (endpoints from slice 3)
    dh = [e for e in s.edges if e.type is EdgeType.REPAIRS and e.src == "item:4884"]
    assert len(dh) == 1 and dh[0].dst == "item:4716" and dh[0].data == {}
    # Barrelchest anchor: both variants auto-imported + the repairs edge
    assert s.node("item:10887") is not None and s.node("item:10888") is not None
    bc = [e for e in s.edges if e.type is EdgeType.REPAIRS and e.src == "item:10888"]
    assert len(bc) == 1 and bc[0].dst == "item:10887"

def test_all_edge_ids_unique_with_three_item_src_edge_types():
    # same_entity + degrades_to + repairs are all item-src and share one rekey call;
    # the committed graph must have zero duplicate edge ids.
    s = JsonKGStore.from_dir(KG)
    ids = [e.id for e in s.edges]
    assert len(ids) == len(set(ids)), "duplicate edge id in committed graph"
