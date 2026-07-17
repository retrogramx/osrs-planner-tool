import subprocess, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def test_verifier_passes_committed():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "data/verify_loot_families.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASSED" in r.stdout
