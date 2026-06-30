import importlib.util, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "fetch_recipe_facilities", os.path.join(ROOT, "data", "fetch_recipe_facilities.py"))
frf = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(frf)

def test_project_rows_drops_empty_and_sorts():
    raw = [
        {"page_name": "B", "uses_facility": ["Anvil"], "uses_skill": ["Smithing"], "extra": 1},
        {"page_name": "A", "uses_facility": None, "uses_skill": ["Magic"]},       # dropped
        {"page_name": "C", "uses_facility": [""], "uses_skill": []},               # dropped (only empty)
        {"page_name": "D", "uses_facility": ["Furnace"], "uses_skill": ["Crafting"]},
    ]
    out = frf.project_rows(raw)
    assert [r["page_name"] for r in out] == ["B", "D"]
    assert set(out[0].keys()) == {"page_name", "uses_facility", "uses_skill"}   # projected
