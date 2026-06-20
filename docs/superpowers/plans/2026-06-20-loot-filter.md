# Loot-Filter Generator Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an impressive ironman RuneLite Loot-Filters (`.rs2f`) filter — two-axis visual language (hue=identity, emphasis=value), a collection-log trophy layer, and **account tailoring** (beam the log slots you still need; optionally hide what you bank).

**Architecture:** `src/osrs_planner/lootfilter/` assembles a `.rs2f` from committed config (`palette` colours/grades + `categories` explicit name-lists) + data (`collection_log.json` ids via `item_dictionary.json`) + an optional real `AccountState` (`tailor.py`), through an `emit.py` text emitter and a `generate.py` orchestrator. Writes a committed **generic** `outputs/gilded-tome-iron.rs2f`; the **tailored** output is account-specific and never committed. Independent of the engine/cost/income overlays (the plugin computes `value`).

**Tech Stack:** Python 3 (stdlib `json`/`re`/`os`), pytest. Target = the `riktenx/loot-filters` rs2f DSL. Consumes `osrs_planner.account` (merged) for tailoring.

## Global Constraints

- **rs2f grammar (verified from `filter-lang.md` + Storn's real filter):** `meta { name=…; description=…; }`; `rule (<conds>) { <prop>=<val>; }` (terminal) / `apply (<conds>) { … }` (non-terminal); conds `id:995`/`id:[995,996]`, `name:"x"`/`name:["a","b"]`/wildcards `"*godsword"`, `value:>=N`/`value:<N`/`havalue:>=N` (ops `> < >= <= ==`), `accountType:1`, `ownership:0|1|2|3`, joined `&& || !`; style `textColor`/`backgroundColor`/`borderColor`/`lootbeamColor`/`menuTextColor` (8-hex ARGB `"#aarrggbb"`), `showLootbeam`/`showValue`/`showDespawn`/`notify`/`hidden` (bare bool), `fontType` (1/2/3), `textAccent` (1/2/3/4), `menuSort` (int), `sound` (int cache-id). `#define NAME value`. Module annotations: `/*@ define:module:<id>\nname: …\n*/` and `/*@ define:input:<module>\nlabel: …\ntype: boolean\ngroup: …\n*/` (filterscape layer; verified against Storn's filter, NOT in `filter-lang.md`).
- **Verified toggle idiom (Storn):** `#define SHOW_X true` then `apply (!SHOW_X && cond) { hidden = true; }` parses and works.
- **Iron gate = `#define IRONMAN accountType:1`** (NOT `IRON` — collides with the built-in `IRON` colour keyword). Prepend `IRONMAN` to EVERY styling rule AND every settings/trophy/tailoring `apply`.
- **Colours are 8-hex ARGB** `"#aarrggbb"` (alpha `ff`).
- **Categories are EXPLICIT name-lists, never bare `"{Metal} *"` globs** (over-match ammo/essence/etc.). Bars/ores use REAL names (`Bronze` is not an ore; bars/ores are `Adamantite`/`Runite`, not `Adamant`/`Rune`; `Coal` has no "ore" suffix).
- **Nothing hidden by default:** `HIDE_FLOOR` default `0`, `HIDE_OWNED` default `false`.
- **Module/eval order:** `settings → tailoring(if account) → trophies → categories → fallback`.
- **Determinism:** id-lists sorted; fixed module order; generic re-gen byte-stable.
- **Licensing:** rs2f format is the plugin's (free to emit); Storn's/Joe's filters are design reference ONLY — our own modules/names/colours.
- **Boundary:** `lootfilter/` imports stdlib + `osrs_planner.account.state` (for tailoring types); NOT `osrs_planner.engine`/`.cost`/`.income` overlay logic; KG untouched.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/osrs_planner/lootfilter/__init__.py` | package marker |
| `src/osrs_planner/lootfilter/palette.py` | `VALUE_GRADES`, `style_for`, `TROPHY_GRADES`, colour maps. Pure data. |
| `src/osrs_planner/lootfilter/categories.py` | `categorize()` matcher + `category_rules()` (explicit name-lists). |
| `src/osrs_planner/lootfilter/emit.py` | rs2f emitter (meta, rule builder, modules, IRONMAN preamble, fallback+HIDE_FLOOR, settings, trophies, categories). |
| `src/osrs_planner/lootfilter/tailor.py` | account-aware module: missing-clog beam, obtained dim, hide-owned. |
| `src/osrs_planner/lootfilter/generate.py` | `generate_filter(account_state=None)` + `write_filter`. |
| `data/validate_loot_filter.py` | structural validator. |
| `outputs/gilded-tome-iron.rs2f` | committed generic artifact. |
| `scripts/lootfilter_demo.py` | regen generic + a tailored example over account fixtures. |
| `tests/lootfilter/test_*.py` | per-unit tests. |

---

## Task 1: Palette (visual language) + boundary

**Files:** Create `src/osrs_planner/lootfilter/__init__.py`, `palette.py`, `tests/lootfilter/__init__.py`, `tests/lootfilter/test_palette.py`, `tests/lootfilter/test_boundary.py`

**Interfaces:**
- Produces: `VALUE_GRADES: list[(grade, min_value, emphasis)]` SS→E; `style_for(hue, grade) -> dict[str,str]`; `TROPHY_GRADES`; `MATERIAL_COLORS`/`RUNE_COLORS`/`GEM_COLORS`/`LOG_COLORS` (`dict[str,"#aarrggbb"]`).

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_palette.py`)

