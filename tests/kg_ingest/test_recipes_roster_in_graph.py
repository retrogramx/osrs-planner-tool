import json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]

def _load(name): return json.loads((ROOT / "kg" / name).read_text())

def test_recipe_roster_present_and_wired():
    nodes = _load("nodes.json"); edges = _load("edges.json")
    recipes = [n for n in nodes if n["id"].startswith("recipe:")]
    assert len(recipes) >= 1500, f"expected a large recipe roster, got {len(recipes)}"
    nid = {n["id"] for n in nodes}
    rf = [e for e in edges if e["type"] == "requires_facility"]
    assert len(rf) >= 500, f"expected many requires_facility edges, got {len(rf)}"
    for e in rf:
        assert e["dst"] in nid and e["dst"].startswith("facility:")   # targets a committed facility node
    # a known recipe wires materials + facility + skill gate
    dagger = next((n for n in recipes if n["name"] == "Bronze dagger"), None)
    assert dagger is not None and "Smithing" in dagger["data"].get("xp", {})

def test_assemble_is_byte_stable():
    p = ROOT / "kg" / "nodes.json"; before = p.read_bytes()
    subprocess.run([sys.executable, "-m", "kg_ingest.assemble"], cwd=ROOT, check=True)
    assert p.read_bytes() == before, "assemble is not byte-stable"

def test_verify_recipes_passes():
    import subprocess, sys, pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, "data/verify_recipes.py"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
