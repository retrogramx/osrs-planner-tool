# src/osrs_planner/lootfilter/emit.py
"""rs2f emitter (design §4/§5). Bools/ints bare, colours quoted. Every styling rule
is iron-gated via the IRONMAN macro. HIDE_FLOOR default 0 hides nothing."""
from __future__ import annotations

import re

from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for, FALLBACK_HUES, _text_on, _border_on, COIN_TIERS
from osrs_planner.lootfilter.palette import TROPHY_GRADES  # add to imports
from osrs_planner.lootfilter.categories import category_rules, ORE_NAMES, BAR_NAMES  # add

IRONMAN = "IRONMAN"
_BARE = {"true", "false"}

def style_str(style: dict) -> str:
    parts = []
    for k, v in style.items():
        v = str(v)
        # bools/ints + icon function-expressions (e.g. CurrentItem()) are bare; colours/strings quoted
        bare = v in _BARE or v.lstrip("-").isdigit() or k == "icon"
        parts.append(f"{k} = {v};" if bare else f'{k} = "{v}";')
    return "{ " + " ".join(parts) + " }"

def emit_rule(conds: str, style: dict, terminal: bool = True) -> str:
    return f"{'rule' if terminal else 'apply'} ({conds}) {style_str(style)}"

def _macro_body(style: dict) -> str:
    """A style dict as a `#define` macro body: 'k = v;' pairs WITHOUT the wrapping braces."""
    return style_str(style)[2:-2].strip()   # reuse style_str, drop the '{ ' ... ' }'

def emit_style_input(module_id: str, label: str, group: str, macro: str, conds: str,
                     style: dict, terminal: bool = True) -> str:
    """A FilterScape-EDITABLE style: a `type: style` input (colour picker) + a `#define` holding its
    default + a rule that applies the macro. Editing the picker rewrites the #define on export."""
    decl = f"/*@ define:input:{module_id}\ntype: style\nlabel: {label}\ngroup: {group}\n*/"
    define = f"#define {macro} {_macro_body(style)}"
    rule = f"{'rule' if terminal else 'apply'} ({conds}) {{ {macro} }}"
    return f"{decl}\n{define}\n{rule}"

def emit_meta(name: str, desc: str) -> str:
    return f'meta {{\n    name = "{name}";\n    description = "{desc}";\n}}\n'

def emit_module(module_id: str, name: str, body: str, subtitle: str = "", description: str = "") -> str:
    # FilterScape/loot-filters-ui require name + subtitle + description on EVERY module (the plugin
    # is lenient, the web customizer isn't -- a missing field makes its importer build a bad module).
    return (f"/*@ define:module:{module_id}\nname: {name}\n"
            f"subtitle: {subtitle or name}\n"
            f"description: |\n    {description or name}\n*/\n{body}\n")

def emit_preamble() -> str:
    # Deliberately EMPTY: a FilterScape filter must START with a module declaration -- any content
    # between meta{} and the first module (e.g. an orphaned #define) makes its parser discard the
    # whole filter. The IRONMAN macro therefore lives at the top of the settings module instead.
    return ""

def _human(n: int) -> str:
    for div, suf in ((1_000_000, "m"), (1_000, "k")):
        if n >= div:
            return f"{n // div}{suf}"
    return str(n)

def emit_coins() -> str:
    """Coins + platinum tokens -> their own gold ladder, darkening as the stack value climbs.
    Each tier is an editable colour picker (grouped under 'Coins')."""
    idl = "id:[995, 13204]"
    lines = []
    for minv, gold in COIN_TIERS:
        label = "Coins (<100)" if minv == 0 else f"Coins (>={_human(minv)})"
        style = {"backgroundColor": gold, "borderColor": _border_on(gold), "textColor": _text_on(gold),
                 "fontType": "1", "textAccent": "3", "icon": "CurrentItem()"}
        lines.append(emit_style_input("coins", label, "Coins", f"COIN_{minv}",
                                      f"{IRONMAN} && {idl} && value:>={minv}", style))
    return emit_module("coins", "Coins", "\n".join(lines), "Gold, darkening by stack value")

def emit_fallback() -> str:
    lines = [emit_rule(f"{IRONMAN} && value:<HIDE_FLOOR", {"hidden": "true"})]  # default 0 -> hides nothing (not editable)
    for grade, minv, _e in VALUE_GRADES:
        label = f"Value {grade} (any)" if minv == 0 else f"Value {grade} (>={_human(minv)})"
        lines.append(emit_style_input("fallback", label, "Value tiers", f"FB_{grade}",
                                      f"{IRONMAN} && value:>={minv}", style_for(FALLBACK_HUES[grade], grade)))
    return emit_module("fallback", "Value fallback (SS->E)", "\n".join(lines), "Uncategorised loot, coloured by value")

