# src/osrs_planner/lootfilter/categories.py
"""Name-pattern -> category + item hue (design §9). Gear requires a metal prefix AND a
gear-word (so ammo/essence/pouch/bones/masks are NOT mis-coloured as 'metal gear').
Patterns + hues were audited against the real item_dictionary.json (15,496 items) per
resource domain. categorize() backs the tests; the emitter iterates category_rules().

category_rules() entries are (id, display, include_patterns, hue, exclude_patterns) and
are PRIORITY-ORDERED (first emitted rule wins); potions stay LAST (their exclude list +
every earlier category claim it first)."""
from __future__ import annotations

import fnmatch

from osrs_planner.lootfilter.palette import MATERIAL_COLORS, RUNE_COLORS, GEM_COLORS, LOG_COLORS

GEAR_PIECES = ("platebody","platelegs","plateskirt","full helm","med helm","chainbody",
    "sq shield","kiteshield","sword","longsword","dagger","scimitar","mace","warhammer",
    "battleaxe","2h sword","spear","hasta","claws","boots","axe","pickaxe","halberd",
    "crossbow","defender")
_GEAR_METALS = list(MATERIAL_COLORS)  # bronze..dragon (gear naming uses 'adamant'/'rune')
# ores/bars: REAL in-game item NAME -> an ore/bar-appropriate hue (NOT the gear-metal palette,
# so Coal reads dark and Gold reads gold -- design 'hue = identity').
_COAL, _GOLDH, _SILVERH, _IRONORE = "#ff2b2b2b", "#ffd8b01a", "#ffd0d8e0", "#ffa05a3a"
ORE_NAMES = {"Copper ore":"#ffcd7f32","Tin ore":"#ffb5c0c9","Iron ore":_IRONORE,"Coal":_COAL,
    "Silver ore":_SILVERH,"Gold ore":_GOLDH,"Mithril ore":"#ff4169e1","Adamantite ore":"#ff3cb371","Runite ore":"#ff40e0d0"}
BAR_NAMES = {"Bronze bar":"#ffcd7f32","Iron bar":"#ff6b6b6b","Steel bar":"#ffb5c0c9","Silver bar":_SILVERH,
    "Gold bar":_GOLDH,"Mithril bar":"#ff4169e1","Adamantite bar":"#ff3cb371","Runite bar":"#ff40e0d0"}
CRYSTAL_SEEDS = {"Crystal seed","Crystal seedling","Crystal weapon seed","Crystal armour seed",
    "Crystal tool seed","Crystal teleport seed","Crystal chime seed","Crystal saw seed",
    "Enhanced crystal weapon seed","Enhanced crystal teleport seed"}

# --- audited resource tables (counts verified vs item_dictionary.json) ---
_AMMO_HUE = "#ff8c2f5b"   # one deep-wine identity for the whole ammo family (avoids brown/ore clashes)
_PRAYER_HUE = "#ffc7b9a0"  # prayer supplies (bones/ashes/ensouled): soft muted bone -- elegant, not stark white
_KNIVES = [f"{m} knife{s}" for m in ("Bronze","Iron","Steel","Black","Mithril","Adamant","Rune","Dragon")
           for s in ("", "(p)", "(p+)", "(p++)")]  # enumerated: bare '* knife' leaks Kitchen/Hunting/etc.