```python
from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for, TROPHY_GRADES, MATERIAL_COLORS

def test_grades_descend():
    assert [g[0] for g in VALUE_GRADES] == ["SS","S","A","B","C","D","E"]
    assert [g[1] for g in VALUE_GRADES] == [10_000_000,1_000_000,100_000,10_000,1_000,100,0]

def test_escalation_beam_at_S_sound_at_A():
    e = {g[0]: g[2] for g in VALUE_GRADES}
    assert e["S"]["beam"] and not e["A"]["beam"]
    assert e["A"]["sound"] and not e["B"]["sound"]

def test_style_for_renders_hue():
    s = style_for("#ff4169e1", "S")
    assert s["textColor"] == "#ff4169e1" and s["showLootbeam"] == "true" and s["lootbeamColor"] == "#ff4169e1"

def test_material_colors():
    for m in ("bronze","iron","steel","black","mithril","adamant","rune","dragon"):
        assert MATERIAL_COLORS[m].startswith("#ff") and len(MATERIAL_COLORS[m]) == 9

def test_trophy_always_beams():
    g = {x[0]: x[2] for x in TROPHY_GRADES}
    assert all(g[k]["beam"] and g[k]["sound"] for k in ("SS","S","A","B","C"))
```

- [ ] **Step 2: Run → fail** — `venv/bin/python -m pytest tests/lootfilter/test_palette.py -v` (module not found).

- [ ] **Step 3: Implement** (`src/osrs_planner/lootfilter/palette.py`)

```python
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
```

- [ ] **Step 4: Run → pass.** `venv/bin/python -m pytest tests/lootfilter/test_palette.py -v` (5 pass).

- [ ] **Step 5: Boundary test** (`tests/lootfilter/test_boundary.py`)

```python
import ast, os
PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "src", "osrs_planner", "lootfilter")
FORBIDDEN = ("osrs_planner.engine", "osrs_planner.cost", "osrs_planner.income")

def test_lootfilter_imports_no_overlay():
    bad = []
    for fn in os.listdir(PKG):
        if not fn.endswith(".py"): continue
        for node in ast.walk(ast.parse(open(os.path.join(PKG, fn), encoding="utf-8").read())):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for m in mods:
                if any(b in (m or "") for b in FORBIDDEN): bad.append(f"{fn}: {m}")
    assert not bad, f"forbidden overlay import: {bad}"
```
Create `src/osrs_planner/lootfilter/__init__.py` + `tests/lootfilter/__init__.py` (empty).

- [ ] **Step 6: Run + commit.** `venv/bin/python -m pytest tests/lootfilter/ -v` (pass)
```bash
git add src/osrs_planner/lootfilter/__init__.py src/osrs_planner/lootfilter/palette.py tests/lootfilter/
git commit -m "loot-filter: palette (visual language) + boundary"
```

---

## Task 2: Categoriser (gear-word-gated, exclusions)

**Files:** Create `src/osrs_planner/lootfilter/categories.py`, `tests/lootfilter/test_categories.py`

**Interfaces:**
- Produces: `categorize(item_name) -> dict | None` (`{id, hue}`) — gear requires a metal prefix AND a gear word; ammo/essence/pouch/bones → None; crystal/weapon/armour seeds → None; `Grimy *` → herbs. Used by tests; the emitter uses `category_rules()` (Task 5).

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_categories.py`)

```python
from osrs_planner.lootfilter.categories import categorize
from osrs_planner.lootfilter.palette import MATERIAL_COLORS, RUNE_COLORS

def test_mithril_gear_is_metal():
    assert categorize("Mithril platebody")["id"] == "gear"
    assert categorize("Mithril platebody")["hue"] == MATERIAL_COLORS["mithril"]

def test_rune_ammo_and_essence_not_gear():
    assert categorize("Rune arrow") is None
    assert categorize("Rune essence") is None
    assert categorize("Runite ore")["id"] == "ores"     # ore, not gear

