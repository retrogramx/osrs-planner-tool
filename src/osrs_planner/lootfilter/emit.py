# src/osrs_planner/lootfilter/emit.py
"""rs2f emitter (design §4/§5). Bools/ints bare, colours quoted. Every styling rule
is iron-gated via the IRONMAN macro. HIDE_FLOOR default 0 hides nothing."""
from __future__ import annotations

import re

from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for, FALLBACK_HUES, _text_on, _border_on, COIN_TIERS
from osrs_planner.lootfilter.palette import TROPHY_GRADES  # add to imports
from osrs_planner.lootfilter.palette import FAMILY_HUES, gear_score, GEAR_TIERS
from osrs_planner.lootfilter.palette import GRADE_ORDER, quantity_display_grade
from osrs_planner.lootfilter.categories import category_rules, categorize

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

def _yaml_scalar(value: str) -> str:
    """Double-quote a value destined for a YAML plain-scalar field (name/subtitle/label/group).
    FilterScape parses each `define:module`/`define:input`/`define:group` body as YAML, and a plain
    scalar containing a colon-space, '#', or a leading indicator char throws -- which nulls the
    ENTIRE imported filter ('No filter selected'), not just its module. Quoting is the class-level
    guard so any editorial string is import-safe."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

def emit_style_input(module_id: str, label: str, group: str, macro: str, conds: str,
                     style: dict, terminal: bool = True) -> str:
    """A FilterScape-EDITABLE style: a `type: style` input (colour picker) + a `#define` holding its
    default + a rule that applies the macro. Editing the picker rewrites the #define on export."""
    decl = f"/*@ define:input:{module_id}\ntype: style\nlabel: {_yaml_scalar(label)}\ngroup: {_yaml_scalar(group)}\n*/"
    define = f"#define {macro} {_macro_body(style)}"
    rule = f"{'rule' if terminal else 'apply'} ({conds}) {{ {macro} }}"
    return f"{decl}\n{define}\n{rule}"

def _quoted_list(items) -> str:
    """A ["a", "b"] list of quoted, escaped strings — valid for both a YAML `enum:` and an rs2f
    `#define` default list."""
    return "[" + ", ".join(_yaml_scalar(str(i)) for i in items) + "]"

def emit_enumlist_input(module_id: str, label: str, group: str, enum_names, macro: str, default_names) -> str:
    """A type:enumlist dropdown (options = enum_names) + its #define default selection. The user
    moves items between tier dropdowns to re-tier them (spec §4)."""
    decl = (f"/*@ define:input:{module_id}\nlabel: {_yaml_scalar(label)}\ntype: enumlist\n"
            f"enum: {_quoted_list(enum_names)}\ngroup: {_yaml_scalar(group)}\n*/")
    return f"{decl}\n#define {macro} {_quoted_list(default_names)}"

def emit_number_input(module_id: str, label: str, group: str, macro: str, default: int) -> str:
    decl = (f"/*@ define:input:{module_id}\nlabel: {_yaml_scalar(label)}\ntype: number\n"
            f"group: {_yaml_scalar(group)}\n*/")
    return f"{decl}\n#define {macro} {int(default)}"

def emit_style_def(module_id: str, label: str, group: str, macro: str, style: dict) -> str:
    """A type:style colour picker + its #define default -- WITHOUT an apply rule (the caller emits
    its own match/escalation rules referencing the macro)."""
    decl = (f"/*@ define:input:{module_id}\ntype: style\nlabel: {_yaml_scalar(label)}\n"
            f"group: {_yaml_scalar(group)}\n*/")
    return f"{decl}\n#define {macro} {_macro_body(style)}"

def emit_meta(name: str, desc: str) -> str:
    return f'meta {{\n    name = "{name}";\n    description = "{desc}";\n}}\n'

