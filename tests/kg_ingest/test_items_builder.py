from kg_ingest.builders.items import build_items
from osrs_planner.engine.kg.model import EdgeType, NodeKind

# Minimal in-memory dictionary records (mirrors data/item_dictionary.json shape).
DICT = [
    {"item_id": 1704, "name": "Amulet of glory", "members": True, "page_name": "Amulet of glory",
     "is_variant": True, "is_canonical": False, "version_anchor": "Uncharged"},
    {"item_id": 1712, "name": "Amulet of glory(4)", "members": True, "page_name": "Amulet of glory",
     "is_variant": True, "is_canonical": True, "version_anchor": "4"},
    {"item_id": 4587, "name": "Dragon scimitar", "members": True, "page_name": "Dragon scimitar",
     "is_variant": False, "is_canonical": True},
    {"item_id": 99, "name": "Referenced thing", "members": False, "page_name": "Referenced thing",
     "is_variant": False, "is_canonical": True},
]

def _by_id(nodes):
    return {n.id: n for n in nodes}

def test_multivariant_page_emits_page_node_variants_and_bridges():
    nodes, edges, groups = build_items(DICT, {"Amulet of glory"}, [], set())
    assert groups == {}
    byid = _by_id(nodes)
    page = byid["item:amulet-of-glory"]
    assert page.kind is NodeKind.ITEM and page.data == {"is_page": True} and page.name == "Amulet of glory"
    v = byid["item:1712"]
    assert v.name == "Amulet of glory(4)" and v.slug == "1712"
    assert v.data == {"members": True, "is_canonical": True, "version_anchor": "4"}
    se = [e for e in edges if e.type is EdgeType.SAME_ENTITY]
    pairs = {(e.src, e.dst) for e in se}
    assert ("item:1704", "item:amulet-of-glory") in pairs
    assert ("item:1712", "item:amulet-of-glory") in pairs
    assert all(e.data["basis"] == "shares wiki page 'Amulet of glory'" for e in se)

def test_single_variant_referenced_item_has_no_page_or_bridge():
    nodes, edges, _ = build_items(DICT, set(), [], {"item:99"})
    byid = _by_id(nodes)
    assert byid["item:99"].data == {"members": False, "is_canonical": True}
    assert "item:referenced-thing" not in byid       # no page node for single-variant
    assert not edges                                 # no same_entity bridge

def test_owned_ids_are_skipped_to_avoid_dedup_conflict():
    nodes, _, _ = build_items(DICT, set(), [], {"item:4587"}, owned_ids=frozenset({"item:4587"}))
    assert "item:4587" not in _by_id(nodes)          # build_goals owns it; build_items must not re-emit
