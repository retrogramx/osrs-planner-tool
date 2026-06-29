from kg_ingest.builders.shops import build_shops
from osrs_planner.engine.kg.model import EdgeType

DICT = [{"item_id": 1931, "name": "Pot", "page_name": "Pot", "is_canonical": True, "members": False},
        {"item_id": 1935, "name": "Jug", "page_name": "Jug", "is_canonical": True, "members": False}]
RECS = [{"sold_by": "Al Kharid General Store", "sold_item": "Pot", "store_currency": "Coins"},
        {"sold_by": "Al Kharid General Store", "sold_item": "Jug", "store_currency": "Coins"},
        {"sold_by": "Al Kharid General Store", "sold_item": "Ghost item", "store_currency": "Coins"}]
IB = {"Al Kharid General Store": {"locations": ["[[Al Kharid]]"], "members": "No", "owner": []}}

def _sells(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.SELLS}

def test_sells_emitted_for_resolved_items():
    nodes, edges, _ = build_shops(RECS, IB, [], DICT, set())
    s = _sells(edges)
    assert ("shop:al-kharid-general-store", "item:1931") in s
    assert ("shop:al-kharid-general-store", "item:1935") in s

def test_unresolved_item_skipped_not_fabricated():
    nodes, edges, _ = build_shops(RECS, IB, [], DICT, set())
    assert not any(e.dst == "item:None" for e in edges)
    assert all(e.dst is not None for e in edges)

def test_sells_edge_has_no_currency_or_price_keys():
    nodes, edges, _ = build_shops(RECS, IB, [], DICT, set())
    sells = next(e for e in edges if e.type is EdgeType.SELLS)
    for forbidden in ("currency", "store_currency", "price", "cost"):
        assert forbidden not in sells.data           # validate_cost Inv 6
    assert sells.data["source_token"] == "Bucket:Storeline"
