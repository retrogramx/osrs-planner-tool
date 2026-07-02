# tests/kg_ingest/test_validate_recipe_id_registry.py
import types
from data.validate_kg import check_recipe_id_registry


class _Store:
    def __init__(self, nodes): self.nodes = {n.id: n for n in nodes}


def _n(nid, slug, data=None):
    return types.SimpleNamespace(id=nid, slug=slug, data=data or {})


def _patch_registry(monkeypatch, reg):
    import data.validate_kg as v, json
    monkeypatch.setattr(v.os.path, "exists", lambda p: True)
    monkeypatch.setattr(v.json, "load", lambda f: {"recipes": reg})
    monkeypatch.setattr("builtins.open", lambda *a, **k: __import__("io").StringIO("{}"))


def test_clean_graph_passes(monkeypatch):
    reg = {"h1": {"slugs": ["bronze-bar"], "output": "Bronze bar"}}
    _patch_registry(monkeypatch, reg)
    store = _Store([_n("recipe:bronze-bar", "bronze-bar"),
                    _n("recipe:charge-scythe-of-vitur", "charge-scythe-of-vitur", {"charge_capacity": 100})])
    assert check_recipe_id_registry(store) == []            # charge recipe excluded from coverage


def test_roster_slug_not_in_registry_fails(monkeypatch):
    _patch_registry(monkeypatch, {"h1": {"slugs": ["bronze-bar"], "output": "Bronze bar"}})
    store = _Store([_n("recipe:iron-bar", "iron-bar")])     # not in registry
    errs = check_recipe_id_registry(store)
    assert any("iron-bar" in e and "not in the registry" in e for e in errs)


def test_registry_slug_collision_fails(monkeypatch):
    reg = {"h1": {"slugs": ["dup"], "output": "A"}, "h2": {"slugs": ["dup"], "output": "B"}}
    _patch_registry(monkeypatch, reg)
    store = _Store([_n("recipe:dup", "dup")])
    errs = check_recipe_id_registry(store)
    assert any("registered under two identities" in e for e in errs)


def test_duplicate_committed_slug_fails(monkeypatch):
    reg = {"h1": {"slugs": ["bronze-bar"], "output": "Bronze bar"}}
    _patch_registry(monkeypatch, reg)
    store = _Store([_n("recipe:bronze-bar", "bronze-bar"),
                    _n("recipe:bronze-bar-2", "bronze-bar")])  # same slug, different id
    errs = check_recipe_id_registry(store)
    assert any("duplicate committed recipe slug" in e for e in errs)