def test_black_mask_not_gear_dragon_bones_is_bones():
    assert categorize("Black mask") is None                  # slayer unique, not 'black gear'
    assert categorize("Dragon bones")["id"] == "bones"       # prayer supply -> bones, not 'dragon gear'
    assert categorize("Rune thrownaxe") is None              # ranged ammo, not melee 'axe' gear

def test_fire_rune_is_rune():
    c = categorize("Fire rune")
    assert c["id"] == "runes" and c["hue"] == RUNE_COLORS["fire"]

def test_grimy_herb_is_herb():
    assert categorize("Grimy ranarr weed")["id"] == "herbs"

def test_crystal_seed_not_seed_category():
    assert categorize("Crystal weapon seed") is None     # high-value unique, not a green seed
    assert categorize("Ranarr seed")["id"] == "seeds"

def test_twisted_bow_falls_through():
    assert categorize("Twisted bow") is None
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** (`src/osrs_planner/lootfilter/categories.py`)

```python
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
```

- [ ] **Step 4: Run → pass** (7 tests). **Step 5: Commit.**
```bash
git add src/osrs_planner/lootfilter/categories.py tests/lootfilter/test_categories.py
git commit -m "loot-filter: gear-word-gated categoriser with exclusions"
```

---

## Task 3: Emit core — meta, rule builder, IRONMAN preamble, fallback + hide floor

**Files:** Create `src/osrs_planner/lootfilter/emit.py`, `tests/lootfilter/test_emit.py`

**Interfaces:**
- Produces: `IRONMAN = "IRONMAN"`; `style_str(style) -> str`; `emit_rule(conds, style, terminal=True) -> str`; `emit_meta(name, desc) -> str`; `emit_module(id, name, body) -> str`; `emit_preamble() -> str` (`#define IRONMAN accountType:1` + `#define HIDE_FLOOR 0`); `emit_fallback() -> str` (the SS→E ladder + the HIDE_FLOOR cut, all IRONMAN-gated).

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_emit.py`)

```python
from osrs_planner.lootfilter.emit import emit_meta, emit_rule, style_str, emit_fallback, emit_preamble

def test_meta():
    assert 'name = "Gilded Tome — Iron";' in emit_meta("Gilded Tome — Iron", "x")

def test_style_str():
    assert style_str({"textColor": "#ff4169e1", "showLootbeam": "true"}) == '{ textColor = "#ff4169e1"; showLootbeam = true; }'

def test_emit_rule_terminal_and_apply():
    assert emit_rule("IRONMAN && value:>=1000", {"textColor": "#ffffffff"}).startswith("rule (")
    assert emit_rule("ownership:2", {"hidden": "true"}, terminal=False).startswith("apply (")

def test_preamble_defines_macros():
    p = emit_preamble()
    assert "#define IRONMAN accountType:1" in p and "#define HIDE_FLOOR 0" in p

def test_fallback_iron_gated_with_hide_floor():
    fb = emit_fallback()
    assert fb.count("rule (IRONMAN") == 8                 # 7 grades + 1 HIDE_FLOOR cut
    assert "value:<HIDE_FLOOR" in fb and "value:>=10000000" in fb and "value:>=0" in fb
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** (`src/osrs_planner/lootfilter/emit.py`)

```python
# src/osrs_planner/lootfilter/emit.py
"""rs2f emitter (design §4/§5). Bools/ints bare, colours quoted. Every styling rule
is iron-gated via the IRONMAN macro. HIDE_FLOOR default 0 hides nothing."""
from __future__ import annotations

from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for

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
```

- [ ] **Step 4: Run → pass** (5 tests). **Step 5: Commit.**
```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_emit.py
git commit -m "loot-filter: rs2f emitter core (IRONMAN gate, fallback + hide floor)"
```

---

## Task 4: Trophy module (collection-log id-list, never-hide)

**Files:** Modify `emit.py` (add `emit_trophies`); Test `tests/lootfilter/test_trophies.py`

**Interfaces:** `emit_trophies(clog_item_ids) -> str` — a `trophies` module: a non-terminal `apply (IRONMAN && id:[…]) { hidden=false; }` never-hide guard, then the SS→C gold/bronze ladder `rule (IRONMAN && id:[…] && value:>=…) { … beam+sound }`. ids sorted.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_trophies.py`)

```python
from osrs_planner.lootfilter.emit import emit_trophies

def test_trophies_never_hide_and_graded():
    out = emit_trophies([4151, 11920, 995])
    assert "apply (IRONMAN" in out and "hidden = false;" in out
    assert "id:[995, 4151, 11920]" in out
    assert "showLootbeam = true;" in out and "value:>=10000000" in out

