"""validate_cost.py runs clean on committed data; constructed-broken inputs fail.

Negative fixtures are CONSTRUCTED in tmp dirs (never mutate the frozen committed
JSON). The committed datasets are hand-curated, wiki-verified source-of-truth
covering the golden-set goals + a small representative sample; bulk wiki sourcing
is a disclosed v1 follow-up.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VALIDATOR = os.path.join(REPO, "data", "validate_cost.py")
PY = sys.executable


def _run(*args):
    return subprocess.run([PY, VALIDATOR, *args], capture_output=True, text=True)


def test_validator_passes_on_committed_data():
    r = _run()
    assert r.returncode == 0, f"validate_cost failed on committed data:\n{r.stdout}\n{r.stderr}"
    assert "COST VALIDATION PASSED" in r.stdout


def _make_broken_root(tmp_path, *, shop_records=None, kg_text=None):
    """Construct a minimal broken data+kg root (never touch committed files)."""
    data = tmp_path / "data"
    kgd = tmp_path / "kg"
    data.mkdir()
    kgd.mkdir()
    (data / "item_dictionary.json").write_text(json.dumps(
        {"records": [{"item_id": 4587, "name": "Dragon scimitar"}]}))
    (data / "currencies.json").write_text(json.dumps(
        {"records": [{"id": "currency:coins", "name": "Coins"}]}))
    (data / "shop_prices.json").write_text(json.dumps(
        {"records": shop_records if shop_records is not None else []}))
    (kgd / "nodes.json").write_text(kg_text if kg_text is not None else "[]")
    return str(data), str(kgd)


def test_unresolvable_item_id_fails(tmp_path):
    d, k = _make_broken_root(tmp_path, shop_records=[
        {"channel": "shop", "item_id": "item:99999999", "currency": "currency:coins",
         "amount": 1, "account_allow": ["main", "ironman", "uim"], "requires_ge": False}])
    r = _run("--data", d, "--kg", k)
    assert r.returncode == 1
    assert "does not resolve" in r.stdout


def test_unresolvable_currency_fails(tmp_path):
    d, k = _make_broken_root(tmp_path, shop_records=[
        {"channel": "shop", "item_id": "item:4587", "currency": "currency:bogus",
         "amount": 1, "account_allow": ["main", "ironman", "uim"], "requires_ge": False}])
    r = _run("--data", d, "--kg", k)
    assert r.returncode == 1
    assert "currency ref does not resolve" in r.stdout


def test_ge_channel_marked_iron_eligible_fails(tmp_path):
    d, k = _make_broken_root(tmp_path, shop_records=[
        {"channel": "ge", "item_id": "item:4587", "currency": "currency:coins",
         "amount": 1, "account_allow": ["main", "ironman"], "requires_ge": True}])
    r = _run("--data", d, "--kg", k)
    assert r.returncode == 1
    assert "iron-eligible" in r.stdout


def test_cost_token_in_kg_fails(tmp_path):
    d, k = _make_broken_root(
        tmp_path, shop_records=[],
        kg_text=json.dumps([{"id": "item:4587", "kind": "item", "data": {"price": 60000}}]))
    r = _run("--data", d, "--kg", k)
    assert r.returncode == 1
    assert "cost token leaked" in r.stdout
