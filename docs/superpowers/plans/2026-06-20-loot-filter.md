# Loot-Filter Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a genuinely-impressive ironman RuneLite Loot-Filters (`.rs2f`) filter from our committed data — a two-axis visual language (hue = identity, emphasis = value) with a collection-log trophy layer.

**Architecture:** A new independent overlay `src/osrs_planner/lootfilter/` that ASSEMBLES a modular `.rs2f` filter from committed config (`palette.py` colours/grades + `categories.py` name-patterns) + data (`collection_log.json` trophy ids, `item_dictionary.json` for id resolution), via an `emit.py` text emitter and a `generate.py` orchestrator, writing a committed `outputs/gilded-tome-iron.rs2f`. Gated by a structural `data/validate_loot_filter.py`. It does NOT import engine/cost/income (item `value` is computed by the plugin at runtime); the KG is untouched.

**Tech Stack:** Python 3 (stdlib `json`/`re`/`os`), pytest. Output target = the `riktenx/loot-filters` rs2f DSL.

## Global Constraints

- **rs2f grammar (verified from the plugin's `filter-lang.md` + real filters):** `meta { name = "…"; description = "…"; }`; `rule (<conds>) { <prop> = <val>; }` (terminal) / `apply (<conds>) { … }` (non-terminal); conditions `id:995`/`id:[995,996]`, `name:"x"`/`name:["a","b"]`/wildcards `"*godsword"`, `value:>=N`/`havalue:>=N`/`gevalue:>=N` (ops `> < >= <= ==`, underscores allowed in ints), `accountType:1`, `ownership:0|1|2|3`, joined with `&& || !`; style props `textColor`/`backgroundColor`/`borderColor`/`lootbeamColor`/`menuTextColor`/`textAccentColor` (8-hex ARGB `"#aarrggbb"`), `showLootbeam`/`showValue`/`showDespawn`/`notify`/`hidden`/`hideOverlay`/`highlightTile` (bool), `fontType` (1/2/3), `textAccent` (1/2/3/4), `menuSort` (int), `sound` (int cache-id or `"x.wav"`), `icon` (`Item(<id>)`); `#define NAME value` macros (multi-line end lines with `\`). Module annotations (filterscape): `/*@ define:module:<id>\nname: …\n*/` and `/*@ define:input:<module>\nlabel: …\ntype: boolean\ngroup: …\n*/`.
- **Colours are 8-hex ARGB** `"#aarrggbb"` (alpha `ff` = opaque), matching Storn's filter.
- **The whole filter is `accountType:1`-gated** via a `#define IRON accountType:1` macro prepended to every styling rule's conditions, so it is inert on a non-iron account.
- **General tiering uses `value` (max GE/HA), GE-inclusive** (the plugin computes it). `havalue` only for alch-specific calls.
- **Module/evaluation order:** `settings` → `trophies` → `categories` → `fallback` (specific wins over general).
- **Determinism:** all id-lists sorted; modules emitted in fixed order; re-running `generate.py` is byte-stable (a CI gate).
- **Licensing:** the rs2f format is the plugin's (free to emit). Storn's/Joe's filters are all-rights-reserved — design reference ONLY. All module names, lists, and colours here are our own / Gilded-Tome-branded.
- **Boundary:** `lootfilter/` imports only stdlib (+ may read `data/*.json`); it must NOT import `osrs_planner.engine` / `.cost` / `.income`; the KG (`kg/*.json`) is untouched.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/osrs_planner/lootfilter/__init__.py` | package marker |
| `src/osrs_planner/lootfilter/palette.py` | the visual language: `VALUE_GRADES` (SS→E thresholds + emphasis), `MATERIAL_COLORS`/`RUNE_COLORS`/`GEM_COLORS`/`LOG_COLORS` maps, `TROPHY_GRADES`. Pure data. |
| `src/osrs_planner/lootfilter/categories.py` | `CATEGORIES` (name-pattern → category + hue) + `categorize(name)` matcher (for tests). Pure data + matcher. |
| `src/osrs_planner/lootfilter/emit.py` | rs2f text emitter: `meta`, a rule/apply builder, a graded-ladder builder, module wrappers. |
| `src/osrs_planner/lootfilter/generate.py` | orchestrator `generate_filter(account_state=None) -> str` + `write_filter()`. |
| `data/validate_loot_filter.py` | committed structural validator. |
| `outputs/gilded-tome-iron.rs2f` | committed generated artifact (byte-stable). |
| `scripts/lootfilter_demo.py` | regenerates + prints a summary. |
| `tests/lootfilter/test_*.py` | per-unit tests. |

---

## Task 1: Scaffold + palette (the visual language) + boundary

**Files:**
- Create: `src/osrs_planner/lootfilter/__init__.py`, `src/osrs_planner/lootfilter/palette.py`, `tests/lootfilter/__init__.py`, `tests/lootfilter/test_palette.py`, `tests/lootfilter/test_boundary.py`

**Interfaces:**
- Produces: `VALUE_GRADES: list[tuple[str, int, dict]]` ordered SS→E, each `(grade, min_value, emphasis)` where `emphasis` has keys `beam: bool`, `sound: bool`, `border: bool`, `fontType: int`, `accent: int`, `bg_alpha: str` (2-hex). `style_for(hue_hex, grade) -> dict[str,str]` returns rs2f style props (textColor/backgroundColor/etc.) for an item-hue at a grade. `TROPHY_GRADES` same shape with the gold/bronze ramp. Colour maps are `dict[str,str]` name→`"#aarrggbb"`.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_palette.py`)

