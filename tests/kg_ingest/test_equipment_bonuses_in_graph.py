import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType, NodeKind

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def _bonus_node_for(s, item_node):
    es = [e for e in s.edges if e.type is EdgeType.HAS_BONUSES and e.src == item_node]
    assert len(es) == 1
    return s.node(es[0].dst)

def test_scythe_and_dharoks_bonuses_resolve_correctly():
    # the 2026-06-25 audit regression guards: selection must pick the CANONICAL values.
    s = JsonKGStore.from_dir(KG)
    scythe = _bonus_node_for(s, "item:22325")
    assert scythe.kind is NodeKind.EQUIPMENT_BONUSES
    assert scythe.data["stats"]["slash_attack_bonus"] == 125    # canonical, not the beta's 110
    assert scythe.data["weapon"]["combat_style"] == "Scythe"
    dharoks = _bonus_node_for(s, "item:4716")
    assert dharoks.data["stats"]["stab_defence_bonus"] == 45    # variant_idx 0, not the empty variant_idx 1

def test_bonuses_attach_to_variants_not_pages_and_ids_unique():
    s = JsonKGStore.from_dir(KG)
    # page node must NOT carry has_bonuses (only numeric variant ids do)
    assert not any(e.type is EdgeType.HAS_BONUSES and e.src == "item:scythe-of-vitur" for e in s.edges)
    ids = [e.id for e in s.edges]
    assert len(ids) == len(set(ids)), "duplicate edge id with four item-src edge types present"
