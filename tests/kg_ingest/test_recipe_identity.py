# tests/kg_ingest/test_recipe_identity.py
from osrs_planner.engine.kg.model import Node, NodeKind
from kg_ingest.recipe_identity import (
    resolve_recipe_payload, recipe_identity_hash, mint_slug, is_method_suffixed,
    _facility_lookup, _num, _as_list,
)
import json as _j


def _resolver(dictrecs):
    from kg_ingest.builders.map_varrock import make_item_resolver
    import html
    r = make_item_resolver(dictrecs)
    def resolve(name):
        iid = r(html.unescape((name or "").strip()))
        return f"item:{iid}" if iid is not None else None
    return resolve


def _itemdict():
    return [{"item_id": 2349, "name": "Bronze bar", "page_name": "Bronze bar", "is_canonical": True},
            {"item_id": 1205, "name": "Bronze dagger", "page_name": "Bronze dagger", "is_canonical": True},
            {"item_id": 1337, "name": "Hammer", "page_name": "Hammer", "is_canonical": True}]


def _facilities():
    return [Node(id="facility:anvil", kind=NodeKind.FACILITY, name="Anvil", slug="anvil", data={})]


def _row(page, skill, tool, facility, pj):
    return {"page_name": page, "uses_skill": skill, "uses_tool": tool,
            "uses_facility": facility, "production_json": _j.dumps(pj)}


def test_resolve_payload_shape():
    resolve = _resolver(_itemdict()); fac = _facility_lookup(_facilities())
    p = resolve_recipe_payload(_row("Bronze dagger", ["Smithing"], ["Hammer"], ["Anvil"],
        {"materials": [{"quantity": "1", "name": "Bronze bar"}], "ticks": "5", "members": False,
         "skills": [{"name": "Smithing", "level": "1", "experience": "12.5", "boostable": "Yes"}],
         "output": {"quantity": "1", "name": "Bronze dagger"}}), resolve, fac)
    assert p["out_dst"] == "item:1205" and p["out_name"] == "Bronze dagger"
    assert ("item:2349", 1, "material") in p["consumes"]
    assert ("item:1337", 1, "tool") in p["consumes"]
    assert p["produces"] == [("item:1205", 1)]
    assert p["facilities"] == ["facility:anvil"]
    assert p["atoms"] == [("skill:smithing", 1, True)]
    assert p["xp"] == {"Smithing": 12.5} and p["ticks"] == 5 and p["members"] is False


def test_resolve_payload_unresolvable_output_is_none():
    resolve = _resolver(_itemdict()); fac = _facility_lookup(_facilities())
    assert resolve_recipe_payload(_row("X", [], None, None,
        {"materials": [], "output": {"name": "Nonexistent xyz"}}), resolve, fac) is None
    # no output at all -> None too
    assert resolve_recipe_payload(_row("X", [], None, None, {"materials": []}), resolve, fac) is None


def test_identity_hash_order_independent_and_excludes_data():
    resolve = _resolver(_itemdict()); fac = _facility_lookup(_facilities())
    a = resolve_recipe_payload(_row("Bronze dagger", ["Smithing"], None, None,
        {"materials": [{"quantity": "1", "name": "Bronze bar"}], "ticks": "5",
         "skills": [{"name": "Smithing", "level": "1", "experience": "12.5"}],
         "output": {"quantity": "1", "name": "Bronze dagger"}}), resolve, fac)
    b = resolve_recipe_payload(_row("Bronze dagger", ["Smithing"], None, None,
        {"materials": [{"quantity": "1", "name": "Bronze bar"}], "ticks": "999",   # different ticks
         "skills": [{"name": "Smithing", "level": "1", "experience": "0.1"}],       # different xp
         "output": {"quantity": "1", "name": "Bronze dagger"}}), resolve, fac)
    assert recipe_identity_hash(a) == recipe_identity_hash(b)   # xp/ticks excluded from identity


def test_identity_hash_distinguishes_subtxt():
    resolve = _resolver(_itemdict()); fac = _facility_lookup(_facilities())
    base = {"materials": [], "output": {"quantity": "1", "name": "Bronze bar"}}
    a = resolve_recipe_payload(_row("Bronze bar", [], None, None,
        {**base, "output": {**base["output"], "subtxt": "Furnace"}}), resolve, fac)
    b = resolve_recipe_payload(_row("Bronze bar", [], None, None,
        {**base, "output": {**base["output"], "subtxt": "Blast Furnace"}}), resolve, fac)
    assert recipe_identity_hash(a) != recipe_identity_hash(b)


def test_mint_slug_guard_and_method():
    claimed = {"bronze-bar"}
    assert mint_slug("Bronze bar", "", claimed) == "bronze-bar-2"   # guarded
    assert mint_slug("Bronze bar", "Blast Furnace", claimed) == "bronze-bar-blast-furnace"
    assert "bronze-bar-2" in claimed and "bronze-bar-blast-furnace" in claimed


def test_is_method_suffixed():
    assert is_method_suffixed("bronze-bar-blast-furnace", "Bronze bar", "Blast Furnace") is True
    assert is_method_suffixed("bronze-bar", "Bronze bar", "Normal furnace") is False   # bare
    assert is_method_suffixed("bronze-bar-2", "Bronze bar", "") is False               # no subtxt
