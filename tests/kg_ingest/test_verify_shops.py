import subprocess, sys, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

def _run(script):
    return subprocess.run([sys.executable, os.path.join(ROOT, "data", script)],
                          capture_output=True, text=True)

def test_verify_shop_coverage_runs_and_reports():
    r = _run("verify_shop_coverage.py")
    assert r.returncode == 0                       # report-not-fail
    assert "COVERAGE" in r.stdout

def test_verify_shops_passes_on_committed_graph():
    r = _run("verify_shops.py")
    assert r.returncode == 0, r.stdout
    assert "SHOP VERIFICATION" in r.stdout
