# tests/kg_ingest/test_recipe_roster_builder.py
import json, pathlib, pytest
from osrs_planner.engine.kg.model import EdgeType, Node, NodeKind, AtomType
from kg_ingest.builders.recipes import build_recipe_roster
from kg_ingest.recipe_identity import resolve_recipe_payload, recipe_identity_hash, _facility_lookup
from kg_ingest.builders.map_varrock import make_item_resolver
import html
ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_requires_facility_edgetype_exists():
    assert EdgeType("requires_facility") is EdgeType.REQUIRES_FACILITY


def test_schema_additive_changes():
    s = json.loads((ROOT / "kg" / "schema.json").read_text())
    assert s["edge_kinds"]["requires_facility"]["status"] == "live"
    assert "tool" in s["vocab"]["consumes_role"]
    assert "members" in s["node_kinds"]["recipe"]["data_keys"]


def _facilities():
    return [Node(id="facility:anvil", kind=NodeKind.FACILITY, name="Anvil", slug="anvil", data={}),
            Node(id="facility:range", kind=NodeKind.FACILITY, name="Range", slug="range", data={"aliases": ["Cooking range"]})]


def _itemdict():
    return [{"item_id": 2349, "name": "Bronze bar", "page_name": "Bronze bar", "is_canonical": True},
            {"item_id": 1205, "name": "Bronze dagger", "page_name": "Bronze dagger", "is_canonical": True},
            {"item_id": 2132, "name": "Raw beef", "page_name": "Raw beef", "is_canonical": True},
            {"item_id": 2142, "name": "Cooked meat", "page_name": "Cooked meat", "is_canonical": True},
            {"item_id": 1337, "name": "Hammer", "page_name": "Hammer", "is_canonical": True}]


def _row(page, skill, tool, facility, pj):
    return {"page_name": page, "uses_skill": skill, "uses_tool": tool, "uses_facility": facility,
            "production_json": json.dumps(pj)}


def _resolve(dictrecs):
    r = make_item_resolver(dictrecs)
    return lambda name: (lambda i: f"item:{i}" if i is not None else None)(r(html.unescape((name or "").strip())))


def _registry_for(rows, dictrecs, facs):
    """Build a minimal registry that assigns each fixture recipe a deterministic slug
    (base slug + method suffix if subtxt) keyed by its identity hash — enough for the
    builder to look up. Groups true-dupes in emission order."""
    resolve = _resolve(dictrecs); fac = _facility_lookup(facs)
    from kg_ingest.ids import slugify
    reg = {"recipes": {}}; claimed = set()
    for r in rows:
        p = resolve_recipe_payload(r, resolve, fac)
        if p is None:
            continue
        base = f"{slugify(p['out_name'])}-{slugify(p['subtxt'])}" if p["subtxt"] else slugify(p["out_name"])
        slug = base; k = 2
        while slug in claimed:
            slug = f"{base}-{k}"; k += 1
        claimed.add(slug)
        h = recipe_identity_hash(p)
        reg["recipes"].setdefault(h, {"slugs": [], "output": p["out_name"]})["slugs"].append(slug)
    return reg


def _build(rows, dictrecs=None, facs=None):
    dictrecs = dictrecs or _itemdict(); facs = facs or _facilities()
    reg = _registry_for(rows, dictrecs, facs)
    return build_recipe_roster(rows, dictrecs, facs, reg)


def _map(nodes): return {n.id: n for n in nodes}