AMMO_PATTERNS = (
    ["* arrow","* arrows","* arrow(p)","* arrow(p+)","* arrow(p++)","*arrowtips","*arrowheads","*arrowhead pack","*arrow pack","*arrow (lit)"]
    + ["*bolts","*bolts (p)","*bolts (p+)","*bolts (p++)","*bolts (e)","*bolts(unf)","*bolts (unf)","*bolt tips","*bolttips","*bolt pack"]
    + ["* dart","* dart(p)","* dart(p+)","* dart(p++)","* dart (p)","*dart tip","*dart tips"]
    + ["* javelin","* javelin(p)","* javelin(p+)","* javelin(p++)","*javelin tips"]
    + _KNIVES
    + ["* thrownaxe"]
    + ["*cannonball","*cannonballs","cannon ball","cannon balls"]
)
_FOOD_HUE = "#ffe0533a"   # warm coral
FOOD_NAMES = {"Shrimps","Anchovies","Sardine","Karambwanji","Herring","Mackerel","Trout","Cod","Pike",
    "Salmon","Tuna","Cooked karambwan","Lobster","Bass","Swordfish","Monkfish","Shark","Sea turtle",
    "Manta ray","Anglerfish","Dark crab","Roe","Caviar","Rainbow fish","Cave eel","Cooked chicken",
    "Cooked meat","Tuna potato","Potato with cheese","Egg potato","Mushroom potato","Chilli potato",
    "Baked potato","Ugthanki kebab","Kebab","Bread","Pitta bread","Stew","Curry","Cake","Chocolate cake",
    "Slice of cake","Apple pie","Meat pie","Redberry pie","Garden pie","Fish pie","Admiral pie","Wild pie",
    "Summer pie","Mushroom pie","Botanical pie","Dragonfruit pie","Mud pie","Anchovy pizza","Meat pizza",
    "Pineapple pizza","Plain pizza","Peach","Strawberry","Watermelon slice","Pineapple","Jangerberries",
    "Edible seaweed","Purple sweets"}
_TELEPORT_HUE = "#ff4dd0e1"   # bright cyan-teal
TELEPORT_PATTERNS = ["* teleport", "* teleport scroll"]
_JEWELLERY_HUE = "#ffb060e0"   # light violet (charged teleport/utility jewellery)
JEWELLERY_PATTERNS = ["*bracelet(*","*bracelet (*","*necklace(*","*necklace (*","*amulet(*","*amulet (*",
    "Ring of *(*","Ring of * (*","Slayer ring (*","*pendant (*"]
_ESSENCE_HUE = "#ff7d7da0"   # muted slate-lavender
ESSENCE_NAMES = {"Rune essence","Pure essence","Daeyalt essence","Guardian essence"}
_PLANK_HUE = "#ffe0a878"   # tan
PLANK_NAMES = {"Plank","Oak plank","Teak plank","Mahogany plank"}
EXTRA_LOGS = {"Logs":"#ff7d5a32","Achey tree logs":"#ff7d5a32","Arctic pine logs":"#ff7d5a32","Bark":"#ff5a4a30"}
CUT_GEMS = {"Sapphire","Emerald","Ruby","Diamond","Dragonstone","Onyx","Zenyte","Opal","Jade","Red topaz"}
_POTION_HUE = "#ff20bfa0"   # apothecary teal
# enumerative excludes: the (1-4) dose suffix is overloaded (jewellery/food/ales/fish/tools); these drop
# exactly the 283 non-potions while keeping the 468 real potions (audited).
_POTION_EXCLUDES = ["*bracelet*","*necklace*","*amulet*","Ring of *","Slayer ring *","*pendant*",
    "Apples(*","Bananas(*","Cabbages(*","Onions(*","Oranges(*","Potatoes(*","Strawberries(*","Tomatoes(*",
    "*ale(*","*bitter(*","*stout(*","Cider(*","*mead(*","Mind bomb(*","Chef*s delight(*","Axeman*s folly(*",
    "Pot of tea *","Slayer*s respite(*","*fish (*","*bat (*","Shayzien *","*spice (*","Olive oil(*","Sacred oil(*",
    "Black mask (*","Broodoo shield (*","Enchanted lyre(*","Imp-in-a-box(*","Memoriam crystal (*","Ogre bellows (*",
    "Rod of ivandis (*","Sheep bones (*","Teleport crystal (*","Tome of experience (*","Victor*s cape (*","Void seal(*",
    "Watering can(*","Waterskin(*","Smelling salts (*","Liquid adrenaline (*","Blessed crystal scarab (*",
    "Healing vial(*","Nectar (*","Ambrosia (*","Tears of elidinis (*","Vial of tears (*"]

