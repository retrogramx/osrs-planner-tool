import importlib.util, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location("fetch_recipes", os.path.join(ROOT, "data", "fetch_recipes.py"))
fr = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fr)

def test_project_rows_keeps_fields_and_sorts():
    raw = [{"page_name": "B", "uses_skill": ["Smithing"], "uses_tool": ["Hammer"], "uses_facility": ["Anvil"], "production_json": "{}", "x": 1},
           {"page_name": "A", "uses_skill": ["Cooking"], "uses_tool": None, "uses_facility": None, "production_json": "{}"}]
    out = fr.project_rows(raw)
    assert [r["page_name"] for r in out] == ["A", "B"]
    assert set(out[0].keys()) == {"page_name", "uses_skill", "uses_tool", "uses_facility", "production_json"}
