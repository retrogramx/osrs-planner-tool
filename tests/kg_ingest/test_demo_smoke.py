"""Smoke test: the demo runner executes over the real committed KG without raising
and emits one labelled block per golden goal."""
from __future__ import annotations

from kg_ingest.demo import run_demo


def test_demo_runs_over_real_kg(capsys):
    run_demo()
    out = capsys.readouterr().out
    for label in ("Dragon scimitar", "Barrows gloves", "Fairy rings", "Tzhaar-ket-om"):
        assert label in out, f"demo output missing {label!r}:\n{out}"
    assert "is_unlocked:" in out, out
