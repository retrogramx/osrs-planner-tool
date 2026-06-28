import subprocess, sys, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_coverage_gate_passes_and_reports_metric():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_world_coverage.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "COVERAGE" in r.stdout
    assert "Dungeons" in r.stdout and "/" in r.stdout      # the have/total metric

def test_coverage_gate_surfaces_slug_collisions_honestly():
    """The gate must not mask slug collisions (e.g. 14 "Unnamed island (…)" titles collapsing
    to one slug). It should report a residual > 0 and show "Unnamed island" in the missing
    sample, proving colliding titles are counted as misses rather than hidden coverage."""
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_world_coverage.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    # Extract the total residual count from the summary line
    m = re.search(r"residual \(snapshot members without a place node\):\s*(\d+)", r.stdout)
    assert m is not None, f"residual summary line not found in output:\n{r.stdout}"
    assert int(m.group(1)) > 0, "residual should be > 0 — slug collisions must appear as misses"
    assert "Unnamed island" in r.stdout, "missing sample must contain 'Unnamed island' to prove collision is reported"