def test_empty_clog_safe():
    assert "module:trophies" in emit_trophies([])
```

- [ ] **Step 2: Run → fail. Step 3: Implement in `emit.py`:**

```python
from osrs_planner.lootfilter.palette import TROPHY_GRADES  # add to imports

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
```

- [ ] **Step 4: Run → pass. Step 5: Commit.**
```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_trophies.py
git commit -m "loot-filter: collection-log trophy module (never-hide)"
```

---

## Task 5: Category modules (explicit name-lists, real ore/bar names)

**Files:** Modify `categories.py` (add `category_rules`); Modify `emit.py` (add `emit_categories`); Test `tests/lootfilter/test_emit_categories.py`

**Interfaces:** `categories.category_rules() -> list[(id, name, patterns: list[str], hue)]` — explicit name-lists (gear = `["{Metal} platebody", …]` per metal; ores/bars = real names; runes/gems/logs explicit; herbs `["Grimy *"]`; seeds `["* seed","* seedling"]`). `emit.emit_categories() -> str` — per group, the graded ladder; **seeds carry a `!name:[CRYSTAL_SEEDS]` exclusion** so crystal uniques fall through.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_emit_categories.py`)

```python
from osrs_planner.lootfilter.emit import emit_categories
from osrs_planner.lootfilter.categories import category_rules

def test_no_bare_metal_glob():
    pats = [p for _i,_n,ps,_h in category_rules() for p in ps]
    assert "Rune *" not in pats and "Mithril *" not in pats   # explicit lists only
    assert "Mithril platebody" in pats and "Mithril scimitar" in pats

def test_real_ore_bar_names_only():
    pats = [p for _i,_n,ps,_h in category_rules() for p in ps]
    assert "Runite ore" in pats and "Adamantite bar" in pats and "Coal" in pats
    assert "Bronze ore" not in pats and "Rune bar" not in pats  # non-existent items

def test_emit_has_mithril_blue_fire_red_and_seed_exclusion():
    out = emit_categories()
    assert '"Mithril platebody"' in out and "#ff4169e1" in out
    assert '"Fire rune"' in out and "#ffff4500" in out
    assert "Crystal weapon seed" in out and "!name:" in out     # seed exclusion present
    assert out.count("module:categories") == 1 and "IRONMAN &&" in out

def test_ore_bar_hue_identity():
    out = emit_categories()
    # Coal reads dark, Gold reads gold -- NOT borrowed gear-metal steel/dragon hues
    assert '"Coal"' in out and "#ff2b2b2b" in out               # Coal dark, not steel grey
    assert "#ffd8b01a" in out                                   # Gold ore/bar gold, not dragon red
```

- [ ] **Step 2: Run → fail. Step 3: Implement.**

In `categories.py`:
```python
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
```
Note: ores/bars pass `hue=None` and are expanded per-name in emit (each ore/bar gets its own metal hue). In `emit.py`:
```python
from osrs_planner.lootfilter.categories import category_rules, ORE_NAMES, BAR_NAMES, CRYSTAL_SEEDS  # add

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
```

- [ ] **Step 4: Run → pass. Step 5: Commit.**
```bash
git add src/osrs_planner/lootfilter/emit.py src/osrs_planner/lootfilter/categories.py tests/lootfilter/test_emit_categories.py
git commit -m "loot-filter: category modules (explicit name-lists, real ore/bar names, seed exclusion)"
```

---

## Task 6: Settings module (IRONMAN-gated toggles)

**Files:** Modify `emit.py` (add `emit_settings`); Test `tests/lootfilter/test_settings.py`

**Interfaces:** `emit_settings() -> str` — a `settings` module of `/*@ define:input */` toggles, EVERY apply IRONMAN-gated: show world-spawns, show unowned, despawn timer, item-value display. (HIDE_FLOOR macro lives in the preamble; its cut is in fallback.)

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_settings.py`)

```python
from osrs_planner.lootfilter.emit import emit_settings

def test_settings_iron_gated_and_covers_toggles():
    out = emit_settings()
    assert "module:settings" in out
    assert out.count("apply (IRONMAN") == out.count("apply (")   # every apply iron-gated
    for macro in ("SHOW_WORLD_SPAWNS", "SHOW_UNOWNED", "SHOW_DESPAWN", "SHOW_VALUE"):
        assert f"#define {macro}" in out
    assert "showValue = true;" in out and "showDespawn = true;" in out
