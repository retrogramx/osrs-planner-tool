# src/osrs_planner/lootfilter/palette.py
"""Visual language (design §6/§7): HUE = material/type colour, EMPHASIS = value grade.
style_for renders a grade's emphasis IN an item's hue. 8-hex ARGB. Authored ourselves."""
from __future__ import annotations

VALUE_GRADES = [
    ("SS", 10_000_000, {"beam": True,  "sound": True,  "border": True,  "fontType": 3, "accent": 3, "bg_alpha": "ff"}),
    ("S",   1_000_000, {"beam": True,  "sound": True,  "border": True,  "fontType": 3, "accent": 3, "bg_alpha": "ff"}),
    ("A",     100_000, {"beam": False, "sound": True,  "border": False, "fontType": 2, "accent": 3, "bg_alpha": "cc"}),
    ("B",      10_000, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 3, "bg_alpha": "99"}),
    ("C",       1_000, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 3, "bg_alpha": "33"}),
    ("D",         100, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 1, "bg_alpha": "00"}),
    ("E",           0, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 1, "bg_alpha": "00"}),
]

_GOLD, _BRONZE = "#ffd8b01a", "#ffbc6025"
TROPHY_GRADES = [
    ("SS", 10_000_000, {"hue": "#ffff0000", "beam": True, "sound": True, "fontType": 3, "accent": 3}),
    ("S",   1_000_000, {"hue": _GOLD,       "beam": True, "sound": True, "fontType": 3, "accent": 3}),
    ("A",     100_000, {"hue": _BRONZE,     "beam": True, "sound": True, "fontType": 2, "accent": 3}),
    ("B",      10_000, {"hue": _BRONZE,     "beam": True, "sound": True, "fontType": 2, "accent": 3}),
    ("C",           0, {"hue": _BRONZE,     "beam": True, "sound": True, "fontType": 1, "accent": 3}),
]

def style_for(hue: str, grade: str) -> dict[str, str]:
    emph = next(e for g, _m, e in VALUE_GRADES if g == grade)
    s = {"textColor": hue, "fontType": str(emph["fontType"]), "textAccent": str(emph["accent"])}
    if grade == "E":
        s["textColor"] = "#66" + hue[3:]; s["menuSort"] = "-10000"
    if emph["bg_alpha"] not in ("00", "ff"):
        s["backgroundColor"] = "#" + emph["bg_alpha"] + hue[3:]
    if emph["border"]:
        s["borderColor"] = hue; s["backgroundColor"] = "#ffffffff"
    if emph["beam"]:
        s["showLootbeam"] = "true"; s["lootbeamColor"] = hue
    if emph["sound"]:
        s["sound"] = "3925"
    return s

MATERIAL_COLORS = {
    "bronze": "#ffcd7f32", "iron": "#ff6b6b6b", "steel": "#ffb5c0c9", "black": "#ff3b3b3b",
    "mithril": "#ff4169e1", "adamant": "#ff3cb371", "rune": "#ff40e0d0", "dragon": "#ffc83232",
}
RUNE_COLORS = {
    "fire": "#ffff4500", "water": "#ff1e90ff", "air": "#ffe6e6e6", "earth": "#ff8b5a2b",
    "mind": "#ffd05050", "body": "#ff8090a0", "cosmic": "#ff7060d0", "chaos": "#ffa04020",
    "nature": "#ff2e8b57", "law": "#ffd0c060", "death": "#ffd0d0d0", "blood": "#ffb01030",
    "soul": "#ffc0c0e0", "astral": "#ff60a0d0", "wrath": "#ffd03020",
}
GEM_COLORS = {
    "sapphire": "#ff1e60ff", "emerald": "#ff30c030", "ruby": "#ffd02030", "diamond": "#ffe0f0ff",
    "dragonstone": "#ffc030a0", "onyx": "#ff402030", "zenyte": "#ffe06010",
}
LOG_COLORS = {
    "oak": "#ffb8895a", "willow": "#ff8a9a5a", "maple": "#ffc07840", "yew": "#ff6a6a3a",
    "magic": "#ff5090d0", "redwood": "#ffb03020", "teak": "#ff9c6b3f", "mahogany": "#ff7a3b25",
}
