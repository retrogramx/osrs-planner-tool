# src/osrs_planner/lootfilter/emit.py
"""rs2f emitter (design §4/§5). Bools/ints bare, colours quoted. Every styling rule
is iron-gated via the IRONMAN macro. HIDE_FLOOR default 0 hides nothing."""
from __future__ import annotations

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

def emit_meta(name: str, desc: str) -> str:
    return f'meta {{\n    name = "{name}";\n    description = "{desc}";\n}}\n'

def emit_module(module_id: str, name: str, body: str) -> str:
    return f"/*@ define:module:{module_id}\nname: {name}\n*/\n{body}\n"

def emit_preamble() -> str:
    return ("#define IRONMAN accountType:1\n"
            '/*@ define:input:settings\nlabel: Hide below value\ntype: number\ngroup: Hide\n*/\n'
            "#define HIDE_FLOOR 0\n")

def emit_coins() -> str:
    """Coins + platinum tokens -> their own gold ladder, darkening as the stack value climbs."""
    idl = "id:[995, 13204]"
    lines = []
    for minv, gold in COIN_TIERS:
        lines.append(emit_rule(f"{IRONMAN} && {idl} && value:>={minv}",
            {"backgroundColor": gold, "borderColor": _border_on(gold), "textColor": _text_on(gold),
             "fontType": "1", "textAccent": "3", "icon": "CurrentItem()"}))
    return emit_module("coins", "Coins (gold, darkening by stack)", "\n".join(lines))

def emit_fallback() -> str:
    lines = [emit_rule(f"{IRONMAN} && value:<HIDE_FLOOR", {"hidden": "true"})]  # default 0 -> hides nothing
    for grade, minv, _e in VALUE_GRADES:
        lines.append(emit_rule(f"{IRONMAN} && value:>={minv}", style_for(FALLBACK_HUES[grade], grade)))
    return emit_module("fallback", "Value fallback (SS→E)", "\n".join(lines))

def _id_list(ids) -> str:
    return "id:[" + ", ".join(str(i) for i in sorted(set(ids))) + "]"

def _trophy_style(emph: dict) -> dict:
    return {"textColor": "#ffffffff", "backgroundColor": "#ff" + emph["hue"][3:], "borderColor": emph["hue"],
            "fontType": str(emph["fontType"]), "textAccent": str(emph["accent"]),
            "showLootbeam": "true", "lootbeamColor": emph["hue"], "sound": "3930", "icon": "CurrentItem()"}

def emit_trophies(clog_item_ids) -> str:
    if not clog_item_ids:
        return emit_module("trophies", "Collection-log trophies", "")
    idl = _id_list(clog_item_ids)
    lines = [emit_rule(f"{IRONMAN} && {idl}", {"hidden": "false"}, terminal=False)]
    for grade, minv, emph in TROPHY_GRADES:
        lines.append(emit_rule(f"{IRONMAN} && {idl} && value:>={minv}", _trophy_style(emph)))
    return emit_module("trophies", "Collection-log trophies", "\n".join(lines))

def _name_list(patterns) -> str:
    return "name:[" + ", ".join(f'"{p}"' for p in patterns) + "]"

# Categories that should NOT force a panel on cheap drops -- prayer supplies (bones/ashes/ensouled)
# are common + low-value, so they value-grade like the fallback: cheap = elegant text, valuable = panel.
_SOFT_CATEGORIES = {"bones"}

def _emit_group(patterns, hue, excludes, lines, border=None, floor=True):
    nl = _name_list(patterns)
    extra = f" && !{_name_list(excludes)}" if excludes else ""
    for grade, minv, _e in VALUE_GRADES:
        # floor=True: keep a SOLID material panel even when cheap (iron-useful != gp). floor=False:
        # value-grade naturally so cheap drops stay elegant TEXT instead of a busy panel.
        g = ("C" if grade in ("D", "E") else grade) if floor else grade
        lines.append(emit_rule(f"{IRONMAN} && {nl}{extra} && value:>={minv}", style_for(hue, g, border)))

def emit_categories() -> str:
    lines = []
    for row in category_rules():
        cid, _name, patterns, hue, excludes = row[:5]
        border = row[5] if len(row) > 5 else None   # optional 6th elem: border override (divine potions)
        floor = cid not in _SOFT_CATEGORIES
        if hue is None:  # ores/bars -> each item NAME carries its own hue
            table = ORE_NAMES if cid == "ores" else BAR_NAMES
            for nm in patterns:
                _emit_group([nm], table[nm], excludes, lines)
        else:
            _emit_group(patterns, hue, excludes, lines, border, floor)
    return emit_module("categories", "Categories (by material/type)", "\n".join(lines))

def emit_settings() -> str:
    body = "\n".join([
        '/*@ define:input:settings\nlabel: Show world spawns\ntype: boolean\ngroup: Show\n*/\n#define SHOW_WORLD_SPAWNS true',
        f"apply ({IRONMAN} && !SHOW_WORLD_SPAWNS && ownership:0) {{ hidden = true; }}",
        '/*@ define:input:settings\nlabel: Show unowned drops\ntype: boolean\ngroup: Show\n*/\n#define SHOW_UNOWNED true',
        f"apply ({IRONMAN} && !SHOW_UNOWNED && ownership:2) {{ hidden = true; }}",
        '/*@ define:input:settings\nlabel: Despawn timer\ntype: boolean\ngroup: Show\n*/\n#define SHOW_DESPAWN true',
        f"apply ({IRONMAN} && SHOW_DESPAWN) {{ showDespawn = true; }}",
        '/*@ define:input:settings\nlabel: Item value\ntype: boolean\ngroup: Show\n*/\n#define SHOW_VALUE true',
        f"apply ({IRONMAN} && SHOW_VALUE) {{ showValue = true; }}",
    ])
    return emit_module("settings", "Settings", body)

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

def emit_untradeables() -> str:
    """Iron-specific: an untradeable drop is EARNED account progression that GE value can't rank.
    CLUE TIERS first (seal colour + parchment border), then colour by TYPE (capes/pets...), else an
    "earned" violet -- always a panel + icon. Sits above categories/fallback, below the clog trophies."""
    lines = []
    for tier, hue in CLUE_TIERS:   # per-tier clue panels, all sharing the parchment border
        pats = [f"{c} ({tier})" for c in _CLUE_CONTAINERS]
        lines.append(emit_rule(f"{IRONMAN} && tradeable:false && {_name_list(pats)}", _untradeable_panel(hue, _CLUE_BORDER)))
    lines += [emit_rule(f"{IRONMAN} && tradeable:false && {_name_list(p)}", _untradeable_panel(hue))
              for p, hue in UNTRADEABLE_TYPES]
    lines.append(emit_rule(f"{IRONMAN} && tradeable:false", _untradeable_panel(_UNTRADEABLE_DEFAULT)))
    return emit_module("untradeables", "Untradeables (clue tiers, types, then earned-violet)", "\n".join(lines))