```

- [ ] **Step 2: Run → fail. Step 3: Implement in `emit.py`:**

```python
def emit_settings() -> str:
    body = "\n".join([
        '/*@ define:input:settings\nlabel: Show world spawns\ntype: boolean\ngroup: Show\n*/\n#define SHOW_WORLD_SPAWNS true',
        f"apply ({IRONMAN} && !SHOW_WORLD_SPAWNS && ownership:0) {{ hidden = true; }}",
        '/*@ define:input:settings\nlabel: Show unowned drops\ntype: boolean\ngroup: Show\n*/\n#define SHOW_UNOWNED true',  # default true: never auto-hide other-players' drops
        f"apply ({IRONMAN} && !SHOW_UNOWNED && ownership:2) {{ hidden = true; }}",
        '/*@ define:input:settings\nlabel: Despawn timer\ntype: boolean\ngroup: Show\n*/\n#define SHOW_DESPAWN true',
        f"apply ({IRONMAN} && SHOW_DESPAWN) {{ showDespawn = true; }}",
        '/*@ define:input:settings\nlabel: Item value\ntype: boolean\ngroup: Show\n*/\n#define SHOW_VALUE true',
        f"apply ({IRONMAN} && SHOW_VALUE) {{ showValue = true; }}",
    ])
    return emit_module("settings", "Settings", body)
```

- [ ] **Step 4: Run → pass. Step 5: Commit.**
```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_settings.py
git commit -m "loot-filter: IRONMAN-gated settings module (incl. value display)"
```

---

## Task 7: Tailoring module (account-aware — the payoff)

**Files:** Create `src/osrs_planner/lootfilter/tailor.py`, `tests/lootfilter/test_tailor.py`

**Interfaces:**
- Consumes: `osrs_planner.account.state.AccountState` (`.counts`, `.clog_obtained` — `"item:<n>"` keys), `emit.py` helpers (`emit_module`/`emit_rule`/`IRONMAN`/`_id_list`).
- Produces: `emit_tailoring(account_state, clog_ids, value_index=None) -> str` (the caller passes the clog id-set, e.g. `set(generate.load_clog_ids())`) — a `tailoring` module: (1) `rule (IRONMAN && id:[missing]) { gold beam + sound + notify }` (missing = clog_ids − obtained); (2) `rule (IRONMAN && id:[obtained∩clog]) { quiet highlight, NO beam }`; (3) `apply (IRONMAN && HIDE_OWNED && id:[bank − ALL clog − high_value]) { hidden=true; }` with `#define HIDE_OWNED false`. Hide-owned excludes the WHOLE collection-log (never hide a trophy you own) and high-value items (via `value_index` `{id:value}`; None → nothing high-value). Empty/None account_state → empty module.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_tailor.py`)

```python
from osrs_planner.lootfilter.tailor import emit_tailoring
from osrs_planner.account.state import build_account_state

def test_missing_beam_obtained_dim_and_hide_owned():
    # clog universe {100,200,300}; obtained {200}; bank {200, 400}
    st = build_account_state("ironman", bank_tsv="200\tX\t1\n400\tY\t1\n", clog_obtained={"item:200"})
    out = emit_tailoring(st, clog_ids={100, 200, 300})
    assert "module:tailoring" in out
    assert "id:[100, 300]" in out and "showLootbeam = true;" in out and "notify = true;" in out  # missing beam
    assert "id:[200]" in out                                  # obtained dim
    assert "#define HIDE_OWNED false" in out
    assert "HIDE_OWNED && id:[400]" in out                    # hide-owned excludes ALL clog (200 is clog, kept)

def test_no_account_state_empty():
    assert emit_tailoring(None, clog_ids={1, 2}).strip().endswith("*/")  # just the module header

def test_high_value_owned_not_hidden():
    st = build_account_state("ironman", bank_tsv="400\tY\t1\n", clog_obtained=set())
    out = emit_tailoring(st, clog_ids=set(), value_index={400: 5_000_000})
    assert "id:[400]" not in out                              # valuable owned item never hidden
```

- [ ] **Step 2: Run → fail. Step 3: Implement** (`src/osrs_planner/lootfilter/tailor.py`)

