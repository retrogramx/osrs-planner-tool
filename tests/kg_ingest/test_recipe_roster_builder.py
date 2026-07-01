import json, pathlib
from osrs_planner.engine.kg.model import EdgeType
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_requires_facility_edgetype_exists():
    assert EdgeType("requires_facility") is EdgeType.REQUIRES_FACILITY

def test_schema_additive_changes():
    s = json.loads((ROOT / "kg" / "schema.json").read_text())
    assert s["edge_kinds"]["requires_facility"]["status"] == "live"
    assert "tool" in s["vocab"]["consumes_role"]
    assert "members" in s["node_kinds"]["recipe"]["data_keys"]


# ---------------------------------------------------------------------------
# Task 3: build_recipe_roster fixture tests
# ---------------------------------------------------------------------------
from osrs_planner.engine.kg.model import Node, NodeKind, AtomType
from kg_ingest.builders.recipes import build_recipe_roster, CORE_SKILLS


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
    import json as _j
    return {"page_name": page, "uses_skill": skill, "uses_tool": tool, "uses_facility": facility, "production_json": _j.dumps(pj)}


def _map(nodes): return {n.id: n for n in nodes}


def test_smith_recipe_full_shape():
    rows = [_row("Bronze dagger", ["Smithing"], ["Hammer"], ["Anvil"],
                {"materials": [{"quantity": "1", "name": "Bronze bar"}], "ticks": "5", "members": False,
                 "skills": [{"name": "Smithing", "level": "1", "experience": "12.5", "boostable": "Yes"}],
                 "output": {"quantity": "1", "name": "Bronze dagger"}})]
    nodes, edges, groups = build_recipe_roster(rows, _itemdict(), _facilities(), set())
    n = _map(nodes)["recipe:bronze-dagger"]
    assert n.kind is NodeKind.RECIPE and n.name == "Bronze dagger"
    assert n.data["xp"] == {"Smithing": 12.5} and n.data["ticks"] == 5 and n.data["members"] is False
    assert n.data["source_token"] == "Bucket:recipe page=Bronze dagger output=Bronze dagger"
    types = [(e.type, e.dst, e.data.get("role")) for e in edges]
    assert (EdgeType.CONSUMES, "item:2349", "material") in types      # 1 Bronze bar
    assert (EdgeType.CONSUMES, "item:1337", "tool") in types          # Hammer as tool
    assert (EdgeType.PRODUCES, "item:1205", None) in types            # Bronze dagger
    assert (EdgeType.REQUIRES_FACILITY, "facility:anvil", None) in types
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    g = groups[req.cond_group]
    atom = g.children[0]
    assert atom.atom_type is AtomType.SKILL_LEVEL and atom.ref_node == "skill:smithing" and atom.threshold == 1


def test_multi_skill_gates_and_xp():
    rows = [_row("Crystal thing", ["Smithing", "Crafting"], None, None,
                {"materials": [], "skills": [{"name": "Smithing", "level": "78", "experience": "2000"},
                                             {"name": "Crafting", "level": "78", "experience": "2000"}],
                 "output": {"quantity": "1", "name": "Bronze bar"}})]
    nodes, edges, groups = build_recipe_roster(rows, _itemdict(), _facilities(), set())
    n = _map(nodes)["recipe:bronze-bar"]
    assert n.data["xp"] == {"Smithing": 2000, "Crafting": 2000}
    g = groups[[e for e in edges if e.type is EdgeType.REQUIRES][0].cond_group]
    refs = {a.ref_node for a in g.children}
    assert refs == {"skill:smithing", "skill:crafting"}


def test_facility_alias_resolution():
    rows = [_row("Cooked meat", ["Cooking"], None, ["Cooking range"],
                {"materials": [{"quantity": "1", "name": "Raw beef"}], "skills": [{"name": "Cooking", "level": "1", "experience": "30"}],
                 "output": {"quantity": "1", "name": "Cooked meat"}})]
    _, edges, _ = build_recipe_roster(rows, _itemdict(), _facilities(), set())
    assert any(e.type is EdgeType.REQUIRES_FACILITY and e.dst == "facility:range" for e in edges)  # Cooking range -> facility:range via alias


def test_html_unescape_resolution_and_multimethod_slug():
    import json as _j
    rows = [_row("Bronze bar", ["Smithing"], None, ["Anvil"],
                {"materials": [], "skills": [{"name": "Smithing", "level": "1", "experience": "6"}],
                 "output": {"quantity": "1", "name": "Bronze bar", "subtxt": "Normal furnace"}}),
            _row("Bronze bar", ["Smithing"], None, ["Anvil"],
                {"materials": [], "skills": [{"name": "Smithing", "level": "1", "experience": "6"}],
                 "output": {"quantity": "1", "name": "Bronze bar", "subtxt": "Blast Furnace"}})]
    nodes, _, _ = build_recipe_roster(rows, _itemdict(), _facilities(), set())
    ids = {n.id for n in nodes}
    assert "recipe:bronze-bar-normal-furnace" in ids and "recipe:bronze-bar-blast-furnace" in ids


def test_unresolvable_output_skips_recipe_and_charge_slug_reserved():
    rows = [_row("Mystery", ["Crafting"], None, None,
                {"materials": [], "skills": [{"name": "Crafting", "level": "1", "experience": "1"}],
                 "output": {"quantity": "1", "name": "Nonexistent item xyz"}}),
            _row("Bronze bar", ["Smithing"], None, None,
                {"materials": [], "skills": [], "output": {"quantity": "1", "name": "Bronze bar"}})]
    nodes, _, _ = build_recipe_roster(rows, _itemdict(), _facilities(), {"bronze-bar"})
    ids = {n.id for n in nodes}
    assert not any("Nonexistent" in n.name for n in nodes)          # unresolvable output -> skipped
    assert "recipe:bronze-bar-2" in ids and "recipe:bronze-bar" not in ids  # charge slug 'bronze-bar' reserved -> guard bumps to -2


def test_deterministic():
    rows = [_row("Bronze dagger", ["Smithing"], ["Hammer"], ["Anvil"],
                {"materials": [{"quantity": "1", "name": "Bronze bar"}], "skills": [{"name": "Smithing", "level": "1", "experience": "12.5"}],
                 "output": {"quantity": "1", "name": "Bronze dagger"}})]
    a = build_recipe_roster(rows, _itemdict(), _facilities(), set())[0]
    b = build_recipe_roster(rows, _itemdict(), _facilities(), set())[0]
    assert [n.id for n in a] == [n.id for n in b]


def test_unresolvable_material_skips_edge_not_recipe():
    rows = [_row("Bronze dagger", ["Smithing"], None, None,
                {"materials": [{"quantity": "1", "name": "Bronze bar"},
                               {"quantity": "1", "name": "Nonexistent ingredient xyz"}],
                 "skills": [{"name": "Smithing", "level": "1", "experience": "12.5"}],
                 "output": {"quantity": "1", "name": "Bronze dagger"}})]
    nodes, edges, _ = build_recipe_roster(rows, _itemdict(), _facilities(), set())
    assert any(n.id == "recipe:bronze-dagger" for n in nodes)  # recipe kept despite an unresolvable material
    mat_edges = [e for e in edges if e.type is EdgeType.CONSUMES and e.data.get("role") == "material"]
    assert len(mat_edges) == 1                                  # only the resolvable material -> 1 edge (not 2)
    assert mat_edges[0].dst == "item:2349"                      # the resolvable one (Bronze bar)