```python
from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for, TROPHY_GRADES, MATERIAL_COLORS

def test_grades_descend_SS_to_E():
    names = [g[0] for g in VALUE_GRADES]
    assert names == ["SS", "S", "A", "B", "C", "D", "E"]
    mins = [g[1] for g in VALUE_GRADES]
    assert mins == [10_000_000, 1_000_000, 100_000, 10_000, 1_000, 100, 0]

def test_emphasis_escalates_beam_at_S_sound_at_A():
    emph = {g[0]: g[2] for g in VALUE_GRADES}
    assert emph["SS"]["beam"] and emph["S"]["beam"] and not emph["A"]["beam"]
    assert emph["SS"]["sound"] and emph["A"]["sound"] and not emph["B"]["sound"]

def test_style_for_renders_hue_at_grade():
    s = style_for("#ff4169e1", "S")  # mithril blue at grade S -> beam in that hue
    assert s["textColor"] == "#ff4169e1"
    assert s["showLootbeam"] == "true" and s["lootbeamColor"] == "#ff4169e1"

def test_material_colors_present():
    for m in ("bronze", "iron", "steel", "black", "mithril", "adamant", "rune", "dragon"):
        assert MATERIAL_COLORS[m].startswith("#ff") and len(MATERIAL_COLORS[m]) == 9

def test_trophy_uses_gold_bronze_and_always_beams():
    grades = {g[0]: g[2] for g in TROPHY_GRADES}
    assert all(grades[g]["beam"] and grades[g]["sound"] for g in ("SS", "S", "A", "B", "C"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/lootfilter/test_palette.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation** (`src/osrs_planner/lootfilter/palette.py`)

```python
# src/osrs_planner/lootfilter/palette.py
"""The visual language: value grades (emphasis ladder) + item material/type colours.

Two axes (design §6): HUE = identity (these colour maps), EMPHASIS = value (the
grade ladder). style_for(hue, grade) renders the grade's emphasis IN the item's
hue. Colours are 8-hex ARGB. Modelled on Storn's palette; authored ourselves."""
from __future__ import annotations

# (grade, min `value`, emphasis). Escalation: beam at S+, sound at A+ (design §7).
VALUE_GRADES = [
    ("SS", 10_000_000, {"beam": True,  "sound": True,  "border": True,  "fontType": 3, "accent": 3, "bg_alpha": "ff"}),
    ("S",   1_000_000, {"beam": True,  "sound": True,  "border": True,  "fontType": 3, "accent": 3, "bg_alpha": "ff"}),
    ("A",     100_000, {"beam": False, "sound": True,  "border": False, "fontType": 2, "accent": 3, "bg_alpha": "cc"}),
    ("B",      10_000, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 3, "bg_alpha": "99"}),
    ("C",       1_000, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 3, "bg_alpha": "33"}),
    ("D",         100, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 1, "bg_alpha": "00"}),
    ("E",           0, {"beam": False, "sound": False, "border": False, "fontType": 1, "accent": 1, "bg_alpha": "00"}),
]

# Trophy (collection-log) ramp: gold/bronze, ALWAYS beam + sound (design §8).
_GOLD, _BRONZE = "#ffd8b01a", "#ffbc6025"
TROPHY_GRADES = [
    ("SS", 10_000_000, {"hue": "#ffff0000", "beam": True, "sound": True, "border": True, "fontType": 3, "accent": 3, "bg_alpha": "ff"}),
    ("S",   1_000_000, {"hue": _GOLD,       "beam": True, "sound": True, "border": True, "fontType": 3, "accent": 3, "bg_alpha": "ff"}),
    ("A",     100_000, {"hue": _BRONZE,     "beam": True, "sound": True, "border": True, "fontType": 2, "accent": 3, "bg_alpha": "cc"}),
    ("B",      10_000, {"hue": _BRONZE,     "beam": True, "sound": True, "border": True, "fontType": 2, "accent": 3, "bg_alpha": "99"}),
    ("C",           0, {"hue": _BRONZE,     "beam": True, "sound": True, "border": True, "fontType": 1, "accent": 3, "bg_alpha": "33"}),
]

def _argb(alpha2: str, hue: str) -> str:
    """Recolour `hue` (#aarrggbb) with a new 2-hex alpha for a tinted background."""
    return "#" + alpha2 + hue[3:]

