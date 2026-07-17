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

def test_resolve_item_id_prefers_exact_page_match_over_unobtainable_variant():
    # Two dict records share name "Foo": an unobtainable quest variant (lower item_id, so a
    # naive first-wins/lowest-id pick would be wrong) and the real page (page_name == name).
    dict_recs = [
        {"item_id": 5, "name": "Foo", "page_name": "Foo (quest)", "is_canonical": True},
        {"item_id": 10, "name": "Foo", "page_name": "Foo", "is_canonical": True},
    ]
    assert parse.resolve_item_id("Foo", dict_recs) == 10

def test_resolve_item_id_falls_back_to_canonical_then_lowest_id():
    dict_recs = [
        {"item_id": 20, "name": "Bar", "page_name": "Bar (variant)", "is_canonical": False},
        {"item_id": 15, "name": "Bar", "page_name": "Bar (other variant)", "is_canonical": True},
        {"item_id": 30, "name": "Bar", "page_name": "Bar (yet another)", "is_canonical": True},
    ]
    # no exact page_name=="Bar" match -> prefer is_canonical -> lowest item_id among canonical
    assert parse.resolve_item_id("Bar", dict_recs) == 15

def test_resolve_item_id_unresolvable_returns_none():
    assert parse.resolve_item_id("Nope", [{"item_id": 1, "name": "Other",
                                            "page_name": "Other", "is_canonical": True}]) is None
