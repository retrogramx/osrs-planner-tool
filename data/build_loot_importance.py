#!/usr/bin/env python3
"""EDITORIAL: hand-ranked ironman base importance per resource item -> data/loot_importance.json.
Judgment, not a wiki fact (owner-reviewed). Tier tables below ARE the ranking; a per-family default
catches the long tail ("rank everything, no value fallback"). Re-run must be byte-stable."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
from osrs_planner.lootfilter import categories as C

def load(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))["records"]

DICT = load("item_dictionary.json")
NAME2ID = {}                          # prefer canonical page for a name
for r in DICT:
    if r["name"] not in NAME2ID or r.get("is_canonical"):
        NAME2ID[r["name"]] = r["item_id"]
ID2NAME = {r["item_id"]: r["name"] for r in DICT}
FAMS = load("loot_families.json")     # item_id -> family (authority for herb/rune/ore/bar/log/seed/bones/ammo/food)

# --- tier resolvers (name -> (base_tier, rationale)); return None to fall to the family default ---

def herb_tier(n):
    key = n.lower().replace("grimy ", "")
    T = {"ranarr weed": ("A", "prayer/super-restore backbone"),
         "snapdragon": ("A", "super restore/sara brew"), "torstol": ("A", "super combat/anti-venom+"),
         "toadflax": ("B", "sara brew/anti-venom"), "avantoe": ("B", "fishing/hunter/extended"),
         "kwuarm": ("B", "super strength/weapon poison"), "huasca": ("B", "herblore secondary base"),
         "cadantine": ("C", "super defence/restore"), "lantadyme": ("C", "antifire/magic"),
         "dwarf weed": ("C", "ranging"), "irit leaf": ("D", "super attack/antipoison"),
         "harralander": ("D", "energy/combat/restore"), "marrentill": ("E", "antipoison, low"),
         "tarromin": ("E", "strength/serum, low"), "guam leaf": ("E", "attack, trivial")}
    return T.get(key)

def rune_tier(n):
    elem = n.lower().replace(" rune", "")
    T = {**{e: ("A", "alch/high-tier casting/RC target") for e in ("nature", "law", "death", "blood", "soul", "wrath")},
         **{e: ("B", "utility casting") for e in ("cosmic", "chaos", "astral")},
         **{e: ("C", "combo/utility") for e in ("mind", "body", "mist", "dust", "mud", "lava", "smoke", "steam")},
         **{e: ("D", "elemental staple, cheap in bulk") for e in ("fire", "water", "air", "earth")}}
    return T.get(elem)

_METAL = {"ore": {"Runite": "A", "Adamantite": "B", "Mithril": "C", "Coal": "C", "Gold": "C", "Iron": "D", "Silver": "D", "Copper": "E", "Tin": "E"},
          "bar": {"Runite": "A", "Adamantite": "B", "Mithril": "C", "Steel": "C", "Gold": "C", "Iron": "D", "Silver": "D", "Bronze": "E"}}
def ore_tier(n):
    for k, t in _METAL["ore"].items():
        if n.startswith(k):
            return (t, f"{k.lower()} ore — smithing/grind gate")
    return None
def bar_tier(n):
    for k, t in _METAL["bar"].items():
        if n.startswith(k):
            return (t, f"{k.lower()} bar — smithing feedstock")
    return None

def log_tier(n):
    T = {"Magic logs": "A", "Redwood logs": "A", "Yew logs": "B", "Maple logs": "C", "Mahogany logs": "C",
         "Teak logs": "C", "Willow logs": "D"}
    if n in T:
        return (T[n], f"{n.lower()} — firemaking/fletching/construction")
    return None  # Logs/Oak/Achey/Arctic pine/Bark -> default E

def essence_tier(n):
    T = {"Pure essence": ("A", "runecrafting fuel, hoarded"), "Daeyalt essence": ("A", "RC xp premium"),
         "Guardian essence": ("B", "GOTR"), "Rune essence": ("C", "low-level RC")}
    return T.get(n)

_GEM_CUT = {"Zenyte": "A", "Onyx": "A", "Dragonstone": "A", "Diamond": "B", "Ruby": "C",
            "Emerald": "D", "Sapphire": "D", "Opal": "E", "Jade": "E", "Red topaz": "E"}
def gem_tier(n):
    uncut = n.startswith("Uncut ")
    base = (n[len("Uncut "):] if uncut else n).capitalize()   # "sapphire"->"Sapphire", matches _GEM_CUT keys
    if base in _GEM_CUT:
        t = _GEM_CUT[base]
        if uncut:                                            # uncut one tier louder (grind gate = cutting)
            from osrs_planner.lootfilter.palette import GRADE_ORDER
            t = GRADE_ORDER[max(0, GRADE_ORDER.index(t) - 1)]
        return (t, f"{base.lower()} gem — crafting/bolt tips")
    return None

def plank_tier(n):
    T = {"Mahogany plank": ("A", "high construction xp"), "Teak plank": ("B", "construction staple"),
         "Oak plank": ("C", "early construction"), "Plank": ("E", "trivial")}
    return T.get(n)

def bones_tier(n):
    nl = n.lower()
    T = {"superior dragon bones": "A", "dagannoth bones": "A", "ourg bones": "A", "hydra bones": "A",
         "frost dragon bones": "A", "dragon bones": "B", "wyvern bones": "B", "lava dragon bones": "B",
         "wyrm bones": "B", "drake bones": "B", "fayrg bones": "B", "raurg bones": "B",
         "big bones": "C", "babydragon bones": "C", "jogre bones": "C", "zogre bones": "C"}
    if nl in T:
        return (T[nl], f"{nl} — prayer xp per bone")
    if nl == "bones":
        return ("D", "basic prayer xp")
    if nl.endswith(" ashes"):
        A = {"infernal ashes": "A", "malicious ashes": "B", "abyssal ashes": "C",
             "fiendish ashes": "D", "vile ashes": "E"}
        return (A.get(nl, "D"), "ashes — prayer xp")
    if nl.startswith("ensouled ") and nl.endswith(" head"):
        return ("C", "arceuus reanimation xp")
    return None  # other bat/wolf/monkey bones -> default D

def ammo_tier(n):
    nl = n.lower()
    demote = " tip" in nl or "tips" in nl                # tips one tier below finished ammo
    for metal, t in (("dragon", "A"), ("rune", "B"), ("amethyst", "B"), ("adamant", "C"),
                     ("mithril", "D"), ("iron", "E"), ("steel", "E"), ("black", "E"), ("bronze", "E")):
        if nl.startswith(metal):
            from osrs_planner.lootfilter.palette import GRADE_ORDER
            gi = GRADE_ORDER.index(t)
            if demote:
                gi = min(len(GRADE_ORDER) - 1, gi + 1)
            return (GRADE_ORDER[gi], f"{metal} ammo{' tips' if demote else ''}")
    if "cannonball" in nl:
        return ("B", "cannon fodder, iron staple")
    return None

_FOOD_SUPPLY = {"Anglerfish": "A", "Manta ray": "A", "Dark crab": "A", "Cooked karambwan": "A",
                "Shark": "B", "Sea turtle": "B", "Monkfish": "B", "Tuna potato": "B",
                "Swordfish": "C", "Lobster": "C", "Bass": "C"}
def food_tier(n):
    if n in _FOOD_SUPPLY:
        return (_FOOD_SUPPLY[n], "combat supply — don't lose these")
    return None  # everything else -> default E

_DEFAULT = {"herb": ("E", "low-tier herb"), "rune": ("D", "elemental/utility rune"),
            "ore": ("E", "low ore"), "bar": ("E", "low bar"), "log": ("E", "low log"),
            "seed": ("E", "allotment/common seed"), "bones": ("D", "common bones"),
            "ammo": ("E", "low-tier ammo"), "food": ("E", "trivial food"),
            "essence": ("C", "essence"), "gem": ("E", "semi-precious gem"), "plank": ("E", "plank")}
_RESOLVER = {"herb": herb_tier, "rune": rune_tier, "ore": ore_tier, "bar": bar_tier, "log": log_tier,
             "seed": None, "bones": bones_tier, "ammo": ammo_tier, "food": food_tier,
             "essence": essence_tier, "gem": gem_tier, "plank": plank_tier}

def seed_tier(n):
    T = {"Ranarr seed": "A", "Snapdragon seed": "A", "Torstol seed": "A", "Magic seed": "A", "Yew seed": "B",
         "Palm tree seed": "B", "Dragonfruit tree seed": "B", "Toadflax seed": "B", "Avantoe seed": "B",
         "Kwuarm seed": "C", "Cadantine seed": "C", "Lantadyme seed": "C", "Dwarf weed seed": "C",
         "Maple seed": "C", "Willow seed": "D", "Oak seed": "D", "Irit seed": "D", "Harralander seed": "D"}
    if n in T:
        return (T[n], f"{n.lower()} — farming/herblore pipeline")
    return None
_RESOLVER["seed"] = seed_tier

def resolve(item_id, family):
    n = ID2NAME.get(item_id, "")
    r = _RESOLVER[family](n) if _RESOLVER.get(family) else None
    if r is None:
        r = _DEFAULT[family]
    return {"item_id": item_id, "name": n, "family": family, "base_tier": r[0], "rationale": r[1]}

def main():
    records, seen = [], set()
    # 1) loot_families families with id-lists ready
    RANKED = {"herb", "rune", "ore", "bar", "log", "seed", "bones", "ammo", "food"}
    for r in FAMS:
        if r["family"] in RANKED and r["item_id"] not in seen and r["item_id"] in ID2NAME:
            records.append(resolve(r["item_id"], r["family"])); seen.add(r["item_id"])
    # 2) categories-sourced families (name sets -> ids)
    def add_names(names, fam):
        for nm in names:
            iid = NAME2ID.get(nm)
            if iid is not None and iid not in seen:
                records.append(resolve(iid, fam)); seen.add(iid)
    add_names(sorted(C.ESSENCE_NAMES), "essence")
    add_names(sorted(C.PLANK_NAMES), "plank")
    gem_names = sorted(C.CUT_GEMS) + sorted("Uncut " + g.lower() for g in C.CUT_GEMS)
    add_names(gem_names, "gem")
    # loot_families.json is missing "Coal" from the ore family (real-data gap: every other
    # ORE_NAMES/BAR_NAMES member is already tagged there). categories.py's name-keyed ore/bar
    # dicts are the completeness backstop, same pattern as essence/plank/gem above.
    add_names(sorted(C.ORE_NAMES), "ore")
    add_names(sorted(C.BAR_NAMES), "bar")
    records.sort(key=lambda r: (r["family"], r["item_id"]))
    out = {"_provenance": {"domain": "loot_importance", "kind": "editorial",
        "note": "Hand-ranked ironman base importance per resource item. Judgment, not a wiki fact; owner-reviewed. "
                "base_tier in {SS,S,A,B,C,D,E}. Quantity escalation (×10/grade) applied at emit time, NOT stored here."},
        "records": records}
    with open(os.path.join(HERE, "loot_importance.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"loot_importance: {len(records)} items ranked")

if __name__ == "__main__":
    main()