def style_for(hue: str, grade: str) -> dict[str, str]:
    """rs2f style props for an item of colour `hue` at value `grade` (design §6/§7)."""
    emph = next(e for g, _m, e in VALUE_GRADES if g == grade)
    s: dict[str, str] = {"textColor": hue, "fontType": str(emph["fontType"]), "textAccent": str(emph["accent"])}
    if grade == "E":
        s["textColor"] = "#66" + hue[3:]  # faded
        s["menuSort"] = "-10000"
    if emph["bg_alpha"] not in ("00", "ff"):
        s["backgroundColor"] = _argb(emph["bg_alpha"], hue)
    if emph["border"]:
        s["borderColor"] = hue
        s["backgroundColor"] = "#ffffffff"
    if emph["beam"]:
        s["showLootbeam"] = "true"; s["lootbeamColor"] = hue
    if emph["sound"]:
        s["sound"] = "3925"  # plugin built-in cache sound id (design §11; tune later)
    return s

# Material/type colour maps (design §9). Metals carry the gear leverage.
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

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/lootfilter/test_palette.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Write the boundary test** (`tests/lootfilter/test_boundary.py`)

```python
import ast, os
PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "src", "osrs_planner", "lootfilter")

def test_lootfilter_never_imports_engine_cost_income():
    offenders = []
    for fn in os.listdir(PKG):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(PKG, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for m in mods:
                if any(b in (m or "") for b in ("osrs_planner.engine", "osrs_planner.cost", "osrs_planner.income")):
                    offenders.append(f"{fn}: {m}")
    assert not offenders, f"lootfilter imports a forbidden overlay: {offenders}"
```

- [ ] **Step 6: Run boundary test + commit**

Run: `venv/bin/python -m pytest tests/lootfilter/ -v` (PASS)
```bash
git add src/osrs_planner/lootfilter/__init__.py src/osrs_planner/lootfilter/palette.py tests/lootfilter/
git commit -m "loot-filter: palette (visual language: grades + material colours) + boundary"
```

---

## Task 2: Categories (name-pattern matcher)

**Files:**
- Create: `src/osrs_planner/lootfilter/categories.py`, `tests/lootfilter/test_categories.py`

**Interfaces:**
- Consumes: `palette` colour maps.
- Produces: `CATEGORIES: list[dict]` each `{id, name, patterns: list[str], hue: str, show_default: bool}` (patterns are rs2f `name:` globs, hue is `#aarrggbb`); `categorize(item_name) -> dict | None` (the first matching category, or None → fallback). Metal/rune/gem/log items resolve to their material hue.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_categories.py`)

```python
from osrs_planner.lootfilter.categories import categorize, CATEGORIES
from osrs_planner.lootfilter.palette import MATERIAL_COLORS, RUNE_COLORS

def test_mithril_gear_is_metal_mithril_blue():
    c = categorize("Mithril platebody")
    assert c and c["id"] == "gear" and c["hue"] == MATERIAL_COLORS["mithril"]

def test_dragon_gear_metal():
    assert categorize("Dragon scimitar")["hue"] == MATERIAL_COLORS["dragon"]

def test_fire_rune_is_rune_red():
    c = categorize("Fire rune")
    assert c and c["id"] == "runes" and c["hue"] == RUNE_COLORS["fire"]

def test_grimy_herb_is_herb_green():
    c = categorize("Grimy ranarr weed")
    assert c and c["id"] == "herbs"

def test_non_resource_returns_none():
    assert categorize("Twisted bow") is None  # -> fallback value ladder

