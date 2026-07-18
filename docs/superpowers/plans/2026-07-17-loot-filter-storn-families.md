# Loot Filter v4 — Family Modules (Wave 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat 479-input `quantities` module with **one editable module per resource family**
(Seeds, Herbs, Runes, Ores, Bars, Logs, Planks, Gems, Ammo, Food, Prayer, Essence), each in Storn's
shape — tier groups (SS→E) with an editable membership dropdown, a minimum-quantity number, and a
colour picker — driven by `data/loot_importance.json`.

**Architecture:** New `emit.py` helpers (`emit_enumlist_input`, `emit_number_input`, `emit_style_def`,
`emit_family_module`) generate per-family modules; `generate.py` loops over families and drops
`emit_quantities`/`emit_families`. The ×10 quantity escalation (PR #29 `palette.quantity_display_grade`)
is preserved — a stacked pile shows a higher tier's colour.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON data; rs2f emitter; Node/tsx real-parser harness for the FilterScape import gate.

## Global Constraints

- **Plain labels — no AI-sounding copy.** Every module name / subtitle / group / input label is plain
  English: group = `"SS tier"`, `"A tier"`; inputs = `"Items"`, `"Minimum quantity"`, `"Colour"`. **No
  em-dashes, no colons in labels, no jargon.** (spec §2)
- **Every YAML scalar field is quoted** via `_yaml_scalar` (name/subtitle/label/group) and enum/list
  values via `_quoted_list` — a colon-space in a plain scalar nulls the whole FilterScape import.
- **Every styling rule is `IRONMAN`-gated** (`accountType:1`).
- **Colours 9-char ARGB** (`#aarrggbb`).
- **First-match-wins:** within a tier, highest quantity-threshold rule first; across tiers, higher base
  tier (SS before E) first.
- **Byte-stable** generic `outputs/gilded-tome-iron.rs2f` on re-run.
- **FilterScape real-parser gate:** the filter MUST parse cleanly through `Kaqemeex/loot-filters-ui`'s
  `parse()` (the only check that catches YAML/parse breakage). Manual per-wave step (§ Task 4).
- Data families & counts (from `loot_importance.json`, 1347 rows): `food` 465, `ammo` 362, `seed` 134,
  `bones` 130, `log` 72, `rune` 50, `herb` 47, `ore` 37, `gem` 22, `bar` 20, `essence` 4, `plank` 4.
  Tiers present: S, A, B, C, D, E (no SS in data — SS is reachable only via escalation).

---

### Task 1: enumlist / number / style-def helpers

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py`
- Test: `tests/lootfilter/test_emit_family_helpers.py`

**Interfaces:**
- Consumes: existing `_yaml_scalar`, `_macro_body`, `style_for`, `IRONMAN`.
- Produces:
  - `_quoted_list(items) -> str` — `["a", "b"]` of `_yaml_scalar`-escaped strings.
  - `emit_enumlist_input(module_id, label, group, enum_names, macro, default_names) -> str`
  - `emit_number_input(module_id, label, group, macro, default) -> str`
  - `emit_style_def(module_id, label, group, macro, style) -> str` — style input + `#define` **only**
    (no rule; caller emits its own rules).

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_emit_family_helpers.py
from osrs_planner.lootfilter.emit import (
    _quoted_list, emit_enumlist_input, emit_number_input, emit_style_def)
from osrs_planner.lootfilter.palette import style_for, FAMILY_HUES

def test_quoted_list_quotes_and_escapes():
    assert _quoted_list(["Ranarr seed", "Guam seed"]) == '["Ranarr seed", "Guam seed"]'

def test_enumlist_input_declares_enum_and_default():
    out = emit_enumlist_input("seeds", "Items", "SS tier",
                              ["Ranarr seed", "Guam seed"], "SEEDS_SS_NAMES", ["Ranarr seed"])
    assert "type: enumlist" in out
    assert 'enum: ["Ranarr seed", "Guam seed"]' in out
    assert 'label: "Items"' in out and 'group: "SS tier"' in out
    assert "#define SEEDS_SS_NAMES [\"Ranarr seed\"]" in out

def test_number_input():
    out = emit_number_input("seeds", "Minimum quantity", "SS tier", "SEEDS_SS_MIN", 1)
    assert "type: number" in out and 'label: "Minimum quantity"' in out
    assert "#define SEEDS_SS_MIN 1" in out

def test_style_def_has_no_rule():
    out = emit_style_def("seeds", "Colour", "SS tier", "SEEDS_SS_STYLE", style_for(FAMILY_HUES["seed"], "A"))
    assert "type: style" in out and "#define SEEDS_SS_STYLE" in out
    assert "rule (" not in out and "apply (" not in out
```

- [ ] **Step 2: Run test to verify it fails** — `./venv/bin/python -m pytest tests/lootfilter/test_emit_family_helpers.py -q` → FAIL (ImportError).

- [ ] **Step 3: Write minimal implementation** (add to `emit.py`, after `emit_style_input`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes** — same command → PASS.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(loot-filter): enumlist/number/style-def emit helpers"`

---

### Task 2: `emit_family_module` — tier ladder + editable membership + ×10 escalation

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py`
- Test: `tests/lootfilter/test_emit_family_module.py`

**Interfaces:**
- Consumes: Task 1 helpers, `hue_for`, `FAMILY_HUES`, `GRADE_ORDER`, `quantity_display_grade`,
  `style_for`, `emit_module`, `IRONMAN`.
- Produces: `emit_family_module(module_id, module_name, subtitle, rows, hue_for=hue_for) -> str`
  where `rows` = the `loot_importance` records for ONE family.

**Design:**
- `enum_names` = sorted unique `name` across rows.
- `name_tier` = name → its base tier; on duplicate names keep the **highest** tier (lowest
  `GRADE_ORDER` index) so a name never lands in two tier defaults.
- Emit tier groups for every grade from `SS` down to the family's lowest present tier (so every
  escalation target has a colour). Each group `"<T> tier"`: `emit_enumlist_input("Items")` +
  `emit_number_input("Minimum quantity", default 1)` + `emit_style_def("Colour",
  style_for(family_hue, T))`.
- Then, for each tier `T` that has members, emit rules (highest threshold first):
  for `k` in `bi..1` a `quantity:>=10**k` rule applying the promoted grade's `_STYLE`; then a
  `quantity:<<MOD>_<T>_MIN` hide; then the base `_STYLE` rule. Tiers emitted SS→E so higher base
  tiers win on any user overlap.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_emit_family_module.py
from osrs_planner.lootfilter.emit import emit_family_module

ROWS = [
    {"item_id": 5295, "name": "Ranarr seed",  "family": "seed", "base_tier": "A"},
    {"item_id": 5318, "name": "Potato seed",  "family": "seed", "base_tier": "E"},
    {"item_id": 5319, "name": "Potato seed",  "family": "seed", "base_tier": "E"},  # dup name
]

def test_module_has_plain_labels_and_tier_groups():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    assert 'name: "Seeds"' in m and 'subtitle: "Farming seeds"' in m
    assert 'group: "A tier"' in m and 'group: "E tier"' in m
    assert 'label: "Items"' in m and 'label: "Minimum quantity"' in m and 'label: "Colour"' in m
    assert "—" not in m                                          # no AI-sounding em-dash anywhere
    # no colon INSIDE any label value (the `label: "..."` separator is fine; the quoted text is not)
    import re as _re
    for val in _re.findall(r'label: "([^"]*)"', m):
        assert ":" not in val, f"label has a colon: {val!r}"

def test_enum_is_full_family_default_is_tier():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    assert 'enum: ["Potato seed", "Ranarr seed"]' in m           # full family, sorted, deduped
    assert '#define SEEDS_A_NAMES ["Ranarr seed"]' in m           # A default
    assert '#define SEEDS_E_NAMES ["Potato seed"]' in m           # E default, deduped

def test_ss_tier_group_exists_as_escalation_target():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    assert "#define SEEDS_SS_STYLE" in m                          # SS colour exists even with no SS members

def test_escalation_promotes_A_to_higher_tier_by_count():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    # A base: >=10 -> S colour, >=100 -> SS colour, base -> A colour
    assert "name:SEEDS_A_NAMES && quantity:>=100) { SEEDS_SS_STYLE }" in m
    assert "name:SEEDS_A_NAMES && quantity:>=10) { SEEDS_S_STYLE }" in m
    assert "name:SEEDS_A_NAMES && quantity:<SEEDS_A_MIN)" in m
    assert m.index("quantity:>=100) { SEEDS_SS_STYLE }") < m.index("quantity:>=10) { SEEDS_S_STYLE }")

def test_every_rule_iron_gated():
    m = emit_family_module("seeds", "Seeds", "Farming seeds", ROWS)
    rule_lines = [l for l in m.splitlines() if l.startswith("rule (") or l.startswith("apply (")]
    assert rule_lines and all("IRONMAN" in l for l in rule_lines)
```

- [ ] **Step 2: Run test to verify it fails** — `pytest tests/lootfilter/test_emit_family_module.py -q` → FAIL.

- [ ] **Step 3: Write minimal implementation** (add to `emit.py`):

```python
def emit_family_module(module_id: str, module_name: str, subtitle: str, rows, hue_for=hue_for) -> str:
    """One resource-family module in Storn's shape (spec §4/§5): editable tier groups (SS..lowest)
    with an 'Items' membership dropdown, a 'Minimum quantity', and a 'Colour'. ×10 escalation
    promotes a stacked pile to a higher tier's colour, keyed off the editable membership macro."""
    from collections import defaultdict
    if not rows:
        return emit_module(module_id, module_name, "", subtitle)
    fam = rows[0]["family"]
    hue = FAMILY_HUES.get(fam, "#ff9e9e9e")
    enum_names = sorted({r["name"] for r in rows})
    name_tier: dict[str, str] = {}
    for r in rows:                              # dedup name -> highest tier (lowest index)
        t = r["base_tier"]
        if r["name"] not in name_tier or GRADE_ORDER.index(t) < GRADE_ORDER.index(name_tier[r["name"]]):
            name_tier[r["name"]] = t
    by_tier: dict[str, list] = defaultdict(list)
    for name, t in name_tier.items():
        by_tier[t].append(name)
    present = [g for g in GRADE_ORDER if g in by_tier]
    tiers = GRADE_ORDER[: GRADE_ORDER.index(present[-1]) + 1]   # SS .. lowest present
    U = module_id.upper()
    def NM(t): return f"{U}_{t}_NAMES"
    def MN(t): return f"{U}_{t}_MIN"
    def ST(t): return f"{U}_{t}_STYLE"
    inputs, rules = [], []
    for t in tiers:                                            # inputs: every tier group
        g = f"{t} tier"
        inputs.append(emit_enumlist_input(module_id, "Items", g, enum_names, NM(t), sorted(by_tier.get(t, []))))
        inputs.append(emit_number_input(module_id, "Minimum quantity", g, MN(t), 1))
        inputs.append(emit_style_def(module_id, "Colour", g, ST(t), style_for(hue, t)))
    for t in tiers:                                            # rules: SS..E so higher tier wins overlap
        if t not in by_tier:
            continue
        bi = GRADE_ORDER.index(t)
        for k in range(bi, 0, -1):                             # escalation: highest threshold first
            grade = quantity_display_grade(t, 10 ** k)
            if grade != t:
                rules.append(f"rule ({IRONMAN} && name:{NM(t)} && quantity:>={10 ** k}) {{ {ST(grade)} }}")
        rules.append(f"rule ({IRONMAN} && name:{NM(t)} && quantity:<{MN(t)}) {{ hidden = true; }}")
        rules.append(f"rule ({IRONMAN} && name:{NM(t)}) {{ {ST(t)} }}")
    return emit_module(module_id, module_name, "\n".join(inputs + rules), subtitle)
```

- [ ] **Step 4: Run test to verify it passes** — `pytest tests/lootfilter/test_emit_family_module.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(loot-filter): emit_family_module — Storn tier buckets + editable membership + escalation"`

---

### Task 3: wire family modules into `generate.py`; retire `emit_quantities`/`emit_families`; extend validator

**Files:**
- Modify: `src/osrs_planner/lootfilter/generate.py`, `src/osrs_planner/lootfilter/emit.py`
  (remove `emit_quantities`, `emit_families`), `data/validate_loot_filter.py`
- Modify: `scripts/lootfilter_demo.py` is unaffected (calls `write_filter`)
- Test: `tests/lootfilter/test_generate.py` (update), `tests/lootfilter/test_validate.py` (extend)

**Interfaces:**
- Consumes: `emit_family_module`, `load_importance`.
- Produces: `FAMILY_MODULES` table in `generate.py` (family key → (module_id, name, subtitle)); the
  emitted module order (spec §7).

**`FAMILY_MODULES`** (family key from data → module):

```python
FAMILY_MODULES = [   # emit order; one module per family present in loot_importance
    ("seed", "seeds", "Seeds", "Farming seeds"),
    ("herb", "herbs", "Herbs", "Grimy and clean herbs"),
    ("rune", "runes", "Runes", "Runes"),
    ("ore", "ores", "Ores", "Mined ores"),
    ("bar", "bars", "Bars", "Smithing bars"),
    ("log", "logs", "Logs", "Woodcutting logs"),
    ("plank", "planks", "Planks", "Construction planks"),
    ("gem", "gems", "Gems", "Cut and uncut gems"),
    ("ammo", "ammo", "Ammo", "Arrows, bolts and darts"),
    ("food", "food", "Food", "Cooked and raw food"),
    ("bones", "prayer", "Prayer", "Bones and ashes"),
    ("essence", "essence", "Essence", "Runecrafting essence"),
]
```

- [ ] **Step 1: Update `generate.py`** — replace the `emit_quantities`/`emit_categories`/`emit_families`
  block. Group importance rows by family; emit one module per `FAMILY_MODULES` entry that has rows.
  Keep `emit_categories` for now (non-resource categories: teleports/jewellery/potions — a later wave
  reshapes them). New body of `generate_filter` (the `parts +=` section):

```python
    importance = load_importance(data_dir)
    from collections import defaultdict
    by_family = defaultdict(list)
    for r in importance:
        by_family[r["family"]].append(r)
    family_modules = [emit.emit_family_module(mid, name, sub, by_family[fam])
                      for fam, mid, name, sub in FAMILY_MODULES if by_family.get(fam)]
    parts += [emit.emit_notable(load_recommended_ids(data_dir), load_rare_ids(data_dir)),
              emit.emit_trophies(clog),
              emit.emit_gear(load_gear_records(data_dir)),
              *family_modules,
              emit.emit_categories(),                     # non-resource categories (teleports/jewellery/potions)
              emit.emit_untradeables(), emit.emit_coins(), emit.emit_fallback(),
              emit.emit_meta(title, description)]
```

  Add `FAMILY_MODULES` (above) near the top of `generate.py`. Delete `emit_quantities` and
  `emit_families` from `emit.py` and their imports/usages.

- [ ] **Step 2: Extend `validate_loot_filter.py`** — add after the existing checks:

```python
    # enumlist integrity: non-empty enum; every #define default is a subset of its enum
    for block in re.findall(r"/\*@ define:input:\w+\nlabel:.*?type: enumlist\n(.*?)\*/\s*#define (\w+) (\[.*?\])", text, re.S):
        enum_line, macro, default = block
        m = re.search(r"enum: (\[.*\])", enum_line)
        check(m is not None, f"enumlist {macro} has no enum")
        if m:
            enum_set = set(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
            default_set = set(re.findall(r'"((?:[^"\\]|\\.)*)"', default))
            check(enum_set, f"enumlist {macro} enum is empty")
            check(default_set <= enum_set, f"enumlist {macro} default not a subset of enum")
    # every area:[...] box is 6 ints
    for box in re.findall(r"area:\[([^\]]*)\]", text):
        check(len([x for x in box.split(",") if x.strip()]) == 6, f"area box not 6 ints: [{box}]")
```

  Update the `order` list in `validate_loot_filter.py` to the new module order:
  `["settings", "custom", "notable", "trophies", "gear", "seeds", "herbs", "runes", "ores", "bars",
  "logs", "planks", "gems", "ammo", "food", "prayer", "essence", "categories", "coins", "fallback"]`.

- [ ] **Step 3: Update `tests/lootfilter/test_generate.py`** — replace `quantities`/`emit_families`
  assertions with family-module assertions:

```python
def test_family_modules_present_and_ordered():
    from osrs_planner.lootfilter.generate import generate_filter
    f = generate_filter()
    for mid in ["seeds", "herbs", "runes", "ores", "bars", "logs", "planks", "gems", "ammo", "food", "prayer", "essence"]:
        assert f"define:module:{mid}" in f
    assert f.index("define:module:seeds") < f.index("define:module:categories")
    assert "define:module:quantities" not in f     # retired

def test_seeds_module_is_editable_tiers():
    from osrs_planner.lootfilter.generate import generate_filter
    f = generate_filter()
    assert 'group: "A tier"' in f and 'label: "Items"' in f and "#define SEEDS_A_STYLE" in f
```

  (Delete the old `test_quantities_*` tests that referenced the retired module.)

- [ ] **Step 4: Regenerate + byte-stability + full lootfilter suite**

```bash
./venv/bin/python scripts/lootfilter_demo.py            # regen generic
./venv/bin/python data/validate_loot_filter.py          # PASS
cp outputs/gilded-tome-iron.rs2f /tmp/a && ./venv/bin/python scripts/lootfilter_demo.py >/dev/null && cmp outputs/gilded-tome-iron.rs2f /tmp/a && echo BYTE-STABLE
./venv/bin/python -m pytest tests/lootfilter -q
```
Expected: validator PASS, BYTE-STABLE, tests green.

- [ ] **Step 5: Commit** — `git commit -m "feat(loot-filter): per-family modules replace flat quantities; validator + order"`

---

### Task 4: coverage verifier + real-parser gate + regen

**Files:**
- Create: `data/verify_family_modules.py`
- Test: `tests/lootfilter/test_verify_family_modules.py`

**Interfaces:**
- Consumes: `loot_importance.json`, the generated filter.
- Produces: `verify_family_modules.py` (report-not-fail, exit 0) — every `loot_importance` item's name
  appears in exactly one tier `_NAMES` default of its family module; reports any name in zero or >1.

- [ ] **Step 1: Write the verifier** (`data/verify_family_modules.py`): load `loot_importance.json`,
  regenerate the filter via `generate_filter()`, for each family module parse its `<MOD>_<T>_NAMES`
  defaults, assert each family name appears in exactly one tier default; print
  `family-coverage: N/N covered` per family and a residual list; **exit 0** (report-not-fail, per
  `feedback_editorial_data_report_not_fail`). Load the module via `importlib.util.spec_from_file_location`
  if importing generate at top-level (avoid the `tests/data` package shadow — reference_tests_data_package_shadow).

- [ ] **Step 2: Write the test** (`tests/lootfilter/test_verify_family_modules.py`): run the verifier
  via `subprocess`, assert returncode 0 and `"covered"` in stdout (mirror `test_validate.py`'s subprocess pattern).

- [ ] **Step 3: Run the verifier + full Python suite**

```bash
./venv/bin/python data/verify_family_modules.py
./venv/bin/python -m pytest -q --continue-on-collection-errors   # (4 drop_rates collection errors are pre-existing)
```

- [ ] **Step 4: FilterScape real-parser gate (manual, REQUIRED).** Run the generic + a tailored build
  through the actual parser and confirm PARSE OK with the 12 family modules:

```bash
# harness lives in the scratchpad clone of Kaqemeex/loot-filters-ui (packages/ui/src/parsing/harness.ts)
cd <scratchpad>/lfui/packages/ui/src/parsing && node --import tsx harness.ts <repo>/outputs/gilded-tome-iron.rs2f
```
Expected: `PARSE OK`, modules include `seeds … essence`, each with its tier inputs. If the clone is
absent: `git clone https://github.com/Kaqemeex/loot-filters-ui`, `npm i tsx yaml zod`, stub the
`types/Images.ts` PNG imports (see the import-fix session).

- [ ] **Step 5: Commit** — `git commit -m "feat(loot-filter): family-module coverage verifier + real-parser gate"`

---

## Post-wave

- Whole-branch review (opus) over Tasks 1–4 before merge — cross-module first-match-wins ordering is
  invisible in single-task diffs (the recurring lesson from #28/#29).
- Regenerate the tailored `outputs/gilded-tome-tiger0295.rs2f` (live TempleOSRS clog) and import-test.
- **Deferred to later waves:** gear (metal + non-metal + jewellery sprites), content (per-boss modules
  + area boxes + themed colours), utility (alchs/keys/teleports), frame (settings globals + hidden +
  custom promotion). `herblore_secondaries` and `food_pots` split have no `loot_importance` rows yet —
  add when their data lands.
- **Open decision (owner):** family tier colours default to the family identity hue (Storn-pure, one
  colour per tier). Per-element/per-metal identity within runes/ores/bars/logs/gems (the PR #12 hues)
  is a possible refinement — flagged, not built.
