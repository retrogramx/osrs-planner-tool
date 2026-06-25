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


def _envelope(records):
    """Wrap rows in the normalized cost-dataset envelope the validator expects
    ({_provenance.record_count, records, _excluded})."""
    return {
        "_provenance": {"record_count": len(records)},
        "records": records,
        "_excluded": [],
    }


def _make_broken_root(tmp_path, *, shop_records=None, recipe_records=None, kg_text=None):
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
        _envelope(shop_records if shop_records is not None else [])))
    if recipe_records is not None:
        (data / "recipes.json").write_text(json.dumps(_envelope(recipe_records)))
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


def test_schema_json_currency_kind_is_not_a_cost_leak(tmp_path):
    # kg/schema.json is the LOCKED v2 ontology vocabulary; it legitimately NAMES a
    # 'currency' node kind (decision: coins is just one currency). Invariant 6
    # (cost-free KG) guards the graph INSTANCE files, not the schema's vocabulary,
    # so a currency token in schema.json must NOT fail validation.
    import pathlib
    d, k = _make_broken_root(tmp_path, shop_records=[])
    (pathlib.Path(k) / "schema.json").write_text(json.dumps(
        {"node_kinds": {"currency": {"status": "reserved"}},
         "edge_kinds": {"realizable_via": {"domain": ["currency"]}}}))
    r = _run("--data", d, "--kg", k)
    assert r.returncode == 0, f"schema currency kind wrongly flagged:\n{r.stdout}"
    assert "COST VALIDATION PASSED" in r.stdout


def test_cost_token_in_schema_instance_file_still_fails(tmp_path):
    # The exclusion is schema.json ONLY: a real cost token in a graph INSTANCE
    # file (nodes.json) must still fail (the iron-gate guard stays intact).
    d, k = _make_broken_root(
        tmp_path, shop_records=[],
        kg_text=json.dumps([{"id": "item:4587", "kind": "item", "data": {"currency": "x"}}]))
    r = _run("--data", d, "--kg", k)
    assert r.returncode == 1
    assert "cost token leaked" in r.stdout


def test_unresolvable_craft_input_fails(tmp_path):
    # Recipe output resolves (item:4587) but an INPUT item_id does not -- inv 3.
    d, k = _make_broken_root(tmp_path, shop_records=[], recipe_records=[
        {"output_item_id": "item:4587", "currency": "currency:coins", "output_qty": 1,
         "inputs": [{"item_id": "item:99999999", "qty": 1}],
         "account_allow": ["main", "ironman", "uim"], "requires_ge": False}])
    r = _run("--data", d, "--kg", k)
    assert r.returncode == 1
    assert "input item_id does not resolve" in r.stdout
