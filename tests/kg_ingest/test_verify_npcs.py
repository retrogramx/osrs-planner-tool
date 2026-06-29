import subprocess, sys, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
def _run(s): return subprocess.run([sys.executable, os.path.join(ROOT, "data", s)], capture_output=True, text=True)

def test_verify_npc_coverage_runs():
    r = _run("verify_npc_coverage.py"); assert r.returncode == 0; assert "NPC COVERAGE" in r.stdout

def test_verify_npcs_passes_on_committed_graph():
    r = _run("verify_npcs.py"); assert r.returncode == 0, r.stdout; assert "NPC VERIFICATION" in r.stdout
