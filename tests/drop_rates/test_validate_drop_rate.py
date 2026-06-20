import json, os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VALIDATOR = os.path.join(REPO, "data", "validate_drop_rate.py")
PY = sys.executable

def _run(*args): return subprocess.run([PY, VALIDATOR, *args], capture_output=True, text=True)

def test_passes_on_committed_data():
    r = _run()
    assert r.returncode == 0, f"validator failed on committed data:\n{r.stdout}\n{r.stderr}"

def test_fabricated_rate_without_raw_fails(tmp_path):
    bad = {"_provenance": {"record_count": 1}, "records": [
        {"item_id": 4151, "item": "Abyssal whip", "source": "X", "source_node_type": "monster",
         "drop_rate": 0.5, "drop_rate_raw": "", "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    ], "_excluded": []}
    p = tmp_path / "drop_rates.json"; p.write_text(json.dumps(bad))
    r = _run("--dataset", str(p))
    assert r.returncode == 1 and "fabricat" in (r.stdout + r.stderr).lower()

def test_probability_over_one_fails(tmp_path):
    bad = {"_provenance": {"record_count": 1}, "records": [
        {"item_id": 4151, "item": "X", "source": "Y", "source_node_type": "monster",
         "drop_rate": 1.5, "drop_rate_raw": "3/2", "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    ], "_excluded": []}
    p = tmp_path / "drop_rates.json"; p.write_text(json.dumps(bad))
    assert _run("--dataset", str(p)).returncode == 1

def test_null_with_sourced_status_fails(tmp_path):
    bad = {"_provenance": {"record_count": 1}, "records": [
        {"item_id": 4151, "item": "X", "source": "Y", "source_node_type": "monster",
         "drop_rate": None, "drop_rate_raw": "", "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    ], "_excluded": []}
    p = tmp_path / "drop_rates.json"; p.write_text(json.dumps(bad))
    assert _run("--dataset", str(p)).returncode == 1
