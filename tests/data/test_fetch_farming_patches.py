import importlib.util, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

def _load(mod_name, rel):
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

fetch = _load("fetch_farming_patches", "data/fetch_farming_patches.py")

def test_classify_member_routes_by_infobox():
    assert fetch.classify_member(["Infobox Scenery"]) == "patch_type"
    assert fetch.classify_member(["Infobox Location"]) == "place"     # Coral Nurseries
    assert fetch.classify_member(["Infobox NPC"]) == "npc"            # Chet
    assert fetch.classify_member([]) == "other"

def test_classify_member_umbrella_by_name_is_caller_concern():
    # Special patches has an Infobox but is treated as an umbrella by the coverage verifier,
    # not here; classify_member only reads infoboxes. Scenery -> patch_type.
    assert fetch.classify_member(["Infobox Scenery"]) == "patch_type"