```python
# src/osrs_planner/lootfilter/tailor.py
"""Account tailoring (design §9): beam the collection-log slots you still NEED, dim
the ones you HAVE, optionally hide what you bank. Consumes an already-built
AccountState (counts + clog_obtained); never calls the ingestion itself. The caller
supplies the clog id-set (generate.load_clog_ids)."""
from __future__ import annotations

from osrs_planner.lootfilter.emit import emit_module, emit_rule, IRONMAN, _id_list

_HIGH_VALUE = 100_000  # A grade -> never hide an owned item worth this much

def _ids(keys) -> set[int]:
    return {int(k.split(":")[1]) for k in keys}

def emit_tailoring(account_state, clog_ids, value_index=None) -> str:
    if account_state is None:
        return emit_module("tailoring", "Account tailoring", "")
    clog = set(clog_ids)
    obtained = _ids(account_state.clog_obtained)
    owned = _ids(account_state.counts)
    missing = sorted(clog - obtained)
    have = sorted(clog & obtained)
    value_index = value_index or {}
    hide = sorted(i for i in owned if i not in clog and value_index.get(i, 0) < _HIGH_VALUE)
    lines = ['/*@ define:input:tailoring\nlabel: Hide items already in my bank\ntype: boolean\ngroup: Tailor\n*/\n#define HIDE_OWNED false']
    if missing:
        lines.append(emit_rule(f"{IRONMAN} && {_id_list(missing)}",
            {"hidden": "false", "textColor": "#ffffffff", "backgroundColor": "#ffd8b01a", "borderColor": "#ffffd700",
             "showLootbeam": "true", "lootbeamColor": "#ffffd700", "sound": "3930", "notify": "true", "fontType": "3"}))
    if have:
        lines.append(emit_rule(f"{IRONMAN} && {_id_list(have)}",
            {"textColor": "#66d8b01a", "fontType": "1"}))   # quiet, no beam
    if hide:
        lines.append(emit_rule(f"{IRONMAN} && HIDE_OWNED && {_id_list(hide)}", {"hidden": "true"}, terminal=False))
    return emit_module("tailoring", "Account tailoring", "\n".join(lines))
```

- [ ] **Step 4: Run → pass. Step 5: Commit.**
```bash
git add src/osrs_planner/lootfilter/tailor.py tests/lootfilter/test_tailor.py
git commit -m "loot-filter: account tailoring (missing-clog beam, obtained dim, hide-owned)"
```

---

## Task 8: Generate orchestrator + committed generic artifact + tailored demo

**Files:** Create `src/osrs_planner/lootfilter/generate.py`, `scripts/lootfilter_demo.py`, `tests/lootfilter/test_generate.py`; generate `outputs/gilded-tome-iron.rs2f`

**Interfaces:** `generate.load_clog_ids(data_dir) -> list[int]`; `generate_filter(account_state=None, data_dir=…) -> str` assembling `meta + preamble + settings + tailoring(if account) + trophies + categories + fallback`; `write_filter(path, account_state=None)`.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_generate.py`)

```python
import os
from osrs_planner.lootfilter.generate import generate_filter, load_clog_ids
from osrs_planner.account.state import build_account_state
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_generic_modules_in_order_no_tailoring():
    f = generate_filter()
    for m in ("module:settings", "module:trophies", "module:categories", "module:fallback"):
        assert m in f
    assert "module:tailoring" not in f                        # generic omits tailoring
    assert f.index("module:settings") < f.index("module:trophies") < f.index("module:categories") < f.index("module:fallback")
    assert f.startswith("meta {") and "#define IRONMAN accountType:1" in f

def test_tailored_inserts_tailoring_above_trophies():
    st = build_account_state("ironman", bank_tsv="995\tCoins\t1\n", clog_obtained={"item:4151"})
    f = generate_filter(account_state=st)
    assert "module:tailoring" in f and f.index("module:tailoring") < f.index("module:trophies")

def test_real_clog_ids_load():
    ids = load_clog_ids(os.path.join(REPO, "data"))
    assert len(ids) > 500 and 4151 in ids

def test_tailored_hide_owned_spares_high_value():
    # the high-value guard must be LIVE in the real generate path (not just the unit test)
    import re
    from osrs_planner.lootfilter.generate import load_value_index
    D = os.path.join(REPO, "data")
    vi = load_value_index(D); clog = set(load_clog_ids(D))
    hv = next(i for i in sorted(vi) if vi[i] >= 1_000_000 and i not in clog)   # valuable, non-clog
    lv = next(i for i in sorted(vi) if 0 < vi[i] < 50_000 and i not in clog)   # cheap, non-clog
    st = build_account_state("ironman", bank_tsv=f"{hv}\tH\t1\n{lv}\tL\t1\n", clog_obtained=set())
    m = re.search(r"HIDE_OWNED && (id:\[[0-9, ]+\])", generate_filter(account_state=st))
    assert m, "expected a HIDE_OWNED rule for the cheap item"
    ids = set(m.group(1)[4:-1].replace(" ", "").split(","))
    assert str(lv) in ids and str(hv) not in ids   # cheap hideable; valuable spared
```

- [ ] **Step 2: Run → fail. Step 3: Implement** (`src/osrs_planner/lootfilter/generate.py`)

```python
# src/osrs_planner/lootfilter/generate.py
"""Assemble the full iron .rs2f (design §3/§5). Generic (account_state=None) omits the
tailoring module and is the committed/byte-stable artifact; tailored is account-specific."""
from __future__ import annotations

