import os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = os.path.join(REPO, "data", "validate_loot_filter.py")
def test_validator_passes_committed():
    r = subprocess.run([sys.executable, V], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
def test_validator_fails_unbalanced(tmp_path):
    p = tmp_path / "bad.rs2f"; p.write_text('meta { name = "x";')
    assert subprocess.run([sys.executable, V, "--filter", str(p)], capture_output=True, text=True).returncode == 1