def test_bar_is_not_misread_as_gear():
    # "Mithril bar" is a bar, not gear; it still gets the mithril hue but category 'bars'
    c = categorize("Mithril bar")
    assert c and c["id"] == "bars" and c["hue"] == MATERIAL_COLORS["mithril"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/lootfilter/test_categories.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation** (`src/osrs_planner/lootfilter/categories.py`)

```python
# src/osrs_planner/lootfilter/categories.py
"""Name-pattern -> category + item hue (design §9). OSRS names are systematic, so
these patterns reliably classify the big mechanical groups. NOT granular per-content
curation (deferred). categorize() is the matcher used by tests + the emitter."""
from __future__ import annotations

import re

from osrs_planner.lootfilter.palette import MATERIAL_COLORS, RUNE_COLORS, GEM_COLORS, LOG_COLORS

_METALS = list(MATERIAL_COLORS)         # bronze..dragon
_GEAR_WORDS = ("platebody", "platelegs", "plateskirt", "full helm", "med helm", "chainbody",
               "sq shield", "kiteshield", "sword", "longsword", "dagger", "scimitar", "mace",
               "warhammer", "battleaxe", "2h sword", "spear", "hasta", "claws", "boots", "axe", "pickaxe")

def _metal_in(name_lc: str) -> str | None:
    for m in _METALS:
        if name_lc.startswith(m + " "):
            return m
    return None

def categorize(name: str):
    """Return the first matching category dict, or None (-> fallback ladder)."""
    n = name.strip().lower()
    metal = _metal_in(n)
    if metal:
        if n.endswith(" bar"):
            return {"id": "bars", "name": "Bars", "patterns": [f"{metal.title()} bar"], "hue": MATERIAL_COLORS[metal], "show_default": True}
        if n.endswith(" ore"):
            return {"id": "ores", "name": "Ores", "patterns": [f"{metal.title()} ore"], "hue": MATERIAL_COLORS[metal], "show_default": True}
        if any(w in n for w in _GEAR_WORDS):
            return {"id": "gear", "name": "Gear", "patterns": [f"{metal.title()} *"], "hue": MATERIAL_COLORS[metal], "show_default": True}
    if n.endswith(" rune"):
        elem = n[:-5]
        if elem in RUNE_COLORS:
            return {"id": "runes", "name": "Runes", "patterns": [f"{elem.title()} rune"], "hue": RUNE_COLORS[elem], "show_default": True}
    if n.startswith("grimy ") or (n.startswith("clean ")):
        return {"id": "herbs", "name": "Herbs", "patterns": ["Grimy *", "Clean *"], "hue": "#ff2e8b57", "show_default": True}
    if n.endswith(" seed") or n.endswith(" seedling"):
        return {"id": "seeds", "name": "Seeds", "patterns": ["* seed", "* seedling"], "hue": "#ff00e024", "show_default": True}
    if n.endswith(" logs"):
        tree = n[:-5]
        return {"id": "logs", "name": "Logs", "patterns": [f"{tree.title()} logs", "Logs"], "hue": LOG_COLORS.get(tree, "#ff9c6b3f"), "show_default": True}
    if n.startswith("uncut "):
        gem = n[6:]
        if gem in GEM_COLORS:
            return {"id": "gems", "name": "Gems", "patterns": [f"Uncut {gem}"], "hue": GEM_COLORS[gem], "show_default": True}
    if n.endswith(" bones") or n.endswith(" ashes"):
        return {"id": "bones", "name": "Bones & Ashes", "patterns": ["* bones", "* ashes"], "hue": "#ffe8e0d0", "show_default": True}
    return None

# The committed category table the emitter iterates (deterministic order, specific
# before generic). Each entry's `patterns` are emitted as rs2f name: globs.
CATEGORIES = [
    {"id": "gear",  "name": "Gear (by metal)", "by": "metal"},
    {"id": "bars",  "name": "Bars",  "by": "metal-bar"},
    {"id": "ores",  "name": "Ores",  "by": "metal-ore"},
    {"id": "runes", "name": "Runes", "by": "rune"},
    {"id": "gems",  "name": "Gems",  "by": "gem"},
    {"id": "logs",  "name": "Logs",  "by": "log"},
    {"id": "herbs", "name": "Herbs", "patterns": ["Grimy *", "Clean *"], "hue": "#ff2e8b57"},
    {"id": "seeds", "name": "Seeds", "patterns": ["* seed", "* seedling"], "hue": "#ff00e024"},
    {"id": "bones", "name": "Bones & Ashes", "patterns": ["* bones", "* ashes"], "hue": "#ffe8e0d0"},
]
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/lootfilter/test_categories.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/categories.py tests/lootfilter/test_categories.py
git commit -m "loot-filter: name-pattern categoriser + item-hue mapping"
```

---

## Task 3: emit core — meta, rule builder, value-grade fallback ladder

**Files:**
- Create: `src/osrs_planner/lootfilter/emit.py`, `tests/lootfilter/test_emit.py`

**Interfaces:**
- Consumes: `palette.VALUE_GRADES`, `palette.style_for`.
- Produces: `emit_meta(name, desc) -> str`; `emit_rule(conds: str, style: dict, terminal=True) -> str` (a `rule`/`apply` line); `style_str(style: dict) -> str` (the `{ k = v; }` body); `emit_module(module_id, name, body) -> str` (wraps with the `/*@ define:module */` header); `emit_fallback() -> str` (the SS→E ladder gated `IRON`). `IRON = "accountType:1"` and `#define IRON accountType:1` is emitted once in the preamble by generate.py.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_emit.py`)

```python
from osrs_planner.lootfilter.emit import emit_meta, emit_rule, style_str, emit_fallback

def test_meta():
    m = emit_meta("Gilded Tome — Iron", "x")
    assert m.strip().startswith("meta {") and 'name = "Gilded Tome — Iron";' in m

def test_style_str_props():
    s = style_str({"textColor": "#ff4169e1", "showLootbeam": "true"})
    assert s == '{ textColor = "#ff4169e1"; showLootbeam = true; }'  # bools unquoted, colours quoted

def test_emit_rule_terminal_vs_apply():
    assert emit_rule("IRON && value:>=1000", {"textColor": "#ffffffff"}).startswith("rule (")
    assert emit_rule("ownership:2", {"hidden": "true"}, terminal=False).startswith("apply (")

def test_fallback_has_seven_graded_rules_iron_gated():
    fb = emit_fallback()
    assert fb.count("rule (") == 7
    assert "value:>=10000000" in fb and "value:>=0" in fb
    assert fb.count("IRON &&") == 7  # every fallback rule is iron-gated
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/lootfilter/test_emit.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation** (`src/osrs_planner/lootfilter/emit.py`)

```python
# src/osrs_planner/lootfilter/emit.py
"""rs2f text emitter (design §4/§5). Bools are bare (true/false), ints bare,
colours + sound .wav names quoted; cache-id sounds are bare ints. Every styling
rule is iron-gated via the IRON macro."""
from __future__ import annotations

from osrs_planner.lootfilter.palette import VALUE_GRADES, style_for

IRON = "IRON"  # the rs2f MACRO name (defined once via emit_preamble: #define IRON accountType:1)
_BARE = {"true", "false"}  # already-bare values

def style_str(style: dict) -> str:
    parts = []
    for k, v in style.items():
        v = str(v)
        if v in _BARE or v.lstrip("-").isdigit():
            parts.append(f"{k} = {v};")          # bool / int -> bare
        else:
            parts.append(f'{k} = "{v}";')        # colour / string -> quoted
    return "{ " + " ".join(parts) + " }"

def emit_rule(conds: str, style: dict, terminal: bool = True) -> str:
    kw = "rule" if terminal else "apply"
    return f"{kw} ({conds}) {style_str(style)}"

def emit_meta(name: str, desc: str) -> str:
    return f'meta {{\n    name = "{name}";\n    description = "{desc}";\n}}\n'

def emit_module(module_id: str, name: str, body: str) -> str:
    return f"/*@ define:module:{module_id}\nname: {name}\n*/\n{body}\n"

def emit_fallback() -> str:
    lines = []
    for grade, minv, _emph in VALUE_GRADES:
        # the fallback ladder is uncoloured (white hue) -> pure value emphasis
        style = style_for("#ffffffff", grade)
        lines.append(emit_rule(f"{IRON} && value:>={minv}", style))
    return emit_module("fallback", "Value fallback (SS→E)", "\n".join(lines))
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/lootfilter/test_emit.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_emit.py
git commit -m "loot-filter: rs2f emitter core (meta, rule builder, value fallback)"
```

---

## Task 4: Trophy module (collection-log id-list, never-hide)

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add `emit_trophies`)
- Test: `tests/lootfilter/test_trophies.py`

