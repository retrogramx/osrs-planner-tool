from kg_ingest.builders.storeline import _norm, _base, index_by_shop, match_shop

KEYS = ["Varrock General Store", "Lowe's Archery Emporium", "Zaff's Superior Staffs!",
        "Ratpit bar (Varrock)", "Ratpit bar (Keldagrim)", "Aubury's Rune Shop."]

def test_exact_match():
    assert match_shop("Varrock General Store", KEYS) == "Varrock General Store"
    assert match_shop("Lowe's Archery Emporium", KEYS) == "Lowe's Archery Emporium"

def test_trailing_punctuation_match():
    assert match_shop("Zaff's Superior Staffs", KEYS) == "Zaff's Superior Staffs!"
    assert match_shop("Aubury's Rune Shop", KEYS) == "Aubury's Rune Shop."

def test_town_disambiguator_required():
    # bare base name collides across towns -> must pick the (Varrock) one, never Keldagrim
    assert match_shop("Ratpit Bar", KEYS) == "Ratpit bar (Varrock)"

def test_no_match_returns_none():
    assert match_shop("Baraek's Fur Stall", KEYS) is None
    assert match_shop("Varrock Apothecary", KEYS) is None

def test_index_by_shop_groups_rows():
    recs = [{"sold_by": "A", "sold_item": "x"}, {"sold_by": "A", "sold_item": "y"},
            {"sold_by": "B", "sold_item": "z"}]
    idx = index_by_shop(recs)
    assert sorted(r["sold_item"] for r in idx["A"]) == ["x", "y"]
    assert len(idx["B"]) == 1


from kg_ingest.builders.storeline import build_storeline
from osrs_planner.engine.kg.model import EdgeType

DICT = [   # members is a BOOLEAN in item_dictionary.json (Battlestaff is members)
    {"item_id": 1391, "name": "Battlestaff", "page_name": "Battlestaff", "is_canonical": True, "members": True},
    {"item_id": 1381, "name": "Staff of air", "page_name": "Staff of air", "is_canonical": True, "members": False},
    {"item_id": 6814, "name": "Fur", "page_name": "Fur", "is_canonical": True, "members": False},
]
# Zaff is covered (has Storeline rows); Baraek is a dialogue-shop (no Storeline rows).
STORELINE = [
    {"sold_by": "Zaff's Superior Staffs!", "sold_item": "Staff of air", "store_currency": "Coins"},
    {"sold_by": "Zaff's Superior Staffs!", "sold_item": "Battlestaff", "store_currency": "Coins"},
]
MAP = {"shops": [
    {"id": "shop:zaffs-superior-staffs", "name": "Zaff's Superior Staffs",
     "sells": [{"item_name": "Battlestaff", "source_token": "Zaff sells battlestaves",
                "condition": {"type": "quest", "ref": "What Lies Below", "state": "in_progress"}}]},
    {"id": "shop:baraeks-fur-stall", "name": "Baraek's Fur Stall",
     "sells": [{"item_name": "Fur", "source_token": "Baraek sells fur"}]},
]}

def _sells(edges):
    return {(e.src, e.dst, e.cond_group is not None) for e in edges if e.type is EdgeType.SELLS}

def test_covered_shop_storeline_supplies_ungated_overlay_owns_gated():
    nodes, edges, groups = build_storeline(STORELINE, MAP, DICT)
    s = _sells(edges)
    # Storeline supplies the ungated staff; the gated battlestaff is overlay-owned (gated edge)
    assert ("shop:zaffs-superior-staffs", "item:1381", False) in s   # Storeline staff
    assert ("shop:zaffs-superior-staffs", "item:1391", True) in s    # gated battlestaff (overlay)
    # NO duplicate: Storeline must NOT also emit an ungated battlestaff (ownership rule)
    assert ("shop:zaffs-superior-staffs", "item:1391", False) not in s
    assert nodes == []
    assert len(groups) == 1                                          # one gate cond_group

def test_dialogue_shop_falls_back_to_owner_sells():
    nodes, edges, groups = build_storeline(STORELINE, MAP, DICT)
    s = _sells(edges)
    assert ("shop:baraeks-fur-stall", "item:6814", False) in s       # owner-sells fallback

def test_storeline_edge_carries_members_no_cost_tokens():
    nodes, edges, groups = build_storeline(STORELINE, MAP, DICT)
    staff = next(e for e in edges if e.dst == "item:1381")
    assert staff.data["members"] is False
    # validate_cost Inv 6 forbids price/cost/currency keys in the graph -> none on the edge
    assert "currency" not in staff.data
    assert "store_currency" not in staff.data
    assert "store_buy_price" not in staff.data

def test_unresolved_sold_item_is_skipped_not_fabricated():
    sl = STORELINE + [{"sold_by": "Zaff's Superior Staffs!", "sold_item": "Nonexistent thing", "store_currency": "Coins"}]
    nodes, edges, groups = build_storeline(sl, MAP, DICT)
    assert all(e.dst is not None for e in edges)
    assert not any(e.dst == "item:None" for e in edges)