import json, os
from osrs_planner.lootfilter import emit
from osrs_planner.lootfilter import tailor

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")

def load_clog_ids(data_dir: str = DATA) -> list[int]:
    recs = json.load(open(os.path.join(data_dir, "collection_log.json"), encoding="utf-8"))["records"]
    return sorted({r["item_id"] for r in recs})

def load_value_index(data_dir: str = DATA) -> dict:
    """item_id -> max(GE high price [skip the int-max sentinel], High-Alch), for the
    tailoring hide-owned high-value guard. Reads committed data only (ge_prices.json),
    no overlay import (boundary). `price` is a {high, low, capturedAt} dict."""
    recs = json.load(open(os.path.join(data_dir, "ge_prices.json"), encoding="utf-8"))["records"]
    out = {}
    for r in recs:
        ge = (r.get("price") or {}).get("high") or 0
        if ge >= 2_000_000_000:
            ge = 0
        out[r["item_id"]] = max(ge, r.get("high_alch") or 0)
    return out

def generate_filter(account_state=None, data_dir: str = DATA) -> str:
    clog = load_clog_ids(data_dir)
    parts = [
        emit.emit_meta("Gilded Tome — Iron", "Generated ironman loot filter. Value tiers + collection-log trophies."),
        emit.emit_preamble(),
        emit.emit_settings(),
    ]
    if account_state is not None:  # tailored path: thread the value map so hide-owned spares valuables
        parts.append(tailor.emit_tailoring(account_state, set(clog), value_index=load_value_index(data_dir)))
    parts += [emit.emit_trophies(clog), emit.emit_categories(), emit.emit_fallback()]
    return "\n".join(parts) + "\n"

