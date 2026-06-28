import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_coverage_gate_passes_and_reports_metric():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_world_coverage.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "COVERAGE" in r.stdout
    assert "Dungeons" in r.stdout and "/" in r.stdout      # the have/total metric