def _id_list(ids) -> str:
    return "id:[" + ", ".join(str(i) for i in sorted(set(ids))) + "]"

def _trophy_style(emph: dict) -> dict:
    return {"textColor": "#ffffffff", "backgroundColor": "#ff" + emph["hue"][3:], "borderColor": emph["hue"],
            "fontType": str(emph["fontType"]), "textAccent": str(emph["accent"]),
            "showLootbeam": "true", "lootbeamColor": emph["hue"], "sound": "3930", "icon": "CurrentItem()"}

def emit_trophies(clog_item_ids) -> str:
    if not clog_item_ids:
        return emit_module("trophies", "Collection-log trophies", "", "Generic clog highlight")
    idl = _id_list(clog_item_ids)
    used = set()
    lines = [emit_rule(f"{IRONMAN} && {idl}", {"hidden": "false"}, terminal=False)]  # never hide (not editable)
    for grade, minv, emph in TROPHY_GRADES:
        label = f"Trophy {grade} (any)" if minv == 0 else f"Trophy {grade} (>={_human(minv)})"
        lines.append(emit_style_input("trophies", label, "Collection log", _macro_name("TROPHY", grade, used),
            f"{IRONMAN} && {idl} && value:>={minv}", _trophy_style(emph)))
    return emit_module("trophies", "Collection-log trophies", "\n".join(lines), "Generic clog highlight")

def _name_list(patterns) -> str:
    return "name:[" + ", ".join(f'"{p}"' for p in patterns) + "]"

# FilterScape group label per category id (organises the colour pickers into collapsible sections).
_GROUP_LABEL = {"gear": "Gear", "ores": "Ores", "bars": "Bars", "runes": "Runes", "gems": "Gems",
                "essence": "Essence", "ammo": "Ammo", "logs": "Logs", "planks": "Planks", "herbs": "Herbs",
                "seeds": "Seeds", "bones": "Prayer supplies", "food": "Food", "teleports": "Teleports",
                "charged_jewellery": "Jewellery", "potions": "Potions"}

def _flat_panel(hue: str, border: str | None = None) -> dict:
    """One solid editable panel per group (no value-grade escalation -- identity colour is the point)."""
    return {"backgroundColor": hue, "borderColor": border or _border_on(hue), "textColor": _text_on(hue),
            "fontType": "1", "textAccent": "3", "icon": "CurrentItem()"}

def _macro_name(prefix: str, label: str, used: set) -> str:
    base = prefix + "_" + re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").upper()
    macro, i = base, 2
    while macro in used:                       # macros are global -> keep them unique
        macro, i = f"{base}_{i}", i + 1
    used.add(macro)
    return macro

def emit_categories() -> str:
    lines, used = [], set()
    def add(cid, label, group, patterns, hue, excludes, border):
        conds = f"{IRONMAN} && {_name_list(patterns)}"
        if excludes:
            conds += f" && !{_name_list(excludes)}"
        # bones/ashes/ensouled default to elegant TEXT (no panel); everything else a solid panel
        style = ({"textColor": hue, "textAccent": "1", "fontType": "1"} if cid == "bones"
                 else _flat_panel(hue, border))
        lines.append(emit_style_input("categories", label, group, _macro_name("CAT", label, used), conds, style))
    for row in category_rules():
        cid, display, patterns, hue, excludes = row[:5]
        border = row[5] if len(row) > 5 else None   # optional 6th elem: border override (divine potions)
        group = _GROUP_LABEL.get(cid, cid.title())
        if hue is None:  # ores/bars -> one editable picker PER NAME (each carries its own hue)
            table = ORE_NAMES if cid == "ores" else BAR_NAMES
            for nm in patterns:
                add(cid, nm, group, [nm], table[nm], [], None)
        else:
            add(cid, display, group, patterns, hue, excludes, border)
    return emit_module("categories", "Categories", "\n".join(lines), "By material / type")