**Interfaces:**
- Consumes: `data/collection_log.json` (item_ids), `palette.TROPHY_GRADES`.
- Produces: `emit_trophies(clog_item_ids: list[int]) -> str` — a `trophies` module with (1) a non-terminal `apply (IRON && id:[…]) { hidden = false; }` never-hide guard, then (2) the SS→C trophy ladder `rule (IRON && id:[…] && value:>=…) { gold/bronze beam+sound }`. ids sorted.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_trophies.py`)

```python
from osrs_planner.lootfilter.emit import emit_trophies

def test_trophies_never_hide_and_graded():
    out = emit_trophies([4151, 11920, 995])
    assert "apply (" in out and "hidden = false;" in out       # never-hide guard
    assert "id:[995, 4151, 11920]" in out                       # sorted id-list
    assert "showLootbeam = true;" in out and "value:>=10000000" in out
    assert "IRON &&" in out                                     # iron-gated via the macro

def test_empty_clog_safe():
    assert "module:trophies" in emit_trophies([])
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/lootfilter/test_trophies.py -v`
Expected: FAIL (`emit_trophies` undefined).

- [ ] **Step 3: Implement `emit_trophies` in `emit.py`**

```python
from osrs_planner.lootfilter.palette import TROPHY_GRADES  # add to imports

def _id_list(ids) -> str:
    return "id:[" + ", ".join(str(i) for i in sorted(set(ids))) + "]"

def _trophy_style(emph: dict) -> dict:
    s = {"textColor": "#ffffffff", "backgroundColor": "#ff" + emph["hue"][3:],
         "borderColor": emph["hue"], "fontType": str(emph["fontType"]),
         "textAccent": str(emph["accent"]), "showLootbeam": "true",
         "lootbeamColor": emph["hue"], "sound": "3930"}
    return s

def emit_trophies(clog_item_ids) -> str:
    if not clog_item_ids:
        return emit_module("trophies", "Collection-log trophies", "")
    idl = _id_list(clog_item_ids)
    lines = [emit_rule(f"{IRON} && {idl}", {"hidden": "false"}, terminal=False)]  # never-hide
    for grade, minv, emph in TROPHY_GRADES:
        lines.append(emit_rule(f"{IRON} && {idl} && value:>={minv}", _trophy_style(emph)))
    return emit_module("trophies", "Collection-log trophies", "\n".join(lines))
