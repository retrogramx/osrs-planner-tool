import importlib.util, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "fetch_facility_infoboxes", os.path.join(ROOT, "data", "fetch_facility_infoboxes.py"))
ffi = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ffi)

def test_infoboxes_in_detects_templates():
    assert ffi.infoboxes_in("{{Infobox Scenery|name=Anvil}}\nfoo") == ["Infobox Scenery"]
    assert ffi.infoboxes_in("{{ Infobox NPC |x=1}}") == ["Infobox NPC"]
    assert ffi.infoboxes_in("no infobox here") == []
    assert ffi.infoboxes_in("{{Infobox Shop}}{{Infobox Scenery}}") == ["Infobox Scenery", "Infobox Shop"]
