import os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_verifier_passes_on_committed_map():
    r = subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_map.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MAP VERIFICATION PASSED" in r.stdout
