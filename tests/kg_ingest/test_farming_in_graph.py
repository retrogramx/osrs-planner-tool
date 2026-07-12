# tests/kg_ingest/test_farming_in_graph.py
import json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]

def _nodes():
    return json.loads((ROOT / "kg" / "nodes.json").read_text())

def _edges():
    return json.loads((ROOT / "kg" / "edges.json").read_text())

def test_farming_nodes_present_and_well_formed():
    fp = [n for n in _nodes() if n["id"].startswith("farming_patch:")]
    assert len(fp) >= 70, f"expected ~76 farming patches, got {len(fp)}"
    herb = next((n for n in fp if n["id"] == "farming_patch:herb-catherby"), None)
    assert herb is not None and herb["kind"] == "farming_patch"
    assert herb["data"]["patch_type"] == "herb"
    assert herb["data"]["source_token"] and herb["data"]["source_url"]

def test_farming_located_in_edge_targets_a_real_place():
    place_ids = {n["id"] for n in _nodes() if n["id"].startswith("place:")}
    fp_ids = {n["id"] for n in _nodes() if n["id"].startswith("farming_patch:")}
    li = [e for e in _edges() if e["type"] == "located_in" and e["src"].startswith("farming_patch:")]
    assert any(e["src"] == "farming_patch:herb-catherby" and e["dst"] == "place:catherby" for e in li)
    for e in li:
        assert e["src"] in fp_ids and e["dst"] in place_ids   # no dangling edges
        assert e["cond_group"] is None and e["data"] == {}

def test_assemble_is_byte_stable():
    p = ROOT / "kg" / "nodes.json"
    before = p.read_bytes()
    subprocess.run([sys.executable, "-m", "kg_ingest.assemble"], cwd=ROOT, check=True)
    assert p.read_bytes() == before, "assemble is not byte-stable"