# Per-potion LIQUID colours -- read off the real item models one-by-one with the player (the wiki
# detailed images), so every family is its TRUE in-game liquid. Patterns stay dose-gated; ordered
# so each specific name is hit before the generic teal fallback. Disjoint by name (no order traps).
POTION_FAMILIES = [   # (display, patterns, liquid hue)
    # combat stat potions -- each its real liquid (super-strength is a near-white cream, NOT orange)
    ("Super combat", ["Super combat potion(*"], "#ff2a7a14"),                # dark green
    ("Combat potion", ["Combat potion(*","Combat mix(*"], "#ff8fbf7a"),      # pale green
    ("Super attack", ["Super attack(*","Superattack mix(*"], "#ff5a5ad8"),   # blue
    ("Attack potion", ["Attack potion(*","Attack mix(*"], "#ff5acce0"),      # cyan
    ("Super strength", ["Super strength(*","Super str. mix(*"], "#ffe9e2d6"),# pale cream
    ("Strength potion", ["Strength potion(*","Strength mix(*"], "#ffd8d85a"),# yellow
    ("Super defence", ["Super defence(*","Super def. mix(*"], "#ffd8bc5a"),  # gold
    ("Defence potion", ["Defence potion(*","Defence mix(*"], "#ff5ad85a"),   # green
    ("Goading", ["Goading potion(*"], "#ffb83018"),                          # red
    # restore -- every one is a different pink/red
    ("Super restore", ["Super restore(*","Super restore mix(*"], "#ffe05c98"),       # pink
    ("Restore potion", ["Restore potion(*","Restore mix(*"], "#ffef5a48"),           # coral
    ("Sanfew serum", ["Sanfew serum(*"], "#ffd8948a"),                              # salmon
    ("Blighted super restore", ["Blighted super restore(*"], "#ffc4507a"),          # deep rose
    # prayer
    ("Prayer potion", ["Prayer potion(*","Prayer mix(*","Prayer regeneration potion(*"], "#ff4ad8a8"),  # teal
    ("Prayer enhance", ["Prayer enhance (*","Prayer enhance (+)(*","Prayer enhance (-)(*"], "#ffa45cd0"),  # purple
    # ranging (bastion shares) / magic / battlemage
    ("Ranging", ["Ranging potion(*","Ranging mix(*","Super ranging (*","Bastion potion(*"], "#ff58b8e0"),  # blue-cyan
    ("Magic", ["Magic potion(*","Magic mix(*","Super magic potion (*"], "#fff0c8b0"),  # pale peach
    ("Battlemage", ["Battlemage potion(*"], "#fff5c030"),                              # golden yellow
    # antifire -- four purple shades
    ("Antifire", ["Antifire potion(*","Antifire mix(*"], "#ffa83cd0"),                          # vivid purple
    ("Super antifire", ["Super antifire potion(*","Super antifire mix(*"], "#ffb088d6"),        # pale lavender
    ("Extended antifire", ["Extended antifire(*","Extended antifire mix(*"], "#ff7c50e4"),      # blue-violet
    ("Extended super antifire", ["Extended super antifire(*","Extended super antifire mix(*"], "#ffc0a0e0"),  # pale lilac
    # antipoison family -- seven distinct shades
    ("Antipoison", ["Antipoison(*","Antipoison (*","Antipoison potion (*","Antipoison mix(*"], "#ff8ee838"),  # lime
    ("Superantipoison", ["Superantipoison(*","Anti-poison supermix(*"], "#fff05ca0"),           # hot pink
    ("Antidote+", ["Antidote+(*","Antidote+ mix(*"], "#ffa6a888"),                              # sage-grey
    ("Antidote++", ["Antidote++(*"], "#ffa8a850"),                                              # olive
    ("Anti-venom", ["Anti-venom(*"], "#ff5a7064"),                                              # teal-sage
    ("Anti-venom+", ["Anti-venom+(*","Extended anti-venom+(*"], "#ff9a8088"),                   # mauve
    ("Relicym's balm", ["Relicym's balm(*","Relicym's mix(*"], "#ffd8a878"),                    # tan
    # stamina / energy
    ("Stamina", ["Stamina potion(*","Stamina mix(*","Extended stamina potion(*"], "#ffc89868"), # tan
    ("Energy", ["Energy potion(*","Energy mix(*"], "#ffd08a90"),                                # dusty rose
    ("Super energy", ["Super energy(*","Super energy mix(*","Extreme energy potion(*"], "#ffee74c0"),  # pink
    # brews / overload / elder
    ("Saradomin brew", ["Saradomin brew(*"], "#ffe8e840"),                                      # lemon yellow
    ("Overloads", ["Overload(*","Overload (*","Blighted overload (*"], "#ff2e2826"),            # near-black
    ("Elder", ["Elder (+)(*","Elder (-)(*","Elder potion (*"], "#ffa86058"),                    # terracotta
    # skill potions
    ("Agility", ["Agility potion(*","Agility mix(*"], "#ff9aae3c"),                             # olive
    ("Fishing", ["Fishing potion(*","Fishing mix(*","Super fishing potion(*"], "#ff807a76"),    # grey
    ("Hunter", ["Hunter potion(*","Hunting mix(*","Super hunter potion(*"], "#ff2e8888"),       # teal
]

