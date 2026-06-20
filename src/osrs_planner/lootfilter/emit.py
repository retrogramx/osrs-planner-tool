# src/osrs_planner/lootfilter/emit.py
"""rs2f emitter (design §4/§5). Bools/ints bare, colours quoted. Every styling rule
is iron-gated via the IRONMAN macro. HIDE_FLOOR default 0 hides nothing."""
from __future__ import annotations

from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for
from osrs_planner.lootfilter.palette import TROPHY_GRADES  # add to imports
from osrs_planner.lootfilter.categories import category_rules, ORE_NAMES, BAR_NAMES, CRYSTAL_SEEDS  # add

IRONMAN = "IRONMAN"
_BARE = {"true", "false"}

def style_str(style: dict) -> str:
    parts = []
    for k, v in style.items():
        v = str(v)
        parts.append(f"{k} = {v};" if (v in _BARE or v.lstrip("-").isdigit()) else f'{k} = "{v}";')
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

def emit_fallback() -> str:
    lines = [emit_rule(f"{IRONMAN} && value:<HIDE_FLOOR", {"hidden": "true"})]  # default 0 -> hides nothing
    for grade, minv, _e in VALUE_GRADES:
        lines.append(emit_rule(f"{IRONMAN} && value:>={minv}", style_for("#ffffffff", grade)))
    return emit_module("fallback", "Value fallback (SS→E)", "\n".join(lines))

def _id_list(ids) -> str:
    return "id:[" + ", ".join(str(i) for i in sorted(set(ids))) + "]"

def _trophy_style(emph: dict) -> dict:
    return {"textColor": "#ffffffff", "backgroundColor": "#ff" + emph["hue"][3:], "borderColor": emph["hue"],
            "fontType": str(emph["fontType"]), "textAccent": str(emph["accent"]),
            "showLootbeam": "true", "lootbeamColor": emph["hue"], "sound": "3930"}

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

def _emit_group(cid, patterns, hue, lines):
    nl = _name_list(patterns)
    extra = f" && !{_name_list(sorted(CRYSTAL_SEEDS))}" if cid == "seeds" else ""
    for grade, minv, _e in VALUE_GRADES:
        lines.append(emit_rule(f"{IRONMAN} && {nl}{extra} && value:>={minv}", style_for(hue, grade)))

def emit_categories() -> str:
    lines = []
    for cid, _name, patterns, hue in category_rules():
        if hue is None:  # ores/bars -> each item NAME carries its own hue
            table = ORE_NAMES if cid == "ores" else BAR_NAMES
            for nm in patterns:
                _emit_group(cid, [nm], table[nm], lines)
        else:
            _emit_group(cid, patterns, hue, lines)
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
