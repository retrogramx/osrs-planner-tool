"""Derive data/loot_families.json: item_id -> resource family, from equipment slot + recipe grammar
+ name suffix + owner overrides. Filter-side (read by lootfilter, NOT assemble.py). Deterministic.
Run: python data/build_loot_families.py"""
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)                        # for kg_ingest.* (run standalone: script dir is on path, ROOT is not)
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))   # for osrs_planner.* (imported by the equipment_bonuses builder)

from kg_ingest.builders.equipment_bonuses import select_bonus_record  # noqa: E402

SRC = "https://oldschool.runescape.wiki/w/"

# (suffix, family) — order matters; longer/more-specific suffixes first.
SUFFIX_FAMILIES = [(" seedling", "seed"), (" seed", "seed"), (" logs", "log"), (" log", "log"),
                   (" ore", "ore"), (" bar", "bar"), (" rune", "rune"), (" arrow", "ammo"),
                   (" bolts", "ammo"), (" dart", "ammo"), (" javelin", "ammo"), (" bones", "bones"),
                   (" ashes", "bones")]

def suffix_family(name):
    low = name.lower()
    for suf, fam in SUFFIX_FAMILIES:
        if low.endswith(suf):
            return fam, f"name_suffix:{suf.strip()}"
    return None, None

def _kg():
    # kg/nodes.json and kg/edges.json are each a committed flat JSON list of Node/Edge dicts
    # (NOT wrapped in {"nodes": [...]} / {"edges": [...]}) — verified live against the committed
    # graph before writing this.
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    return nodes, edges

def recipe_families():
    """{item_name: (family, signal)} — herb (grimy->clean Herblore), food (Cooking-produced)."""
    nodes, edges = _kg()
    by_id = {n["id"]: n for n in nodes}
    cons, prod = {}, {}
    for e in edges:
        if e["type"] == "consumes": cons.setdefault(e["src"], []).append(e["dst"])
        elif e["type"] == "produces": prod.setdefault(e["src"], []).append(e["dst"])
    nm = lambda nid: (by_id.get(nid) or {}).get("name")
    out = {}
    for n in nodes:
        if n.get("kind") != "recipe":
            continue
        xp = (n.get("data") or {}).get("xp") or {}
        prods = [nm(p) for p in prod.get(n["id"], []) if nm(p)]
        conss = [nm(c) for c in cons.get(n["id"], []) if nm(c)]
        if "Herblore" in xp:
            grimy = [c for c in conss if c.startswith("Grimy ")]
            if grimy:                                  # a cleaning recipe: Grimy X -> X
                for c in grimy:
                    out.setdefault(c, ("herb", "recipe:Herblore"))
                for p in prods:                        # the produced clean herb(s)
                    out.setdefault(p, ("herb", "recipe:Herblore"))
        if "Cooking" in xp:
            for p in prods:
                out.setdefault(p, ("food", "recipe:Cooking"))
    return out