# Divine potions = the base potion's liquid + crystal dust, so we colour them their BASE hue and
# add an icy-cyan border to mark them as divine (consumes the border-override in emit_categories).
_DIVINE_BORDER = "#ffaee8ff"   # crystal-dust icy cyan
DIVINE_POTIONS = [   # (display, patterns, BASE potion hue)
    ("Divine super combat", ["Divine super combat potion(*"], "#ff2a7a14"),  # super combat green
    ("Divine ranging", ["Divine ranging potion(*"], "#ff58b8e0"),            # ranging blue-cyan
    ("Divine magic", ["Divine magic potion(*"], "#fff0c8b0"),                # magic peach
    ("Divine bastion", ["Divine bastion potion(*"], "#ff58b8e0"),            # bastion (ranging-side)
    ("Divine battlemage", ["Divine battlemage potion(*"], "#fff5c030"),      # battlemage gold
]

def _any(name: str, patterns) -> bool:
    nl = name.lower()
    return any(fnmatch.fnmatch(nl, p.lower()) for p in patterns)

def categorize(name: str):
    n = name.strip()
    nl = n.lower()
    if n in BAR_NAMES: return {"id": "bars", "hue": BAR_NAMES[n]}
    if n in ORE_NAMES: return {"id": "ores", "hue": ORE_NAMES[n]}
    if "thrownaxe" not in nl:  # ranged ammo, not melee 'axe' gear
        for metal in _GEAR_METALS:
            if nl.startswith(metal + " ") and any(w in nl for w in GEAR_PIECES):
                return {"id": "gear", "hue": MATERIAL_COLORS[metal]}
    if nl.endswith(" rune"):
        elem = nl[:-5]
        if elem in RUNE_COLORS: return {"id": "runes", "hue": RUNE_COLORS[elem]}
    if _any(n, AMMO_PATTERNS): return {"id": "ammo", "hue": _AMMO_HUE}
    if nl.startswith("uncut "):
        gem = nl[6:]
        if gem in GEM_COLORS: return {"id": "gems", "hue": GEM_COLORS[gem]}
    if n in CUT_GEMS: return {"id": "gems", "hue": GEM_COLORS[nl]}
    if n in ESSENCE_NAMES: return {"id": "essence", "hue": _ESSENCE_HUE}
    if nl.startswith("grimy "): return {"id": "herbs", "hue": "#ff2e8b57"}
    if nl.endswith(" logs"):
        tree = nl[:-5]
        if tree in LOG_COLORS: return {"id": "logs", "hue": LOG_COLORS[tree]}
    if n in EXTRA_LOGS: return {"id": "logs", "hue": EXTRA_LOGS[n]}
    if n in PLANK_NAMES: return {"id": "planks", "hue": _PLANK_HUE}
    if n in FOOD_NAMES: return {"id": "food", "hue": _FOOD_HUE}
    if (nl.endswith(" seed") or nl.endswith(" seedling")) and n not in CRYSTAL_SEEDS:
        return {"id": "seeds", "hue": "#ff00e024"}
    if (nl.endswith(" bones") or nl.endswith(" ashes") or nl in ("bones", "ashes")
            or (nl.startswith("ensouled ") and nl.endswith(" head"))):
        return {"id": "bones", "hue": _PRAYER_HUE}
    if _any(n, TELEPORT_PATTERNS): return {"id": "teleports", "hue": _TELEPORT_HUE}
    if _any(n, JEWELLERY_PATTERNS): return {"id": "charged_jewellery", "hue": _JEWELLERY_HUE}
    if nl.endswith(("(1)", "(2)", "(3)", "(4)")) and not _any(n, _POTION_EXCLUDES):
        for _disp, pats, base in DIVINE_POTIONS:      # divine -> its base liquid (icy border added in emit)
            if _any(n, pats):
                return {"id": "potions", "hue": base}
        for _disp, pats, hue in POTION_FAMILIES:      # colour by liquid; teal fallback
            if _any(n, pats):
                return {"id": "potions", "hue": hue}
        return {"id": "potions", "hue": _POTION_HUE}
    return None

