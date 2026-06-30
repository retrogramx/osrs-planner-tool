import json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]

def _nodes():
    return json.loads((ROOT / "kg" / "nodes.json").read_text())

def test_facility_nodes_present_and_well_formed():
    facs = [n for n in _nodes() if n["id"].startswith("facility:")]
    assert len(facs) >= 250, f"expected many facilities, got {len(facs)}"
    anvil = next((n for n in facs if n["id"] == "facility:anvil"), None)
    assert anvil is not None and anvil["kind"] == "facility"
    assert "Smithing" in anvil["data"].get("skills", [])
    assert anvil["data"]["source_token"] == "Bucket:recipe.uses_facility=Anvil"
    # deferred NPC/shop never become facilities
    assert not any(n["id"] == "facility:thormac" for n in facs)
    assert not any(n["id"] == "facility:sawmill" for n in facs)

def test_assemble_is_byte_stable():
    p = ROOT / "kg" / "nodes.json"
    before = p.read_bytes()
    subprocess.run([sys.executable, "-m", "kg_ingest.assemble"], cwd=ROOT, check=True)
    assert p.read_bytes() == before, "assemble is not byte-stable"

def test_verify_facilities_passes():
    import subprocess, sys, pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, "data/verify_facilities.py"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
