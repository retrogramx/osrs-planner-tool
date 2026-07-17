import importlib.util, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b = _load("build_loot_families", "data/build_loot_families.py")

def test_suffix_family_seed():
    fam, sig = b.suffix_family("Ranarr seed")
    assert fam == "seed" and sig.startswith("name_suffix")

def test_grimy_herb_family_from_kg():
    fams = b.recipe_families()          # {item_name: (family, signal)}
    # real KG item names are "Grimy ranarr weed" -> "Ranarr weed" (not "Grimy ranarr" —
    # the brief's sample name was wrong; verified live against kg/nodes.json+edges.json).
    assert fams.get("Grimy ranarr weed", (None,))[0] == "herb"
    assert fams.get("Ranarr weed", (None,))[0] == "herb"

def test_gear_vs_utility_split():
    # a real combat body has family gear; a statless equippable is utility
    eq = b.equipment_families()         # {item_id: (family, signal)}
    # Bandos chestplate id 11832 (combat) -> gear ; Games necklace(8) id 3853 -> utility
    assert eq.get(11832, (None,))[0] == "gear"
    assert eq.get(3853, (None,))[0] == "utility"

def test_equipment_families_dedupes_stat_variants_via_canonical_selection():
    # items_equipment.json carries MULTIPLE records per item_id (stat-variant/(beta) dupes);
    # a naive "last record in file order wins" pick can land on an all-zero INACTIVE variant
    # and misclassify a real gear piece as utility. equipment_families() must select the
    # canonical/active record (same selection rule as kg_ingest.builders.equipment_bonuses).
    eq = b.equipment_families()
    # Ahrim's hood (item_id 4708) is a real duplicated id in items_equipment.json: an
    # all-zero-stats record sorts after the real combat-stat record in file order.
    assert eq.get(4708, (None,))[0] == "gear"

def test_equipment_families_guards_none_item_id():
    # items_equipment.json has records with item_id=None (unresolved page) — must not crash
    # and must not appear as a None key in the output.
    eq = b.equipment_families()
    assert None not in eq
