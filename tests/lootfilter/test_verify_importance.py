import os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def test_verify_reports_and_exits_zero():
    r = subprocess.run([sys.executable, os.path.join(REPO, "data", "verify_loot_importance.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "coverage" in r.stdout.lower() and "herb" in r.stdout