```

- [ ] **Step 4: Run + commit**

Run: `venv/bin/python -m pytest tests/lootfilter/test_trophies.py -v` (PASS)
```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_trophies.py
git commit -m "loot-filter: collection-log trophy module (gold/bronze, never-hide)"
```

---

## Task 5: Category modules (name-pattern, hue × grade)

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add `emit_categories`)
- Modify: `src/osrs_planner/lootfilter/categories.py` (add `category_rules()` yielding (id, name, patterns, hue))
- Test: `tests/lootfilter/test_emit_categories.py`

**Interfaces:**
- Produces: `categories.category_rules() -> list[tuple[str,str,list[str],str]]` (id, display name, rs2f name-patterns, hue) — expands metal/rune/gem/log maps into concrete pattern groups. `emit.emit_categories() -> str` — a `categories` module; per category, a graded ladder `rule (IRON && name:[patterns] && value:>=…) { style_for(hue, grade) }`.

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_emit_categories.py`)

```python
from osrs_planner.lootfilter.emit import emit_categories
from osrs_planner.lootfilter.categories import category_rules

def test_category_rules_expand_metals_and_runes():
    rules = {r[0] + ":" + r[3] for r in category_rules()}
    assert any(r.startswith("gear:") for r in rules)
    # mithril gear hue present
    assert any("#ff4169e1" in r for r in rules)

def test_emit_categories_has_mithril_blue_and_fire_red():
    out = emit_categories()
    assert 'name:["Mithril *"]' in out and "#ff4169e1" in out      # mithril gear blue
    assert 'name:["Fire rune"]' in out and "#ffff4500" in out       # fire rune red
    assert out.count("module:categories") == 1
    assert "IRON &&" in out                                         # iron-gated via the macro
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/lootfilter/test_emit_categories.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `category_rules()` + `emit_categories()`**

In `categories.py`:
```python
def category_rules():
    """Expand the colour maps into concrete (id, name, patterns, hue) groups."""
    out = []
    for metal, hue in MATERIAL_COLORS.items():
        out.append(("gear", f"{metal.title()} gear", [f"{metal.title()} *"], hue))
        out.append(("bars", f"{metal.title()} bar", [f"{metal.title()} bar"], hue))
        out.append(("ores", f"{metal.title()} ore", [f"{metal.title()} ore"], hue))
    for elem, hue in RUNE_COLORS.items():
        out.append(("runes", f"{elem.title()} rune", [f"{elem.title()} rune"], hue))
    for gem, hue in GEM_COLORS.items():
        out.append(("gems", f"Uncut {gem}", [f"Uncut {gem}"], hue))
    for tree, hue in LOG_COLORS.items():
        out.append(("logs", f"{tree.title()} logs", [f"{tree.title()} logs"], hue))
    out.append(("herbs", "Herbs", ["Grimy *", "Clean *"], "#ff2e8b57"))
    out.append(("seeds", "Seeds", ["* seed", "* seedling"], "#ff00e024"))
    out.append(("bones", "Bones & ashes", ["* bones", "* ashes"], "#ffe8e0d0"))
    return out
```
In `emit.py`:
```python
from osrs_planner.lootfilter.categories import category_rules  # add to imports

def _name_list(patterns) -> str:
    return "name:[" + ", ".join(f'"{p}"' for p in patterns) + "]"

def emit_categories() -> str:
    lines = []
    for _cid, _name, patterns, hue in category_rules():
        nl = _name_list(patterns)
        for grade, minv, _emph in VALUE_GRADES:
            lines.append(emit_rule(f"{IRON} && {nl} && value:>={minv}", style_for(hue, grade)))
    return emit_module("categories", "Categories (by material/type)", "\n".join(lines))
```

- [ ] **Step 4: Run + commit**

Run: `venv/bin/python -m pytest tests/lootfilter/ -v` (all PASS)
```bash
git add src/osrs_planner/lootfilter/emit.py src/osrs_planner/lootfilter/categories.py tests/lootfilter/test_emit_categories.py
git commit -m "loot-filter: category modules (item-hue x value-grade)"
```

---

## Task 6: Settings module + the account-state seam + generate orchestrator

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add `emit_settings`, `emit_preamble`)
- Create: `src/osrs_planner/lootfilter/generate.py`
- Test: `tests/lootfilter/test_generate.py`

**Interfaces:**
- Produces: `emit.emit_preamble() -> str` (the `#define IRON accountType:1` + any colour macros); `emit.emit_settings() -> str` (a `settings` module with `/*@ define:input */` toggles: show world-spawns, show unowned, despawn, value display — each compiling to an `apply` guard). `generate.generate_filter(account_state=None) -> str` assembles `meta + preamble + settings + trophies + categories + fallback`; `generate.load_clog_ids(data_dir) -> list[int]`; `generate.write_filter(path, account_state=None)`. **`account_state` is the wired-unused seam** (assigned to `_`).

- [ ] **Step 1: Write the failing test** (`tests/lootfilter/test_generate.py`)

