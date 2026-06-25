import importlib.util, os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _run():
    return subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_item_families.py")],
                          capture_output=True, text=True)

def test_verifier_passes_on_committed_families():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ITEM-FAMILIES VERIFICATION PASSED" in r.stdout
