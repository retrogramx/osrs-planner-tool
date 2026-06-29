from kg_ingest.builders.npcs import _npc_slug, build_npcs
from osrs_planner.engine.kg.model import NodeKind

RECS = [{"sold_by": "Al Kharid General Store"}, {"sold_by": "Mystic Shop"}]
SHOP_IB = {"Al Kharid General Store": {"owner": ["[[Shop keeper (Al Kharid)|Shop keeper]]"]},
           "Mystic Shop": {"owner": ["[[Sins of the Father]]"]}}   # a QUEST mis-linked as owner
NPC_IB = {"Shop keeper (Al Kharid)": {"locations": ["[[Al Kharid]]"], "is_npc": True},
          "Sins of the Father": {"locations": [], "is_npc": False}}  # no NPC infobox -> not an npc

def test_npc_slug():
    assert _npc_slug("Shop keeper (Al Kharid)") == "npc:shop-keeper-al-kharid"

def test_build_npcs_emits_node_for_real_npc_only():
    nodes, edges, groups = build_npcs(RECS, SHOP_IB, NPC_IB, [], set(), set())
    ids = {n.id for n in nodes}
    assert "npc:shop-keeper-al-kharid" in ids
    assert "npc:sins-of-the-father" not in ids        # quest, no NPC infobox -> filtered, never fabricated
    n = next(n for n in nodes if n.id == "npc:shop-keeper-al-kharid")
    assert n.kind is NodeKind.NPC
    assert "role" not in n.data                        # role left unset (D2)
    assert edges == [] and groups == {}

def test_varrock_npcs_excluded():
    npc_ib = {"Aubury": {"locations": ["[[Varrock]]"], "is_npc": True}}
    recs = [{"sold_by": "Aubury's Rune Shop"}]
    shop_ib = {"Aubury's Rune Shop": {"owner": ["[[Aubury]]"]}}
    nodes, _, _ = build_npcs(recs, shop_ib, npc_ib, [], set(), {"Aubury"})
    assert nodes == []                                 # Aubury is a Varrock npc (build_map owns it)
