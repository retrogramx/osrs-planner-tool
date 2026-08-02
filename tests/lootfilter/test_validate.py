import os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = os.path.join(REPO, "data", "validate_loot_filter.py")
def test_validator_passes_committed():
    r = subprocess.run([sys.executable, V], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
def test_validator_fails_unbalanced(tmp_path):
    p = tmp_path / "bad.rs2f"; p.write_text('meta { name = "x";')
    assert subprocess.run([sys.executable, V, "--filter", str(p)], capture_output=True, text=True).returncode == 1
def test_validator_fails_unquoted_colon_scalar(tmp_path):
    # an unquoted subtitle with a colon-space is exactly what nulls a FilterScape import
    p = tmp_path / "colon.rs2f"; p.write_text(
        "/*@ define:module:settings\nname: Settings\n"
        "subtitle: Resource piles: escalated by count\ndescription: |\n    x\n*/\n"
        "#define IRONMAN accountType:1\n#define HIDE_FLOOR 0\nmeta { name = \"x\"; description = \"y\"; }\n")
    r = subprocess.run([sys.executable, V, "--filter", str(p)], capture_output=True, text=True)
    assert r.returncode == 1 and "breaks FilterScape import" in r.stdout, r.stdout + r.stderr
