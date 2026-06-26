from kg_ingest.builders.repairs import build_repairs
from osrs_planner.engine.kg.model import EdgeType

REC = [
    {"slug": "repair-dharoks-helm", "page": "Dharok's helm", "broken": 4884, "repaired": 4716},
    {"slug": "repair-barrelchest-anchor", "page": "Barrelchest anchor", "broken": 10888, "repaired": 10887},
]

def test_one_repairs_edge_per_record_item_src_empty_data():
    nodes, edges, groups = build_repairs(REC)
    assert nodes == [] and groups == {}
    pairs = [(e.src, e.dst) for e in edges if e.type is EdgeType.REPAIRS]
    assert ("item:4884", "item:4716") in pairs        # Dharok's helm broken -> undamaged
    assert ("item:10888", "item:10887") in pairs      # Barrelchest broken -> fixed
    assert all(e.data == {} and e.cond_group is None for e in edges)   # pure transition
    assert all(e.src.startswith("item:") for e in edges)               # item-src


def test_repairs_edges_are_deterministic():
    e1 = build_repairs(REC)[1]
    e2 = build_repairs(REC)[1]
    assert [(e.id, e.src, e.dst) for e in e1] == [(e.id, e.src, e.dst) for e in e2]