def emit_module(module_id: str, name: str, body: str, subtitle: str = "", description: str = "") -> str:
    # FilterScape/loot-filters-ui require name + subtitle + description on EVERY module (the plugin
    # is lenient, the web customizer isn't -- a missing field makes its importer build a bad module).
    return (f"/*@ define:module:{module_id}\nname: {_yaml_scalar(name)}\n"
            f"subtitle: {_yaml_scalar(subtitle or name)}\n"
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

def hue_for(name: str, family: str) -> str:
    """Identity hue for a resource item: per-name via categorize() (coal dark, per-element runes,
    per-tree logs, gems, ore/bar), else the family hue, else neutral grey (never raises)."""
    c = categorize(name)
    if c and c.get("hue"):
        return c["hue"]
    return FAMILY_HUES.get(family, "#ff9e9e9e")

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

_NOTABLE_HUE = "#ffd08a20"   # amber "known target" border for recommended items
_RARE_HUE = "#ffff45d6"      # magenta rare-drop beam
_VALUE_HUE = "#ffff2b2b"     # red high-value beam (matches FALLBACK_HUES SS)

def emit_notable(recommended_ids, rare_ids) -> str:
    """Beam policy (design §5): rare drops + the value:>=500000 safety net are the scarcity signal
    and DO beam; recommended-for-activity items get a border-lift EDITABLE style with NO beam
    (else every recommended item -- hundreds -- would beam). The BEAM rules are emitted FIRST
    (whole-branch-review fix B): rules are terminal/first-match-wins, so a recommended item that
    is ALSO rare or >=500k must hit the beam rule, not the no-beam recommended rule -- else
    recommended∩rare/value items (e.g. Abyssal whip, Bandos chestplate) would never beam."""
    used, lines = set(), []
    if rare_ids:
        style = {"backgroundColor": _RARE_HUE, "borderColor": "#ffffffff", "textColor": _text_on(_RARE_HUE),
                 "fontType": "3", "textAccent": "3", "showLootbeam": "true", "lootbeamColor": _RARE_HUE, "sound": "3925"}
        lines.append(emit_style_input("notable", "Rare drop", "Notable",
            _macro_name("NOTABLE", "rare", used), f"{IRONMAN} && {_id_list(rare_ids)}", style))
    vstyle = {"backgroundColor": _VALUE_HUE, "borderColor": "#ffffffff", "textColor": _text_on(_VALUE_HUE),
              "fontType": "3", "textAccent": "3", "showLootbeam": "true", "lootbeamColor": _VALUE_HUE, "sound": "3925"}
    lines.append(emit_style_input("notable", "High value (>=500k)", "Notable",
        _macro_name("NOTABLE", "value", used), f"{IRONMAN} && value:>=500000", vstyle))
    if recommended_ids:
        style = {"backgroundColor": _NOTABLE_HUE, "borderColor": "#ffffffff",
                 "textColor": _text_on(_NOTABLE_HUE), "fontType": "2", "textAccent": "3"}
        lines.append(emit_style_input("notable", "Recommended-for-activity", "Notable",
            _macro_name("NOTABLE", "recommended", used), f"{IRONMAN} && {_id_list(recommended_ids)}", style))
    return emit_module("notable", "Notable", "\n".join(lines), "Recommended / rare / high-value")

def emit_gear(gear_records) -> str:
    """Equipment ranked WITHIN each slot by gear_score, bucketed into GEAR_TIERS (fraction of that
    slot's max score). One editable id-list style-input per (slot, tier), brightest tier first."""
    from collections import defaultdict
    by_slot = defaultdict(list)
    for r in gear_records:
        by_slot[r["slot"]].append((r["item_id"], gear_score(r["stats"])))
    hue = FAMILY_HUES["gear"]
    used, lines = set(), []
    for slot in sorted(by_slot):
        items = by_slot[slot]
        top = max((s for _i, s in items), default=0) or 1
        tiers = defaultdict(list)
        for iid, score in items:
            # Clamp: gear_score sums defence bonuses, so a slot can contain a NEGATIVE-scoring
            # item even when `top` (the slot max) is positive. GEAR_TIERS bottoms out at 0.0, so
            # an unclamped negative frac would match no tier -> uncaught StopIteration. Clamping
            # to 0.0 puts a negative-score item in the lowest grade (C), which is the correct
            # placement -- it's worse than everything else in the slot.
            frac = max(score / top, 0.0)
            grade = next(g for g, thr in GEAR_TIERS if frac >= thr)
            tiers[grade].append(iid)
        for grade, _thr in GEAR_TIERS:            # emit S..C (brightest first)
            ids = tiers.get(grade)
            if not ids:
                continue
            lines.append(emit_style_input("gear", f"Gear {slot} {grade}", f"Gear — {slot}",
                _macro_name("GEAR", f"{slot}{grade}", used),
                f"{IRONMAN} && {_id_list(ids)}", style_for(hue, grade)))
    return emit_module("gear", "Gear by slot", "\n".join(lines), "Equipment tiered by slot")

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
        add(cid, display, group, patterns, hue, excludes, border)
    return emit_module("categories", "Categories", "\n".join(lines), "By material / type")

def emit_families(family_ids, skip=frozenset()) -> str:
    """One editable style-input per derived family. Skips 'gear' (stat-tiered by emit_gear), any
    family with no ids / no FAMILY_HUES entry, and any family in `skip` (owned by emit_quantities)."""
    used, lines = set(), []
    for fam in sorted(family_ids):
        ids = family_ids[fam]
        if not ids or fam not in FAMILY_HUES or fam == "gear" or fam in skip:
            continue
        lines.append(emit_style_input("families", fam.replace("_", " ").title(), "Families",
            _macro_name("FAM", fam, used), f"{IRONMAN} && {_id_list(ids)}",
            _flat_panel(FAMILY_HUES[fam])))
    return emit_module("families", "Resource families", "\n".join(lines), "By derived family")

def emit_quantities(importance, hue_for=hue_for) -> str:
    """Resource piles: hand-ranked base tier (from loot_importance) escalated one grade per ×10 in
    pile count (design §3/§5), rendered in the item's identity hue. Groups by (family, hue, base) so
    id-lists stay short; per group emits threshold-descending rules (SS first = first-match-wins)."""
    from collections import defaultdict
    groups = defaultdict(list)            # (family, hue, base_tier) -> [item_id]
    all_ids = []
    for r in importance:
        hue = hue_for(r["name"], r["family"])
        groups[(r["family"], hue, r["base_tier"])].append(r["item_id"])
        all_ids.append(r["item_id"])
    used, lines = set(), []
    lines.append("/*@ define:input:quantities\nlabel: Hide piles below count\ntype: number\ngroup: Hide\n*/\n#define QUANTITY_FLOOR 0")
    lines.append(emit_rule(f"{IRONMAN} && {_id_list(all_ids)} && quantity:<QUANTITY_FLOOR", {"hidden": "true"}, terminal=False))
    for family, hue, base in sorted(groups, key=lambda k: (k[0], GRADE_ORDER.index(k[2]), k[1])):
        ids = groups[(family, hue, base)]
        bi = GRADE_ORDER.index(base)
        group_label = f"Quantities — {family.replace('_', ' ').title()}"
        for k in range(bi, -1, -1):                    # decades: k=bi (thr 10^bi -> SS) first .. k=0 (thr 1 -> base)
            thr = 10 ** k
            grade = quantity_display_grade(base, thr)  # single-source the ×10 model (Task 1)
            cond = f"{IRONMAN} && {_id_list(ids)}"
            if thr > 1:
                cond += f" && quantity:>={thr}"
            lines.append(emit_style_input("quantities", f"{family.title()} {grade} (base {base}, >={thr})",
                group_label, _macro_name("QTY", f"{family}_{base}_{grade}_{hue[3:]}", used), cond,
                style_for(hue, grade)))
    return emit_module("quantities", "Quantities", "\n".join(lines),
                       "Resource piles: base importance escalated by stack size")

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

def emit_list_input(module_id: str, label: str, group: str, macro: str, default: str = "") -> str:
    """A `type: stringlist` input + its #define (default empty). Users type item names into it."""
    decl = f"/*@ define:input:{module_id}\ntype: stringlist\nlabel: {_yaml_scalar(label)}\ngroup: {_yaml_scalar(group)}\n*/"
    return f"{decl}\n#define {macro} [{default}]"

def emit_custom_highlights(free: int = 6, tiers=("SS", "S", "A", "B", "C")) -> str:
    """Manual-override layer (spec §2): FilterScape has no native per-item override, so we ship
    generic custom highlight groups instead -- paired stringlist (typed item names) + style
    (colour/beam) inputs, plus tier-inject slots and a hide bank. All empty/off by default."""
    used, lines = set(), []
    for i in range(1, free + 1):
        listmac = _macro_name("CUSTOMLIST", str(i), used)
        lines.append(emit_list_input("custom", f"Custom highlight {i} — items", "Custom highlights", listmac))
        lines.append(emit_style_input("custom", f"Custom highlight {i} — style", "Custom highlights",
            _macro_name("CUSTOMSTYLE", str(i), used), f"{IRONMAN} && name:{listmac}",
            {"textColor": "#ffffffff", "fontType": "2", "textAccent": "3"}))
    for grade in tiers:
        listmac = _macro_name("CUSTOMTIER", grade, used)
        lines.append(emit_list_input("custom", f"Custom {grade}-tier items", "Custom tiers", listmac))
        lines.append(emit_rule(f"{IRONMAN} && name:{listmac}", style_for(FALLBACK_HUES[grade], grade)))
    # hide bank
    hidemac = _macro_name("CUSTOMHIDE", "list", used)
    lines.append(emit_list_input("custom", "Hide these items", "Hide", hidemac))
    lines.append(emit_rule(f"{IRONMAN} && name:{hidemac}", {"hidden": "true"}))
    return emit_module("custom", "Custom highlights", "\n".join(lines),
                       "Type item names to recolour / hide them yourself")