def category_rules():
    """(id, display, include_patterns, hue, exclude_patterns); hue=None -> per-name hue (ores/bars)."""
    out = []
    for metal, hue in MATERIAL_COLORS.items():
        out.append(("gear", f"{metal.title()} gear", [f"{metal.title()} {p}" for p in GEAR_PIECES], hue, []))
    out.append(("ores", "Ores", list(ORE_NAMES), None, []))
    out.append(("bars", "Bars", list(BAR_NAMES), None, []))
    for elem, hue in RUNE_COLORS.items():
        out.append(("runes", f"{elem.title()} rune", [f"{elem.title()} rune"], hue, []))
    for gem, hue in GEM_COLORS.items():
        out.append(("gems", f"Uncut {gem}", [f"Uncut {gem}"], hue, []))     # uncut
        out.append(("gems", gem.capitalize(), [gem.capitalize()], hue, []))  # cut
    out.append(("essence", "Essence", sorted(ESSENCE_NAMES), _ESSENCE_HUE, []))
    out.append(("ammo", "Ammo", AMMO_PATTERNS, _AMMO_HUE, []))
    for tree, hue in LOG_COLORS.items():
        out.append(("logs", f"{tree.title()} logs", [f"{tree.title()} logs"], hue, []))
    for nm, hue in EXTRA_LOGS.items():
        out.append(("logs", nm, [nm], hue, []))
    out.append(("planks", "Planks", sorted(PLANK_NAMES), _PLANK_HUE, []))
    out.append(("herbs", "Herbs", ["Grimy *"], "#ff2e8b57", []))
    out.append(("seeds", "Seeds", ["* seed", "* seedling"], "#ff00e024", sorted(CRYSTAL_SEEDS)))
    out.append(("bones", "Prayer supplies (bones, ashes, ensouled)", ["* bones", "* ashes", "Bones", "Ashes", "Ensouled * head"], _PRAYER_HUE, []))
    out.append(("food", "Food", sorted(FOOD_NAMES), _FOOD_HUE, []))
    out.append(("teleports", "Teleports", TELEPORT_PATTERNS, _TELEPORT_HUE, []))
    out.append(("charged_jewellery", "Charged jewellery", JEWELLERY_PATTERNS, _JEWELLERY_HUE, []))
    for disp, pats, base in DIVINE_POTIONS:           # divine = base liquid + icy border (6-tuple)
        out.append(("potions", disp, pats, base, [], _DIVINE_BORDER))
    for disp, pats, hue in POTION_FAMILIES:           # per-liquid families...
        out.append(("potions", disp, pats, hue, []))
    out.append(("potions", "Potions", ["*(1)", "*(2)", "*(3)", "*(4)"], _POTION_HUE, _POTION_EXCLUDES))  # ...then teal fallback
    return out
