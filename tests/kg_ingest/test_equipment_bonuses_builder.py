from kg_ingest.builders.equipment_bonuses import select_bonus_record, build_equipment_bonuses
from osrs_planner.engine.kg.model import EdgeType, NodeKind

def _stats(**kw):
    base = {k: 0 for k in (
        "stab_attack_bonus","slash_attack_bonus","crush_attack_bonus","magic_attack_bonus","range_attack_bonus",
        "stab_defence_bonus","slash_defence_bonus","crush_defence_bonus","magic_defence_bonus","range_defence_bonus",
        "strength_bonus","ranged_strength_bonus","prayer_bonus","magic_damage_bonus")}
    base.update(kw); return base

SCYTHE = [
    {"item_id":22325,"item":"Scythe of vitur","page_name":"Scythe of vitur","slot":"2h","stat_variant_index":0,
     "stats":_stats(slash_attack_bonus=125,strength_bonus=75),"weapon":{"weapon_attack_speed":5,"weapon_attack_range":"1","combat_style":"Slash"}},
    {"item_id":22325,"item":"Scythe of vitur","page_name":"Scythe of vitur","slot":"2h","stat_variant_index":1,
     "stats":_stats(slash_attack_bonus=75),"weapon":{"weapon_attack_speed":5,"weapon_attack_range":"1","combat_style":"Slash"}},
    {"item_id":22325,"item":"Scythe of vitur","page_name":"Scythe of vitur (beta)","slot":"2h","stat_variant_index":None,
     "stats":_stats(slash_attack_bonus=110),"weapon":{"weapon_attack_speed":5,"weapon_attack_range":"1","combat_style":"Slash"}},
]
DHAROK = [
    {"item_id":4716,"item":"Dharok's helm","page_name":"Dharok's helm","slot":"head","stat_variant_index":0,"stats":_stats(stab_defence_bonus=45)},
    {"item_id":4716,"item":"Dharok's helm","page_name":"Dharok's helm","slot":"head","stat_variant_index":1,"stats":_stats()},
]

def test_select_drops_beta_and_prefers_variant_zero():
    assert select_bonus_record(SCYTHE, "Scythe of vitur")["stats"]["slash_attack_bonus"] == 125
    assert select_bonus_record(DHAROK, "Dharok's helm")["stats"]["stab_defence_bonus"] == 45

def test_build_emits_node_and_edge_per_owned_item():
    eq = SCYTHE + DHAROK
    owned = {"item:22325"}    # Dharok's NOT owned -> skipped
    canon = {22325:"Scythe of vitur", 4716:"Dharok's helm"}
    nodes, edges, groups = build_equipment_bonuses(eq, owned, canon)
    assert groups == {}
    assert [n.id for n in nodes] == ["equipment_bonuses:22325"]
    n = nodes[0]
    assert n.kind is NodeKind.EQUIPMENT_BONUSES
    assert n.data["stats"]["slash_attack_bonus"] == 125 and n.data["slot"] == "2h"
    assert n.data["weapon"]["combat_style"] == "Slash"
    assert len(edges) == 1
    e = edges[0]
    assert e.type is EdgeType.HAS_BONUSES and e.src == "item:22325" and e.dst == "equipment_bonuses:22325"
    assert e.data == {} and e.cond_group is None

def test_build_omits_weapon_block_for_armour():
    nodes, _, _ = build_equipment_bonuses(DHAROK, {"item:4716"}, {4716:"Dharok's helm"})
    assert "weapon" not in nodes[0].data


# --- select_bonus_record all-zero demotion regression tests ---

# index=0 is all-zero (uncharged/inactive form); index=1 is non-zero (active form).
_DEMOTION_ITEM = [
    {"item_id":99999,"item":"Test item","page_name":"Test item","slot":"weapon",
     "stat_variant_index":0,"stats":_stats()},
    {"item_id":99999,"item":"Test item","page_name":"Test item","slot":"weapon",
     "stat_variant_index":1,"stats":_stats(slash_attack_bonus=50)},
]

# All variants are all-zero (genuinely statless item).
_ALL_ZERO_ITEM = [
    {"item_id":88888,"item":"Statless item","page_name":"Statless item","slot":"weapon",
     "stat_variant_index":0,"stats":_stats()},
    {"item_id":88888,"item":"Statless item","page_name":"Statless item","slot":"weapon",
     "stat_variant_index":1,"stats":_stats()},
]


def test_select_prefers_nonzero_active_variant_over_zero_index_all_zero():
    """When index=0 is all-zero and index=1 is non-zero, the non-zero active form wins."""
    rec = select_bonus_record(_DEMOTION_ITEM, "Test item")
    assert rec["stat_variant_index"] == 1
    assert rec["stats"]["slash_attack_bonus"] == 50


def test_select_returns_index_zero_when_all_variants_are_all_zero():
    """When every variant is all-zero, the genuinely-statless index=0 record is kept."""
    rec = select_bonus_record(_ALL_ZERO_ITEM, "Statless item")
    assert rec["stat_variant_index"] == 0