```python
import os
from osrs_planner.lootfilter.generate import generate_filter, load_clog_ids
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_generate_has_all_modules_in_order():
    f = generate_filter()
    for mod in ("module:settings", "module:trophies", "module:categories", "module:fallback"):
        assert mod in f
    # order: settings < trophies < categories < fallback
    assert f.index("module:settings") < f.index("module:trophies") < f.index("module:categories") < f.index("module:fallback")
    assert f.startswith("meta {") and "#define IRON accountType:1" in f

def test_account_state_seam_accepted_and_ignored():
    a = generate_filter(account_state=None)
    b = generate_filter(account_state={"levels": {"skill:crafting": 99}})
    assert a == b  # v1 ignores it (seam)

def test_real_clog_ids_load_and_appear():
    ids = load_clog_ids(os.path.join(REPO, "data"))
    assert len(ids) > 500 and 4151 in ids  # Abyssal whip is a clog item
    assert f"id:[" in generate_filter()
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/lootfilter/test_generate.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `emit_settings`/`emit_preamble` + `generate.py`**

In `emit.py`:
```python
def emit_preamble() -> str:
    return "#define IRON accountType:1\n"

def emit_settings() -> str:
    body = "\n".join([
        '/*@ define:input:settings\nlabel: Show world spawns\ntype: boolean\ngroup: Show\n*/\n#define SHOW_WORLD_SPAWNS true',
        "apply (!SHOW_WORLD_SPAWNS && ownership:0) { hidden = true; }",
        '/*@ define:input:settings\nlabel: Show unowned drops\ntype: boolean\ngroup: Show\n*/\n#define SHOW_UNOWNED false',
        "apply (!SHOW_UNOWNED && ownership:2) { hidden = true; }",
        '/*@ define:input:settings\nlabel: Despawn timer\ntype: boolean\ngroup: Show\n*/\n#define SHOW_DESPAWN true',
        "apply (SHOW_DESPAWN) { showDespawn = true; }",
    ])
    return emit_module("settings", "Settings", body)
```
Create `generate.py`:
```python
# src/osrs_planner/lootfilter/generate.py
"""Assemble the full iron .rs2f filter (design §3/§5). account_state is the wired-
unused v2 tailoring seam."""
from __future__ import annotations

import json
import os

from osrs_planner.lootfilter import emit

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")

def load_clog_ids(data_dir: str = DATA) -> list[int]:
    recs = json.load(open(os.path.join(data_dir, "collection_log.json"), encoding="utf-8"))["records"]
    return sorted({r["item_id"] for r in recs})

def generate_filter(account_state=None, data_dir: str = DATA) -> str:
    _ = account_state  # SEAM: wired, unused in v1 (v2 tailoring). Do not remove.
    clog = load_clog_ids(data_dir)
    parts = [
        emit.emit_meta("Gilded Tome — Iron",
                       "Generated ironman loot filter. Value tiers + collection-log trophies."),
        emit.emit_preamble(),
        emit.emit_settings(),
        emit.emit_trophies(clog),
        emit.emit_categories(),
        emit.emit_fallback(),
    ]
    return "\n".join(parts) + "\n"

def write_filter(path: str, account_state=None, data_dir: str = DATA) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_filter(account_state, data_dir))
```

- [ ] **Step 4: Run + commit**

Run: `venv/bin/python -m pytest tests/lootfilter/ -v` (all PASS)
```bash
git add src/osrs_planner/lootfilter/emit.py src/osrs_planner/lootfilter/generate.py tests/lootfilter/test_generate.py
git commit -m "loot-filter: settings module + account-state seam + generator"
```

---

## Task 7: Emit the committed artifact + demo + byte-stability

**Files:**
- Create (by running): `outputs/gilded-tome-iron.rs2f`, `scripts/lootfilter_demo.py`
- Test: `tests/lootfilter/test_byte_stable.py`

- [ ] **Step 1: Write `scripts/lootfilter_demo.py`**

```python
#!/usr/bin/env python3
"""Regenerate outputs/gilded-tome-iron.rs2f and print a summary."""
import os
from osrs_planner.lootfilter.generate import write_filter, generate_filter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f")

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_filter(OUT)
    f = generate_filter()
    print(f"wrote {OUT}")
    print(f"  bytes: {len(f)} | rules: {f.count('rule (')} | applies: {f.count('apply (')}")
    print(f"  modules: settings, trophies, categories, fallback")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the committed artifact**

Run: `venv/bin/python scripts/lootfilter_demo.py`
Expected: writes `outputs/gilded-tome-iron.rs2f`, prints a summary (rules > 100).
Eyeball the file: `meta {` header, `#define IRON accountType:1`, the four modules, mithril-blue gear rules, the trophy id-list, the SS→E fallback.

- [ ] **Step 3: Byte-stability test** (`tests/lootfilter/test_byte_stable.py`)

```python
import os
from osrs_planner.lootfilter.generate import generate_filter
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_committed_artifact_matches_fresh_generation():
    committed = open(os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"), encoding="utf-8").read()
    assert committed == generate_filter()  # re-gen is byte-identical
```

- [ ] **Step 4: Run + commit**

