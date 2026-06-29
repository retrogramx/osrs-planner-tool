from kg_ingest.builders.npcs import build_npcs
from osrs_planner.engine.kg.model import EdgeType

RECS = [{"sold_by": "Slayer Rewards"}, {"sold_by": "Al Kharid General Store"}]
SHOP_IB = {"Slayer Rewards": {"owner": ["[[Turael]]", "[[Spria]]"]},
           "Al Kharid General Store": {"owner": ["[[Shop keeper (Al Kharid)|Shop keeper]]"]}}
NPC_IB = {"Turael": {"locations": ["[[Burthorpe]]"], "is_npc": True},
          "Spria": {"locations": ["[[Draynor Village]]"], "is_npc": True},
          "Shop keeper (Al Kharid)": {"locations": ["[[Al Kharid]]"], "is_npc": True}}

def _ops(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.OPERATES}

def test_operates_edges_npc_to_shop():
    nodes, edges, _ = build_npcs(RECS, SHOP_IB, NPC_IB, [], set(), set())
    o = _ops(edges)
    assert ("npc:turael", "shop:slayer-rewards") in o
    assert ("npc:spria", "shop:slayer-rewards") in o           # multi-owner -> one edge per master
    assert ("npc:shop-keeper-al-kharid", "shop:al-kharid-general-store") in o

def test_operates_dst_is_shop_id():
    nodes, edges, _ = build_npcs(RECS, SHOP_IB, NPC_IB, [], set(), set())
    assert all(e.dst.startswith("shop:") for e in edges if e.type is EdgeType.OPERATES)
