import importlib.util, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
parse = _load("parse_recq", "data/parse_recommended_equipment.py")

def test_extract_link_names():
    cell = ('{"Recommended Equipment":{"cape":['
            '"<span>[[File:Graceful cape.png|link=Graceful cape]]</span>[[Graceful cape|Graceful cape]]"]}}')
    got = parse.extract_slot_items(cell)
    assert got == [("cape", "Graceful cape")]

def test_extract_skips_non_link_noise():
    assert parse.extract_slot_items('{"Recommended Equipment":{"ammo":["Arrows"]}}') == []
