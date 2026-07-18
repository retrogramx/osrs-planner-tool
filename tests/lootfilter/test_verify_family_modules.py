import importlib.util
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = os.path.join(REPO, "data", "verify_family_modules.py")


def _load_module():
    # data/*.py is loaded by FILE PATH, not `from data.X import` -- tests/data/__init__.py shadows
    # the `data` package name during full-suite collection (reference_tests_data_package_shadow).
    spec = importlib.util.spec_from_file_location("verify_family_modules", V)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verifier_passes_and_reports_coverage():
    r = subprocess.run([sys.executable, V], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "covered" in r.stdout
    assert "family-coverage:" in r.stdout
    # every family module the generator currently populates should show up
    for fam in ("seed", "herb", "rune", "ore", "bar", "log", "plank", "gem", "ammo", "food", "bones", "essence"):
        assert f"family-coverage: {fam:8}" in r.stdout, f"missing coverage line for family {fam!r}"


def test_real_data_is_fully_covered():
    # Keep this honest: with the current committed loot_importance.json + generator, every family
    # name should land in exactly one tier -- zero residuals. If this ever regresses it's real
    # signal, not a stale assertion (the report-not-fail contract still lets the script exit 0).
    mod = _load_module()
    r = subprocess.run([sys.executable, V], capture_output=True, text=True)
    assert r.returncode == 0
    assert "TOTAL:" in r.stdout
    have, total = r.stdout.split("TOTAL: ")[1].split(" covered")[0].split("/")
    assert have == total, f"expected full coverage, got {have}/{total}:\n{r.stdout}"
    assert "residuals: none" in r.stdout
    assert mod  # loaded cleanly (also exercises the importlib-from-path load path itself)


def test_check_family_coverage_detects_zero_and_multi_tier_names():
    # Unit-level: exercise the pure check function directly (synthetic input) so the
    # residual-detection logic itself is under test, not just "the current data is clean".
    mod = _load_module()
    importance = [
        {"family": "seed", "name": "Ranarr seed"},
        {"family": "seed", "name": "Potato seed"},
        {"family": "seed", "name": "Ghost seed"},  # absent from `text` below -> ZERO tiers
    ]
    text = (
        "#define SEEDS_SS_NAMES []\n"
        '#define SEEDS_S_NAMES ["Ranarr seed"]\n'
        '#define SEEDS_A_NAMES ["Ranarr seed", "Potato seed"]\n'  # Ranarr seed duplicated -> >1 tier
    )
    rows, residuals = mod.check_family_coverage(importance, text)
    assert len(rows) == 1
    row = rows[0]
    assert row["family"] == "seed" and row["module_id"] == "seeds"
    assert row["total"] == 3
    assert row["have"] == 1  # only "Potato seed" lands in exactly one tier
    assert row["zero"] == ["Ghost seed"]
    assert [n for n, _tiers in row["multi"]] == ["Ranarr seed"]
    assert any("ZERO tiers" in line for line in residuals)
    assert any(">1 tier" in line for line in residuals)


def test_main_exits_zero_even_when_synthetic_data_has_gaps(monkeypatch, capsys):
    # report-not-fail (feedback_editorial_data_report_not_fail): main() must return 0 even when
    # check_family_coverage finds residuals -- force a gap by stubbing generate_filter to omit a
    # tier default entirely, then confirm the process still reports 0.
    mod = _load_module()
    monkeypatch.setattr(mod, "generate_filter", lambda: "#define SEEDS_S_NAMES []\n")
    rc = mod.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "ZERO tiers" in out
