from kg_ingest.builders.npcs import operator_map, operator_roster

# Storeline gives the derived roster; the shop brick owner field gives the operators.
RECS = [{"sold_by": "Al Kharid General Store", "sold_item": "Pot"},
        {"sold_by": "Slayer Rewards", "sold_item": "Broad bolts"},
        {"sold_by": "Varrock General Store", "sold_item": "Pot"}]  # Varrock -> excluded
SHOP_IB = {
    "Al Kharid General Store": {"owner": ["[[Shop keeper (Al Kharid)|Shop keeper]]"]},
    "Slayer Rewards": {"owner": ["[[Turael]]", "[[Spria]]"]},          # multi-owner
    "Varrock General Store": {"owner": ["[[Shop keeper]]"]},
}
VARROCK = {"Varrock General Store"}

def test_operator_map_parses_owner_links_derived_only():
    m = operator_map(RECS, SHOP_IB, VARROCK)
    assert m["Al Kharid General Store"] == ["Shop keeper (Al Kharid)"]   # link target, not display
    assert m["Slayer Rewards"] == ["Turael", "Spria"]                   # multi-owner, ordered
    assert "Varrock General Store" not in m                             # Varrock excluded

def test_operator_roster_is_sorted_distinct():
    assert operator_roster(RECS, SHOP_IB, VARROCK) == ["Shop keeper (Al Kharid)", "Spria", "Turael"]