def test_full_shape_uses_registry_slug():
    rows = [_row("Bronze dagger", ["Smithing"], ["Hammer"], ["Anvil"],
                {"materials": [{"quantity": "1", "name": "Bronze bar"}], "ticks": "5", "members": False,
                 "skills": [{"name": "Smithing", "level": "1", "experience": "12.5", "boostable": "Yes"}],
                 "output": {"quantity": "1", "name": "Bronze dagger"}})]
    nodes, edges, groups = _build(rows)
    n = _map(nodes)["recipe:bronze-dagger"]
    assert n.kind is NodeKind.RECIPE and n.name == "Bronze dagger"
    assert n.data["xp"] == {"Smithing": 12.5} and n.data["ticks"] == 5 and n.data["members"] is False
    assert n.data["source_token"] == "Bucket:recipe page=Bronze dagger output=Bronze dagger"
    types = [(e.type, e.dst, (e.data or {}).get("role")) for e in edges]
    assert (EdgeType.CONSUMES, "item:2349", "material") in types
    assert (EdgeType.CONSUMES, "item:1337", "tool") in types
    assert (EdgeType.PRODUCES, "item:1205", None) in types
    assert (EdgeType.REQUIRES_FACILITY, "facility:anvil", None) in types
    g = groups[[e for e in edges if e.type is EdgeType.REQUIRES][0].cond_group]
    assert g.children[0].ref_node == "skill:smithing" and g.children[0].threshold == 1


def test_method_suffixed_source_token():
    # two rows, same output+different subtxt -> registry gives method-suffixed slugs -> source_token carries method=
    rows = [_row("Bronze bar", ["Smithing"], None, ["Anvil"],
                {"materials": [], "skills": [{"name": "Smithing", "level": "1", "experience": "6"}],
                 "output": {"quantity": "1", "name": "Bronze bar", "subtxt": "Blast Furnace"}})]
    nodes, _, _ = _build(rows)
    n = _map(nodes)["recipe:bronze-bar-blast-furnace"]
    assert n.data["source_token"] == "Bucket:recipe page=Bronze bar output=Bronze bar method=Blast Furnace"


def test_row_order_independent_ids():
    rows = [_row("Bronze bar", [], None, None, {"materials": [], "output": {"quantity": "1", "name": "Bronze bar", "subtxt": "A"}}),
            _row("Bronze bar", [], None, None, {"materials": [], "output": {"quantity": "1", "name": "Bronze bar", "subtxt": "B"}})]
    reg = _registry_for(rows, _itemdict(), _facilities())
    ids_fwd = {n.id for n in build_recipe_roster(rows, _itemdict(), _facilities(), reg)[0]}
    ids_rev = {n.id for n in build_recipe_roster(list(reversed(rows)), _itemdict(), _facilities(), reg)[0]}
    assert ids_fwd == ids_rev  # same registry -> same id set regardless of row order


def test_no_skill_recipe_builds_without_requires_or_xp():
    rows = [_row("Combined thing", None, None, None,
                {"materials": [{"quantity": "1", "name": "Bronze bar"}],
                 "output": {"quantity": "1", "name": "Bronze dagger"}})]
    nodes, edges, groups = _build(rows)
    n = _map(nodes)["recipe:bronze-dagger"]
    assert "xp" not in n.data and groups == {}
    assert not any(e.type is EdgeType.REQUIRES for e in edges)
    assert any(e.type is EdgeType.CONSUMES for e in edges) and any(e.type is EdgeType.PRODUCES for e in edges)


def test_unresolvable_material_skips_edge_not_recipe():
    rows = [_row("Bronze dagger", ["Smithing"], None, None,
                {"materials": [{"quantity": "1", "name": "Bronze bar"}, {"quantity": "1", "name": "Nonexistent xyz"}],
                 "skills": [{"name": "Smithing", "level": "1", "experience": "12.5"}],
                 "output": {"quantity": "1", "name": "Bronze dagger"}})]
    nodes, edges, _ = _build(rows)
    mat = [e for e in edges if e.type is EdgeType.CONSUMES and (e.data or {}).get("role") == "material"]
    assert len(mat) == 1 and mat[0].dst == "item:2349"


def test_unregistered_recipe_fails_fast():
    rows = [_row("Bronze dagger", [], None, None, {"materials": [], "output": {"quantity": "1", "name": "Bronze dagger"}})]
    with pytest.raises(ValueError, match="unregistered"):
        build_recipe_roster(rows, _itemdict(), _facilities(), {"recipes": {}})  # empty registry
