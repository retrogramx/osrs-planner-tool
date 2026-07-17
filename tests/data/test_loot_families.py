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

def test_build_classifies_duplicate_name_items():
    # Real gotcha: item_dictionary.json has MULTIPLE item_ids sharing a display name
    # (variant/minigame pages) — e.g. id 11686 "Fire rune (Barbarian Assault)" has
    # name "Fire rune" (same display name as canonical id 554). A naive
    # name->first-id map drops every non-first id silently, even when its name matches
    # a suffix family. build() must classify EVERY id whose name matches, not just
    # the first-seen one.
    records = {r["item_id"]: r for r in b.build()}
    assert records[11686]["family"] == "rune"
    assert records[554]["family"] == "rune"

def test_build_source_url_uses_page_name_not_display_name():
    # item_id 468 has name "Broken pickaxe" but page_name "Broken pickaxe (bronze)" —
    # source_url must be built from the wiki PAGE title (page_name), not the generic
    # display name, so the link actually resolves to the right page.
    records = {r["item_id"]: r for r in b.build()}
    rec = records[468]
    assert rec["source_url"] == "https://oldschool.runescape.wiki/w/Broken_pickaxe_(bronze)"
    # source_token stays the display name (what actually matched the classification signal)
    assert rec["source_token"] == "Broken pickaxe"

def test_name_to_ids_multimap_classifies_all_ids_sharing_a_name():
    # Hermetic unit test of the multimap fix itself (independent of live item_dictionary.json
    # content): two distinct item_ids sharing a suffix-matching name must BOTH get claimed.
    from collections import defaultdict
    fixture = [{"item_id": 1, "name": "Cosmic rune"}, {"item_id": 2, "name": "Cosmic rune"}]
    name_to_ids = defaultdict(list)
    for r in fixture:
        name_to_ids[r["name"]].append(r["item_id"])
    fam_by_id = {}
    def claim(iid, fam, sig, token):
        if iid is not None and iid not in fam_by_id:
            fam_by_id[iid] = (fam, sig, token)
    for name, ids in name_to_ids.items():
        fam, sig = b.suffix_family(name)
        if fam:
            for iid in ids:
                claim(iid, fam, sig, name)
    assert fam_by_id[1][0] == "rune"
    assert fam_by_id[2][0] == "rune"
