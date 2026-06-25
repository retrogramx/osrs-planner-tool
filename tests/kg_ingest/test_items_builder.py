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

def test_owned_variant_on_multivariant_page_skips_node_and_bridge():
    # A variant id owned by another builder must get NEITHER a node NOR a same_entity
    # bridge — its rekeyed global edge id would collide with the owning builder's edge.
    nodes, edges, _ = build_items(DICT, {"Amulet of glory"}, [], set(),
                                  owned_ids=frozenset({"item:1712"}))
    byid = _by_id(nodes)
    assert "item:1712" not in byid                   # owned variant node not re-emitted
    assert "item:1704" in byid                        # non-owned variant still emitted
    se_srcs = {e.src for e in edges if e.type is EdgeType.SAME_ENTITY}
    assert "item:1712" not in se_srcs                 # no bridge for the owned variant
    assert "item:1704" in se_srcs                     # bridge for the non-owned variant remains


# --- L2 family tests ---

FAMILY_DICT = DICT + [
    {"item_id": 4081, "name": "Salve amulet", "members": True, "page_name": "Salve amulet",
     "is_variant": False, "is_canonical": True},
    {"item_id": 12017, "name": "Salve amulet(i)", "members": True, "page_name": "Salve amulet(i)",
     "is_variant": True, "is_canonical": True, "version_anchor": "Nightmare Zone"},
    {"item_id": 25250, "name": "Salve amulet(i)", "members": True, "page_name": "Salve amulet(i)",
     "is_variant": True, "is_canonical": False, "version_anchor": "Soul Wars"},
]
SALVE_FAMILY = [{
    "family_name": "Salve amulet (all variants)", "slug": "salve-amulet-family",
    "members": [{"page": "Salve amulet", "basis": "base"},
                {"page": "Salve amulet(i)", "basis": "imbue"}],
}]


def test_family_node_and_member_bridges():
    nodes, edges, _ = build_items(FAMILY_DICT, set(), SALVE_FAMILY, set())
    byid = _by_id(nodes)
    fam = byid["item:salve-amulet-family"]
    assert fam.data == {"is_family": True} and fam.name == "Salve amulet (all variants)"
    se = {(e.src, e.dst, e.data["basis"]) for e in edges if e.type is EdgeType.SAME_ENTITY}
    # single-variant member bridges from the VARIANT node; multi-variant member from the PAGE node
    assert ("item:4081", "item:salve-amulet-family", "base") in se
    assert ("item:salve-amulet-i", "item:salve-amulet-family", "imbue") in se


def test_multicanonical_page_tolerated():
    # Salve amulet(i) here has two is_canonical rows in real data; builder must not crash/assume singular.
    multi = [
        {"item_id": 25246, "name": "Ring of suffering (i)", "members": True,
         "page_name": "Ring of suffering (i)", "is_variant": True, "is_canonical": True, "version_anchor": "Uncharged"},
        {"item_id": 20657, "name": "Ring of suffering (i)", "members": True,
         "page_name": "Ring of suffering (i)", "is_variant": True, "is_canonical": True, "version_anchor": "Recoil"},
    ]
    nodes, edges, _ = build_items(multi, {"Ring of suffering (i)"}, [], set())
    canon = [n for n in nodes if n.data.get("is_canonical")]
    assert len(canon) == 2   # both kept; page node still anchors
    assert _by_id(nodes)["item:ring-of-suffering-i"].data == {"is_page": True}


def test_owned_single_variant_family_member_skips_l2_bridge():
    # If a single-variant member's anchor id is owned by another builder,
    # the L2 family bridge must be skipped (src would collide on rekeyed global edge id).
    owned_family = [{
        "family_name": "Salve amulet (all variants)", "slug": "salve-amulet-family",
        "members": [{"page": "Salve amulet", "basis": "base"},
                    {"page": "Salve amulet(i)", "basis": "imbue"}],
    }]
    # item:4081 is the single-variant anchor for "Salve amulet" — mark it owned
    nodes, edges, _ = build_items(FAMILY_DICT, set(), owned_family, set(),
                                  owned_ids=frozenset({"item:4081"}))
    se_srcs = {e.src for e in edges if e.type is EdgeType.SAME_ENTITY}
    assert "item:4081" not in se_srcs                # owned single-variant anchor: bridge skipped
    assert "item:salve-amulet-i" in se_srcs          # non-owned multi-variant page anchor: bridge present
