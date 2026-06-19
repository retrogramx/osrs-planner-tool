"""Scaffold smoke test: the ingest packages import and the output dir exists."""
from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_kg_ingest_packages_import():
    assert importlib.import_module("kg_ingest") is not None
    assert importlib.import_module("kg_ingest.builders") is not None


def test_kg_output_dir_exists():
    assert (REPO_ROOT / "kg").is_dir()
