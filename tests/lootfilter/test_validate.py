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
def test_validator_fails_enumlist_default_not_subset(tmp_path):
    # a family module's #define default must only name items that are actually in its own enum
    p = tmp_path / "enum.rs2f"; p.write_text(
        "/*@ define:module:settings\nname: \"Settings\"\nsubtitle: \"x\"\ndescription: |\n    x\n*/\n"
        "#define IRONMAN accountType:1\n#define HIDE_FLOOR 0\n"
        "/*@ define:input:seeds\nlabel: \"Items\"\ntype: enumlist\n"
        "enum: [\"Ranarr seed\", \"Potato seed\"]\ngroup: \"A tier\"\n*/\n"
        "#define SEEDS_A_NAMES [\"Ranarr seed\", \"Bogus seed\"]\n"
        "meta { name = \"x\"; description = \"y\"; }\n")
    r = subprocess.run([sys.executable, V, "--filter", str(p)], capture_output=True, text=True)
    assert r.returncode == 1 and "default not a subset of enum" in r.stdout, r.stdout + r.stderr
def test_validator_fails_area_box_not_6_ints(tmp_path):
    p = tmp_path / "area.rs2f"; p.write_text(
        "/*@ define:module:settings\nname: \"Settings\"\nsubtitle: \"x\"\ndescription: |\n    x\n*/\n"
        "#define IRONMAN accountType:1\n#define HIDE_FLOOR 0\n"
        "rule (IRONMAN && area:[1, 2, 3]) { hidden = true; }\n"
        "meta { name = \"x\"; description = \"y\"; }\n")
    r = subprocess.run([sys.executable, V, "--filter", str(p)], capture_output=True, text=True)
    assert r.returncode == 1 and "area box not 6 ints" in r.stdout, r.stdout + r.stderr
