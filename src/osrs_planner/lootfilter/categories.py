# src/osrs_planner/lootfilter/categories.py
"""Name-pattern -> category + item hue (design §9). Gear requires a metal prefix AND
a gear-word (so ammo/essence/pouch/bones/masks are NOT mis-coloured as 'metal gear').
Crystal/weapon/armour seeds excluded from seeds. categorize() backs the tests; the
emitter iterates category_rules() (Task 5)."""
from __future__ import annotations

from osrs_planner.lootfilter.palette import MATERIAL_COLORS, RUNE_COLORS, GEM_COLORS, LOG_COLORS

GEAR_PIECES = ("platebody","platelegs","plateskirt","full helm","med helm","chainbody",
    "sq shield","kiteshield","sword","longsword","dagger","scimitar","mace","warhammer",
    "battleaxe","2h sword","spear","hasta","claws","boots","axe","pickaxe","halberd",
    "crossbow","defender")
_GEAR_METALS = list(MATERIAL_COLORS)  # bronze..dragon (gear naming uses 'adamant'/'rune')
# ores/bars: REAL in-game item NAME -> an ore/bar-appropriate hue (NOT borrowed from the
# gear-metal palette, so Coal reads dark and Gold reads gold -- design 'hue = identity').
_COAL, _GOLDH, _SILVERH, _IRONORE = "#ff2b2b2b", "#ffd8b01a", "#ffd0d8e0", "#ffa05a3a"
ORE_NAMES = {"Copper ore":"#ffcd7f32","Tin ore":"#ffb5c0c9","Iron ore":_IRONORE,"Coal":_COAL,
    "Silver ore":_SILVERH,"Gold ore":_GOLDH,"Mithril ore":"#ff4169e1","Adamantite ore":"#ff3cb371","Runite ore":"#ff40e0d0"}
BAR_NAMES = {"Bronze bar":"#ffcd7f32","Iron bar":"#ff6b6b6b","Steel bar":"#ffb5c0c9","Silver bar":_SILVERH,
    "Gold bar":_GOLDH,"Mithril bar":"#ff4169e1","Adamantite bar":"#ff3cb371","Runite bar":"#ff40e0d0"}
CRYSTAL_SEEDS = {"Crystal seed","Crystal seedling","Crystal weapon seed","Crystal armour seed",
    "Crystal tool seed","Crystal teleport seed","Crystal chime seed","Crystal saw seed",
    "Enhanced crystal weapon seed","Enhanced crystal teleport seed"}

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
    if nl.startswith("grimy "):
        return {"id": "herbs", "hue": "#ff2e8b57"}
    if nl.startswith("uncut "):
        gem = nl[6:]
        if gem in GEM_COLORS: return {"id": "gems", "hue": GEM_COLORS[gem]}
    if nl.endswith(" logs"):
        tree = nl[:-5]
        if tree in LOG_COLORS:                 # only the trees the emitter actually ships
            return {"id": "logs", "hue": LOG_COLORS[tree]}
    if (nl.endswith(" seed") or nl.endswith(" seedling")) and n not in CRYSTAL_SEEDS:
        return {"id": "seeds", "hue": "#ff00e024"}
    if nl.endswith(" bones") or nl.endswith(" ashes"):
        return {"id": "bones", "hue": "#ffe8e0d0"}
    return None

def category_rules():
    out = []
    for metal, hue in MATERIAL_COLORS.items():
        out.append(("gear", f"{metal.title()} gear", [f"{metal.title()} {p}" for p in GEAR_PIECES], hue))
    out.append(("ores", "Ores", list(ORE_NAMES), None))   # per-name hue resolved in emit (mixed metals)
    out.append(("bars", "Bars", list(BAR_NAMES), None))
    for elem, hue in RUNE_COLORS.items():
        out.append(("runes", f"{elem.title()} rune", [f"{elem.title()} rune"], hue))
    for gem, hue in GEM_COLORS.items():
        out.append(("gems", f"Uncut {gem}", [f"Uncut {gem}"], hue))
    for tree, hue in LOG_COLORS.items():
        out.append(("logs", f"{tree.title()} logs", [f"{tree.title()} logs"], hue))
    out.append(("herbs", "Herbs", ["Grimy *"], "#ff2e8b57"))
    out.append(("seeds", "Seeds", ["* seed", "* seedling"], "#ff00e024"))
    out.append(("bones", "Bones & ashes", ["* bones", "* ashes"], "#ffe8e0d0"))
    return out
