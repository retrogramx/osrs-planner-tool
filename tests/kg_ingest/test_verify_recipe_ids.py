import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_verify_recipe_ids_reports_clean():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_recipe_ids.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "RECIPE-ID STABILITY" in r.stdout
    assert "roster slugs NOT in registry: 0" in r.stdout