def write_filter(path: str, account_state=None, data_dir: str = DATA) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_filter(account_state, data_dir))
```

- [ ] **Step 4: Run → pass.** **Step 5: Write `scripts/lootfilter_demo.py`** (regen generic + a tailored sample over the account fixtures):

```python
#!/usr/bin/env python3
"""Regenerate outputs/gilded-tome-iron.rs2f (generic) + print a tailored example."""
import json, os
from osrs_planner.lootfilter.generate import write_filter, generate_filter, load_clog_ids
from osrs_planner.account.state import build_account_state
from osrs_planner.account.temple import parse_temple_clog

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f")
FIX = os.path.join(REPO, "tests", "account", "fixtures")

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_filter(OUT)
    g = generate_filter()
    print(f"generic: {OUT} | bytes {len(g)} | rules {g.count('rule (')}")
    obtained = parse_temple_clog(json.load(open(os.path.join(FIX, "sample_temple.json"), encoding="utf-8")))["obtained"]
    st = build_account_state("ironman", bank_tsv=open(os.path.join(FIX, "sample_bank.tsv"), encoding="utf-8").read(), clog_obtained=obtained)
    t = generate_filter(account_state=st)
    miss = len(set(load_clog_ids()) - {int(k.split(':')[1]) for k in st.clog_obtained})
    print(f"tailored: bytes {len(t)} | has tailoring module: {'module:tailoring' in t} | missing-clog slots beamed: {miss}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Generate + byte-stability test.** Run `venv/bin/python scripts/lootfilter_demo.py` (writes the artifact). Add `tests/lootfilter/test_byte_stable.py`:
```python
import os
from osrs_planner.lootfilter.generate import generate_filter
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
def test_committed_matches_fresh():
    assert open(os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"), encoding="utf-8").read() == generate_filter()
```

- [ ] **Step 7: Run + commit.**
```bash
git add src/osrs_planner/lootfilter/generate.py scripts/lootfilter_demo.py outputs/gilded-tome-iron.rs2f tests/lootfilter/test_generate.py tests/lootfilter/test_byte_stable.py
git commit -m "loot-filter: generator (generic+tailored) + committed artifact + byte-stability"
```

---

## Task 9: Structural validator + golden + final verification

**Files:** Create `data/validate_loot_filter.py`, `tests/lootfilter/test_validate.py`, `tests/lootfilter/test_golden.py`

**Interfaces:** `python data/validate_loot_filter.py` exits 0 on the committed generic artifact, 1 on a structural violation.

- [ ] **Step 1: Write the validator** (`data/validate_loot_filter.py`)

```python
#!/usr/bin/env python3
"""Structural validator for the GENERIC loot filter (design §12): balanced braces +
block comments, colours are 8-hex ARGB, IRON-gating (every rule( and every settings/
trophy apply( references IRONMAN), trophy ids resolve, module order, hide-floor default 0."""
from __future__ import annotations
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
errors = []
def check(c, m):
    if not c: errors.append(m)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default=os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"))
    ap.add_argument("--data", default=os.path.join(REPO, "data"))
    ns = ap.parse_args()
    text = open(ns.filter, encoding="utf-8").read()

    check(text.count("{") == text.count("}"), "unbalanced braces")
    check(text.count("/*") == text.count("*/"), "unbalanced block comments")
    for col in re.findall(r'"(#[0-9a-fA-F]+)"', text):
        check(len(col) == 9, f"colour not 8-hex ARGB: {col}")
    check("#define IRONMAN accountType:1" in text, "IRONMAN macro not defined")
    check(text.count("rule (IRONMAN") == text.count("rule ("), "a rule( is not IRONMAN-gated")
    check(text.count("apply (IRONMAN") == text.count("apply ("), "an apply( is not IRONMAN-gated")
    check("#define HIDE_FLOOR 0" in text, "HIDE_FLOOR default not 0 (would hide by default)")
    # every macro referenced in a condition is #defined; no empty conditions/bodies
    defined = set(re.findall(r"#define (\w+)", text))
    referenced = set()
    for c in re.findall(r"(?:rule|apply) \(([^)]*)\)", text):
        referenced |= set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\b", c))
    check(not (referenced - defined), f"macro(s) referenced but not defined: {sorted(referenced - defined)[:10]}")
    check(not re.search(r"(?:rule|apply) \(\)", text), "a rule/apply has an empty condition")
    check(not re.search(r"\)\s*\{\s*\}", text), "a rule/apply has an empty body")
    order = ["module:settings", "module:trophies", "module:categories", "module:fallback"]
    idxs = [text.find(m) for m in order]
    check(all(i >= 0 for i in idxs) and idxs == sorted(idxs), f"modules missing/out of order: {idxs}")
    idict = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "item_dictionary.json"), encoding="utf-8"))["records"]}
    clog = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "collection_log.json"), encoding="utf-8"))["records"]}
    for m in re.findall(r"id:\[([0-9, ]+)\]", text):
        for tok in m.split(","):
            iid = int(tok); check(iid in idict or iid in clog, f"trophy id unresolved: {iid}")
    if errors:
        print(f"LOOT-FILTER VALIDATION FAILED -- {len(errors)} violation(s):")
        for e in errors[:50]: print("  -", e)
        return 1
    print(f"LOOT-FILTER VALIDATION PASSED -- rules {text.count('rule (')}, bytes {len(text)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Validator + golden tests.**

`tests/lootfilter/test_validate.py`:
```python
import os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
V = os.path.join(REPO, "data", "validate_loot_filter.py")
def test_validator_passes_committed():
    r = subprocess.run([sys.executable, V], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
def test_validator_fails_unbalanced(tmp_path):
    p = tmp_path / "bad.rs2f"; p.write_text('meta { name = "x";')
    assert subprocess.run([sys.executable, V, "--filter", str(p)], capture_output=True, text=True).returncode == 1
```
`tests/lootfilter/test_golden.py`:
```python
import os
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
F = open(os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"), encoding="utf-8").read()
def test_mithril_gear_blue():
    assert '"Mithril platebody"' in F and "#ff4169e1" in F
def test_no_fake_items():
    assert "Bronze ore" not in F and "Rune bar" not in F and "Rune *" not in F
def test_trophy_and_ladder_and_floor():
    assert "module:trophies" in F and "value:>=10000000" in F and "#define HIDE_FLOOR 0" in F
def test_iron_gated_generic_has_no_tailoring():
    assert "accountType:1" in F and F.startswith("meta {") and "module:tailoring" not in F
```

- [ ] **Step 3: Run validator + full verification.**
```bash
venv/bin/python data/validate_loot_filter.py
venv/bin/python -m pytest tests/ -q
for v in validate_income validate_cost validate_kg validate_drop_rate; do venv/bin/python data/$v.py >/dev/null && echo "$v ok"; done
venv/bin/python scripts/lootfilter_demo.py && git diff --quiet outputs/gilded-tome-iron.rs2f && echo "byte-stable"
```
Expected: validator exit 0; full suite passes (existing + new lootfilter tests); 4 existing validators exit 0; artifact byte-stable.

- [ ] **Step 4: Commit.**
```bash
git add data/validate_loot_filter.py tests/lootfilter/test_validate.py tests/lootfilter/test_golden.py
git commit -m "loot-filter: structural validator + golden set + final verification"
```

---

## Deferred (spec §13 — do NOT build)
Granular per-content supply curation; rarity sub-ranking; main-account variant; custom `.wav` pack; per-category min-value knobs; live filterscape publish; banked-XP-aware value.
