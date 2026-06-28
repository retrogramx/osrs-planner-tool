import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_verify_world_passes():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_world.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WORLD VERIFICATION PASSED" in r.stdout
    assert "unparented" in r.stdout.lower()       # residual is reported
