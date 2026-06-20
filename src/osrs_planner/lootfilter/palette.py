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

def _lum(hue: str) -> float:
    """Perceived luminance of a #aarrggbb colour (0-255), for auto-contrast text/border."""
    return 0.299 * int(hue[3:5], 16) + 0.587 * int(hue[5:7], 16) + 0.114 * int(hue[7:9], 16)

def _text_on(bg: str) -> str:
    return "#ff141414" if _lum(bg) > 135 else "#fff5f5f5"   # dark text on a light panel, near-white on dark

def _border_on(bg: str) -> str:
    return "#ff181818" if _lum(bg) > 135 else "#ffffffff"   # crisp contrasting border

def style_for(hue: str, grade: str, border: str | None = None) -> dict[str, str]:
    """SOLID vivid coloured panel for identity/valuable items (SS..C); cheap uncategorised loot
    (D, E) is plain/faded OUTLINED TEXT, no panel -> the screen stays calm where it doesn't matter.
    Categories floor at C (always a vivid panel). Emphasis: +sound (A) -> +loot beam (S/SS).
    `border` overrides the auto-contrast border (used to mark divine potions with an icy edge)."""
    emph = next(e for g, _m, e in VALUE_GRADES if g == grade)
    if grade in ("D", "E"):                       # low value: just text, no panel -> subtle shadow for readability
        tc = ("#9e" if grade == "E" else "#ff") + hue[3:]
        s = {"textColor": tc, "textAccent": "1", "fontType": "1"}
        if grade == "E":
            s["menuSort"] = "-10000"
        return s
    s = {"backgroundColor": hue, "borderColor": border or _border_on(hue), "textColor": _text_on(hue),
         "fontType": str(emph["fontType"]), "textAccent": "3", "icon": "CurrentItem()"}  # 3 = none: crisp on the solid panel
    if grade in ("SS", "S", "A"):                  # high: + drop sound
        s["sound"] = "3925"
    if grade in ("SS", "S"):                       # top: + loot beam
        s["showLootbeam"] = "true"; s["lootbeamColor"] = hue
    return s

# Value-tier colours for UNCATEGORISED loot (the fallback ladder) so it reads as a colour
# gradient by value instead of monochrome white/grey (fixes the "monochromatic" feedback).
FALLBACK_HUES = {
    "SS": "#ffff2b2b",  # red
    "S":  "#ffff45d6",  # magenta
    "A":  "#ffff9a1f",  # orange
    "B":  "#ff27c2ff",  # cyan
    "C":  "#ff52e052",  # green
    "D":  "#ff6f7780",  # muted slate (was near-white; common loot reads dark + faint, not busy white)
    "E":  "#ff8c8c8c",  # grey
}

# Coins (id 995) + platinum tokens (id 13204): their OWN gold identity, the gold DARKENING as the
# stack value climbs (lightest <100 -> deepest >=100m) so you read the magnitude at a glance.
COIN_TIERS = [   # (min_value, gold_shade) — emitted high-threshold-first (terminal first match)
    (100_000_000, "#ff4a3604"),  # >=100m  deepest amber
    (10_000_000,  "#ff63490a"),  # >=10m
    (1_000_000,   "#ff7c5d10"),  # >=1m
    (100_000,     "#ff967216"),  # >=100k
    (10_000,      "#ffb0881c"),  # >=10k
    (1_000,       "#ffc99e22"),  # >=1k
    (100,         "#ffddb22c"),  # >=100
    (0,           "#ffe9c63e"),  # <100   clear gold (not washed pale)
]

MATERIAL_COLORS = {
    "bronze": "#ffcd7f32", "iron": "#ff6b6b6b", "steel": "#ffb5c0c9", "black": "#ff3b3b3b",
    "mithril": "#ff4169e1", "adamant": "#ff3cb371", "rune": "#ff40e0d0", "dragon": "#ffc83232",
}
RUNE_COLORS = {
    "fire": "#ffff4500", "water": "#ff1e90ff", "air": "#ffe6e6e6", "earth": "#ff8b5a2b",
    "mind": "#ffd05050", "body": "#ff8090a0", "cosmic": "#ff7060d0", "chaos": "#ffa04020",
    "nature": "#ff2e8b57", "law": "#ffd0c060", "death": "#ffd0d0d0", "blood": "#ffb01030",
    "soul": "#ffc0c0e0", "astral": "#ff60a0d0", "wrath": "#ffd03020",
    # combination runes -> one amethyst identity (distinct from every base rune)
    "mist": "#ff9b59b6", "dust": "#ff9b59b6", "mud": "#ff9b59b6",
    "lava": "#ff9b59b6", "smoke": "#ff9b59b6", "steam": "#ff9b59b6",
}
GEM_COLORS = {
    "sapphire": "#ff1e60ff", "emerald": "#ff30c030", "ruby": "#ffd02030", "diamond": "#ffe0f0ff",
    "dragonstone": "#ffc030a0", "onyx": "#ff402030", "zenyte": "#ffe06010",
    # semi-precious -> a shared pale mint
    "opal": "#ff8fd6c0", "jade": "#ff8fd6c0", "red topaz": "#ff8fd6c0",
}
LOG_COLORS = {
    "oak": "#ffb8895a", "willow": "#ff8a9a5a", "maple": "#ffc07840", "yew": "#ff6a6a3a",
    "magic": "#ff5090d0", "redwood": "#ffb03020", "teak": "#ff9c6b3f", "mahogany": "#ff7a3b25",
}