def equipment_families():
    """{item_id: (family, signal)} — gear (combat score > 0) vs utility (equippable, <= 0).

    items_equipment.json carries MULTIPLE records per item_id (stat-variants + (beta)-page
    duplicates — the documented "items_equipment.json selection trap"). A naive
    "last record in file order wins" pick can land on an all-zero INACTIVE variant and
    misclassify a real gear piece as utility (verified live: 48 real item_ids, incl. Ahrim's
    hood/Blade of saeldor/Bow of faerdhinen, flip gear->utility under naive last-wins).
    Reuse select_bonus_record — the same canonical-record selector build_equipment_bonuses
    uses (kg_ingest.builders.equipment_bonuses) — instead of re-deriving that logic.
    """
    recs = json.load(open(os.path.join(HERE, "items_equipment.json"), encoding="utf-8"))["records"]
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    canonical_pages = {r["item_id"]: r["page_name"] for r in dict_recs}
    by_id = defaultdict(list)
    for r in recs:
        if r.get("item_id") is not None:
            by_id[r["item_id"]].append(r)
    out = {}
    for iid in sorted(by_id):
        r = select_bonus_record(by_id[iid], canonical_pages.get(iid))
        s = r["stats"]; g = lambda k: s.get(k) if isinstance(s.get(k), (int, float)) else 0
        atk = max(g("stab_attack_bonus"), g("slash_attack_bonus"), g("crush_attack_bonus"),
                  g("range_attack_bonus"), g("magic_attack_bonus"))
        dfn = g("stab_defence_bonus")+g("slash_defence_bonus")+g("crush_defence_bonus")+g("range_defence_bonus")+g("magic_defence_bonus")
        score = atk + dfn + g("strength_bonus") + g("ranged_strength_bonus") + g("magic_damage_bonus") + g("prayer_bonus")
        fam = "gear" if score > 0 else "utility"
        out[iid] = (fam, f"equipment_slot:{r['slot']}" if fam == "gear" else "equipment_utility")
    return out

def build():
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    # multimap: display names are NOT unique across item_ids (variant/minigame pages share a
    # name with the canonical item, e.g. id 11686 "Fire rune (Barbarian Assault)" has name
    # "Fire rune" same as canonical id 554) — collect ALL ids per name so every id whose name
    # matches a suffix/recipe family gets classified, not just the first-seen id (same
    # fix-class as the recommended_equipment parser's name multimap).
    name_to_ids = defaultdict(list)
    for r in dict_recs:
        name_to_ids[r["name"]].append(r["item_id"])
    for ids in name_to_ids.values():
        ids.sort()
    id_to_name = {r["item_id"]: r["name"] for r in dict_recs}
    # source_url must use the wiki PAGE title, not the generic display name (711/4729 records
    # have name != page_name, e.g. id 468 "Broken pickaxe" -> page "Broken pickaxe (bronze)").
    id_to_page = {r["item_id"]: (r.get("page_name") or r["name"]) for r in dict_recs}
    overrides = json.load(open(os.path.join(HERE, "loot_family_overrides.json"), encoding="utf-8"))["records"]
    rec_fams = recipe_families()
    eq_fams = equipment_families()

    fam_by_id = {}  # item_id -> (family, signal, source_token)
    def claim(iid, fam, sig, token):
        if iid is not None and iid not in fam_by_id:
            fam_by_id[iid] = (fam, sig, token)

    # precedence: overrides > name-suffix > recipe > equipment
    for o in overrides:
        claim(o["item_id"], o["family"], "override", o.get("source_token", id_to_name.get(o["item_id"], "")))
    for name, ids in name_to_ids.items():
        fam, sig = suffix_family(name)
        if fam:
            for iid in ids:
                claim(iid, fam, sig, name)
    for name, (fam, sig) in rec_fams.items():
        for iid in name_to_ids.get(name, []):
            claim(iid, fam, sig, name)
    for iid, (fam, sig) in eq_fams.items():
        claim(iid, fam, sig, id_to_name.get(iid, ""))

    records = [{"item_id": iid, "family": fam, "source_signal": sig,
                "source_token": token, "source_url": SRC + (id_to_page.get(iid, "").replace(" ", "_"))}
               for iid, (fam, sig, token) in fam_by_id.items()]
    records.sort(key=lambda r: r["item_id"])
    return records

def main():
    records = build()
    from collections import Counter
    dist = Counter(r["family"] for r in records)
    env = {"_provenance": {"domain": "loot_families", "license": "CC BY-NC-SA 3.0",
                "note": "derived filter-side taxonomy; precedence override>suffix>recipe>equipment",
                "record_count": len(records), "family_distribution": dict(dist)},
           "records": records}
    with open(os.path.join(HERE, "loot_families.json"), "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(records)} records; families: {dict(dist)}")

if __name__ == "__main__":
    main()
