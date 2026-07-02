import importlib.util
import json as _j
import os

from osrs_planner.engine.kg.model import Node, NodeKind
from kg_ingest.recipe_identity import _facility_lookup

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "update_recipe_registry", os.path.join(_ROOT, "data", "update_recipe_registry.py")
)
_urr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_urr)
seed_registry = _urr.seed_registry
update_registry = _urr.update_registry


def _resolver(dictrecs):
    from kg_ingest.builders.map_varrock import make_item_resolver
    import html
    r = make_item_resolver(dictrecs)
    return lambda name: (lambda i: f"item:{i}" if i is not None else None)(r(html.unescape((name or "").strip())))


def _itemdict():
    return [{"item_id": 2349, "name": "Bronze bar", "page_name": "Bronze bar", "is_canonical": True},
            {"item_id": 2351, "name": "Iron bar", "page_name": "Iron bar", "is_canonical": True}]


def _fac():
    return _facility_lookup([Node(id="facility:furnace", kind=NodeKind.FACILITY, name="Furnace", slug="furnace", data={})])


def _row(page, pj):
    return {"page_name": page, "uses_skill": None, "uses_tool": None, "uses_facility": None,
            "production_json": _j.dumps(pj)}


def test_seed_reproduces_multi_and_bare_slugs():
    # one page, two makeable rows (same output, different subtxt) -> multi=True -> both method-suffixed
    rows = [_row("Bronze bar", {"materials": [], "output": {"quantity": "1", "name": "Bronze bar", "subtxt": "Furnace"}}),
            _row("Bronze bar", {"materials": [], "output": {"quantity": "1", "name": "Bronze bar", "subtxt": "Blast Furnace"}}),
            _row("Iron bar", {"materials": [], "output": {"quantity": "1", "name": "Iron bar", "subtxt": "Furnace"}})]  # single row -> bare
    reg = seed_registry(rows, _resolver(_itemdict()), _fac(), set())
    slugs = {s for e in reg["recipes"].values() for s in e["slugs"]}
    assert slugs == {"bronze-bar-furnace", "bronze-bar-blast-furnace", "iron-bar"}  # iron-bar bare (single-method page)


def test_seed_groups_true_duplicates_in_emission_order():
    rows = [_row("Iron bar", {"materials": [], "output": {"quantity": "1", "name": "Iron bar"}}),
            _row("Iron bar", {"materials": [], "output": {"quantity": "1", "name": "Iron bar"}})]  # identical dupe
    reg = seed_registry(rows, _resolver(_itemdict()), _fac(), set())
    entries = list(reg["recipes"].values())
    assert len(entries) == 1 and entries[0]["slugs"] == ["iron-bar", "iron-bar-2"]  # dupe -> list, emission order


def test_seed_reserves_charge_slugs():
    rows = [_row("Bronze bar", {"materials": [], "output": {"quantity": "1", "name": "Bronze bar"}})]
    reg = seed_registry(rows, _resolver(_itemdict()), _fac(), {"bronze-bar"})
    slugs = {s for e in reg["recipes"].values() for s in e["slugs"]}
    assert slugs == {"bronze-bar-2"}  # charge slug 'bronze-bar' reserved -> guard bumps


def test_update_mints_new_and_leaves_existing_untouched():
    rows = [_row("Bronze bar", {"materials": [], "output": {"quantity": "1", "name": "Bronze bar"}})]
    reg = seed_registry(rows, _resolver(_itemdict()), _fac(), set())
    before = _j.dumps(reg, sort_keys=True)
    # add a brand-new recipe (Iron bar) not in the registry
    rows2 = rows + [_row("Iron bar", {"materials": [], "output": {"quantity": "1", "name": "Iron bar"}})]
    reg2 = update_registry(rows2, _resolver(_itemdict()), _fac(), set(), reg)
    slugs = {s for e in reg2["recipes"].values() for s in e["slugs"]}
    assert slugs == {"bronze-bar", "iron-bar"}                      # new slug appended
    # re-running update with the same rows is a no-op
    reg3 = update_registry(rows2, _resolver(_itemdict()), _fac(), set(), reg2)
    assert _j.dumps(reg3, sort_keys=True) == _j.dumps(reg2, sort_keys=True)


def test_committed_registry_reproduces_current_graph_ids():
    # The committed seed must map every current roster recipe id to itself (zero churn).
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    reg = _j.loads((root / "data" / "recipe_slug_registry.json").read_text())["recipes"]
    reg_slugs = {s for e in reg.values() for s in e["slugs"]}
    nodes = _j.loads((root / "kg" / "nodes.json").read_text())
    roster = [n for n in nodes if n["id"].startswith("recipe:") and "charge_capacity" not in (n.get("data") or {})]
    missing = [n["slug"] for n in roster if n["slug"] not in reg_slugs]
    assert missing == [], f"{len(missing)} committed roster slugs not in registry: {missing[:10]}"
    assert len(reg_slugs) == len(roster), (len(reg_slugs), len(roster))  # exact coverage
