import json, pathlib
from osrs_planner.engine.kg.model import EdgeType
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_requires_facility_edgetype_exists():
    assert EdgeType("requires_facility") is EdgeType.REQUIRES_FACILITY

def test_schema_additive_changes():
    s = json.loads((ROOT / "kg" / "schema.json").read_text())
    assert s["edge_kinds"]["requires_facility"]["status"] == "live"
    assert "tool" in s["vocab"]["consumes_role"]
    assert "members" in s["node_kinds"]["recipe"]["data_keys"]
