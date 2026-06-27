# tests/kg_ingest/test_verify_storeline.py
import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_verify_storeline_passes_on_committed_graph():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_storeline.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "STORELINE VERIFICATION PASSED" in r.stdout
    assert "shops covered by Storeline: 13/15" in r.stdout            # 2 dialogue-shops fall back