Run: `venv/bin/python -m pytest tests/lootfilter/test_byte_stable.py -v` (PASS)
```bash
git add scripts/lootfilter_demo.py outputs/gilded-tome-iron.rs2f tests/lootfilter/test_byte_stable.py
git commit -m "loot-filter: committed iron filter artifact + demo + byte-stability"
```

---

## Task 8: Structural validator + golden + final verification

**Files:**
- Create: `data/validate_loot_filter.py`, `tests/lootfilter/test_validate.py`, `tests/lootfilter/test_golden.py`

**Interfaces:**
- Produces: `python data/validate_loot_filter.py` exits 0 on the committed artifact, 1 on a structural violation.

- [ ] **Step 1: Write the validator** (`data/validate_loot_filter.py`)

```python
#!/usr/bin/env python3
"""Structural validator for the generated loot filter (design §12). We cannot run
the plugin's Java parser, so we check structure: balanced braces, every #define
referenced is defined, colours are 8-hex ARGB, every trophy id resolves in
item_dictionary.json, the filter is accountType:1-gated, modules in order."""
from __future__ import annotations

import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
errors: list[str] = []
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
    # colours: every #rrggbb/#aarrggbb literal is 6 or 8 hex
    for col in re.findall(r'"(#[0-9a-fA-F]+)"', text):
        check(len(col) in (7, 9) and re.fullmatch(r"#[0-9a-fA-F]+", col),
              f"bad colour literal: {col}")
    # iron-gating: the IRON macro is defined, and EVERY styling rule references it
    check("#define IRON accountType:1" in text, "IRON macro not defined")
    check(text.count("rule (IRON") == text.count("rule ("), "a rule is not iron-gated (rule ( without IRON)")
    # module order
    order = ["module:settings", "module:trophies", "module:categories", "module:fallback"]
    idxs = [text.find(m) for m in order]
    check(all(i >= 0 for i in idxs), "a module is missing")
    check(idxs == sorted(idxs), f"modules out of order: {idxs}")
    # trophy ids resolve in the dictionary OR collection-log scope
    idict = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "item_dictionary.json"), encoding="utf-8"))["records"]}
    clog = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "collection_log.json"), encoding="utf-8"))["records"]}
    for m in re.findall(r"id:\[([0-9, ]+)\]", text):
        for tok in m.split(","):
            iid = int(tok)
            check(iid in idict or iid in clog, f"trophy id not in dictionary/clog scope: {iid}")

    if errors:
        print(f"LOOT-FILTER VALIDATION FAILED -- {len(errors)} violation(s):")
        for e in errors[:50]: print("  -", e)
        return 1
    print("LOOT-FILTER VALIDATION PASSED -- structure OK.")
    print(f"  rules: {text.count('rule (')} | applies: {text.count('apply (')} | bytes: {len(text)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write the validator + golden tests**

`tests/lootfilter/test_validate.py`:
```python
import os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
V = os.path.join(REPO, "data", "validate_loot_filter.py")

def test_validator_passes_committed():
    r = subprocess.run([sys.executable, V], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

def test_validator_fails_on_unbalanced(tmp_path):
    p = tmp_path / "bad.rs2f"; p.write_text("meta { name = \"x\";")  # unbalanced
    r = subprocess.run([sys.executable, V, "--filter", str(p)], capture_output=True, text=True)
    assert r.returncode == 1
```
`tests/lootfilter/test_golden.py`:
```python
import os
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
F = open(os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"), encoding="utf-8").read()

def test_mithril_gear_blue():
    assert 'name:["Mithril *"]' in F and "#ff4169e1" in F
def test_fire_rune_red():
    assert 'name:["Fire rune"]' in F and "#ffff4500" in F
def test_trophy_module_and_value_ladder():
    assert "module:trophies" in F and "value:>=10000000" in F and "value:>=0" in F
def test_iron_gated_and_meta():
    assert "accountType:1" in F and F.startswith("meta {")
```

- [ ] **Step 3: Run validator + golden + full verification**

Run:
```bash
venv/bin/python data/validate_loot_filter.py
venv/bin/python -m pytest tests/ -q
for v in validate_income validate_cost validate_kg validate_drop_rate; do venv/bin/python data/$v.py >/dev/null && echo "$v ok"; done
venv/bin/python scripts/lootfilter_demo.py && git diff --quiet outputs/gilded-tome-iron.rs2f && echo "byte-stable"
```
Expected: validator exits 0; full suite passes (existing + new lootfilter tests); the 4 existing validators still exit 0; the artifact regenerates byte-stably.

- [ ] **Step 4: Commit**

```bash
git add data/validate_loot_filter.py tests/lootfilter/test_validate.py tests/lootfilter/test_golden.py
git commit -m "loot-filter: structural validator + golden set + final verification"
```

---

## Deferred (spec §13 — do NOT build)
Account tailoring (the `account_state` seam — beam log gaps, hide banked); granular per-content supply curation; rarity sub-ranking of trophies; main-account variant; custom `.wav` sound pack; live/auto-publish to filterscape.
