import json, os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
J = os.path.join(REPO, "data", "loot_importance.json")
V = os.path.join(REPO, "data", "validate_loot_importance.py")
B = os.path.join(REPO, "data", "build_loot_importance.py")

def _recs():
    return json.load(open(J, encoding="utf-8"))["records"]

def test_provenance_editorial():
    assert json.load(open(J, encoding="utf-8"))["_provenance"]["kind"] == "editorial"

def test_every_record_shape_and_tier():
    grades = {"SS", "S", "A", "B", "C", "D", "E"}
    for r in _recs():
        assert set(r) >= {"item_id", "name", "family", "base_tier", "rationale"}
        assert r["base_tier"] in grades and isinstance(r["item_id"], int) and r["rationale"]

def test_ranarr_high_guam_low():        # the design's motivating ranking must hold
    by = {r["name"]: r["base_tier"] for r in _recs()}
    order = {"SS": 0, "S": 1, "A": 2, "B": 3, "C": 4, "D": 5, "E": 6}
    assert order[by["Grimy ranarr weed"]] < order[by["Grimy guam leaf"]]

def test_cheap_staples_not_bottom():    # value would floor these; the ranking must not
    by = {r["name"]: r["base_tier"] for r in _recs()}
    for staple in ("Pure essence", "Coal"):
        assert by[staple] not in ("D", "E"), f"{staple} ranked too low"

def test_builder_is_byte_stable():
    before = open(J, encoding="utf-8").read()
    subprocess.run([sys.executable, B], check=True)
    assert open(J, encoding="utf-8").read() == before

def test_validator_passes_committed():
    assert subprocess.run([sys.executable, V], capture_output=True, text=True).returncode == 0

def test_validator_catches_bad_tier(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"_provenance": {"kind": "editorial"},
        "records": [{"item_id": 995, "name": "Coins", "family": "ore", "base_tier": "Z", "rationale": "x"}]}))
    assert subprocess.run([sys.executable, V, "--file", str(bad)], capture_output=True, text=True).returncode == 1