def emit_settings() -> str:
    body = "\n".join([
        "#define IRONMAN accountType:1",   # core gate -- lives here so the filter STARTS with a module
        '/*@ define:input:settings\nlabel: Hide below value\ntype: number\ngroup: Hide\n*/\n#define HIDE_FLOOR 0',
        '/*@ define:input:settings\nlabel: Show world spawns\ntype: boolean\ngroup: Show\n*/\n#define SHOW_WORLD_SPAWNS true',
        f"apply ({IRONMAN} && !SHOW_WORLD_SPAWNS && ownership:0) {{ hidden = true; }}",
        '/*@ define:input:settings\nlabel: Show unowned drops\ntype: boolean\ngroup: Show\n*/\n#define SHOW_UNOWNED true',
        f"apply ({IRONMAN} && !SHOW_UNOWNED && ownership:2) {{ hidden = true; }}",
        '/*@ define:input:settings\nlabel: Despawn timer\ntype: boolean\ngroup: Show\n*/\n#define SHOW_DESPAWN true',
        f"apply ({IRONMAN} && SHOW_DESPAWN) {{ showDespawn = true; }}",
        '/*@ define:input:settings\nlabel: Item value\ntype: boolean\ngroup: Show\n*/\n#define SHOW_VALUE true',
        f"apply ({IRONMAN} && SHOW_VALUE) {{ showValue = true; }}",
    ])
    return emit_module("settings", "Settings", body,
                       "Show/hide toggles", "Display toggles for spawns, despawn timer, value, and the hide-below-value floor.")

# Untradeable rewards have ~0 GE value, so colour them by WHAT THEY ARE, not gp.
# CLUE TIERS get the full per-tier treatment (like potions): the seal colour as the panel, plus a
# unifying PARCHMENT border so "tier-colour panel + parchment border" is unmistakably a clue. The
# tier seals collide with coins/clog/etc., but nothing else in the filter has a parchment border.
_CLUE_BORDER = "#ffc8b088"   # scroll parchment -- the shared "this is a clue" signature
CLUE_TIERS = [   # (tier suffix, seal-colour panel) -- canonical OSRS clue tier seals
    ("beginner", "#ffa49a90"),  # grey seal
    ("easy",     "#ff1c8030"),  # green
    ("medium",   "#ff3a8aa0"),  # blue
    ("hard",     "#ffa83cc6"),  # purple
    ("elite",    "#fff2c828"),  # yellow
    ("master",   "#ffc4342a"),  # red
]
_CLUE_CONTAINERS = ["Clue scroll", "Scroll box", "Clue bottle", "Clue nest", "Clue geode", "Reward casket"]

# Other untradeable reward-type buckets, then "earned violet" for the rest. tradeable:false gates
# every rule, so a bucket pattern only ever matches the untradeable variant.
UNTRADEABLE_TYPES = [
    (["*cape*", "*cloak*"], "#ffc0392b"),                            # capes/cloaks (diary, skill; catches cape(t)) -> regal crimson
    (["Pet *", "* ahrim*", "Vorki", "Tzrek*"], "#ffff6fc0"),           # a few obvious pets -> pet pink
]
_UNTRADEABLE_DEFAULT = "#ff8a2be2"  # earned violet

def _untradeable_panel(hue: str, border: str | None = None) -> dict:
    return {"backgroundColor": hue, "borderColor": border or _border_on(hue), "textColor": _text_on(hue),
            "fontType": "2", "textAccent": "3", "icon": "CurrentItem()"}

_UNTRADEABLE_TYPE_LABELS = ["Capes & cloaks", "Pets"]

def emit_untradeables() -> str:
    """Iron-specific: an untradeable drop is EARNED account progression that GE value can't rank.
    Per-tier CLUE colour pickers (parchment border), then capes/pets, then earned-violet -- all editable."""
    lines, used = [], set()
    for tier, hue in CLUE_TIERS:   # per-tier clue colour pickers, sharing the parchment border
        pats = [f"{c} ({tier})" for c in _CLUE_CONTAINERS]
        lines.append(emit_style_input("untradeables", f"Clue ({tier})", "Clues", _macro_name("CLUE", tier, used),
            f"{IRONMAN} && tradeable:false && {_name_list(pats)}", _untradeable_panel(hue, _CLUE_BORDER)))
    for (p, hue), label in zip(UNTRADEABLE_TYPES, _UNTRADEABLE_TYPE_LABELS):
        lines.append(emit_style_input("untradeables", label, "Untradeables", _macro_name("UNTR", label, used),
            f"{IRONMAN} && tradeable:false && {_name_list(p)}", _untradeable_panel(hue)))
    lines.append(emit_style_input("untradeables", "Other untradeables (earned)", "Untradeables", "UNTR_DEFAULT",
        f"{IRONMAN} && tradeable:false", _untradeable_panel(_UNTRADEABLE_DEFAULT)))
    return emit_module("untradeables", "Untradeables", "\n".join(lines), "Clue tiers, types, then earned-violet")
