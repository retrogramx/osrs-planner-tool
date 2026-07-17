# Loot-Filter Quantity Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `quantities` module that renders each resource pile in its identity hue at a hand-ranked base importance tier, escalated one grade per ×10 in pile count (Storn's engine, derived from one committed editorial file).

**Architecture:** New editorial data file `data/loot_importance.json` (materialized by `data/build_loot_importance.py`) maps every resource item → base tier. A pure model `palette.quantity_display_grade(base, count)` promotes the tier by ×10 decades (capped SS). `emit.emit_quantities()` groups items by (family, identity-hue, base tier) and emits escalation rules, using `emit.hue_for()` (per-name via `categorize()`, family fallback). The module is wired into `generate_filter` **above** `categories`, which is trimmed of the now-superseded resource rows; `emit_families` skips the ranked families. Structural `validate_loot_importance.py` + coverage `verify_loot_importance.py` gate the data. Byte-stable regen of the generic filter.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON data; pytest. Filter is FilterScape `.rs2f`. KG (`kg/*.json`) is untouched — this is filter-side only.

## Global Constraints

- **Never fabricate.** Base tiers are declared **editorial** (`kind: editorial`, owner-reviewed) — they need no `source_token`, but every ranked `item_id` must be a real item in `item_dictionary.json`, and its `family` must match `loot_families.json` where present (essence/gem/plank excepted — `categories`-sourced).
- **Byte-stable.** `open("outputs/gilded-tome-iron.rs2f").read() == generate_filter()` after regen; re-running `generate_filter()` is deterministic.
- **All colours are 9-char `#aarrggbb`.** Every styling `rule (`/`apply (` is `IRONMAN`-gated. Filter must START with a module declaration; `meta{}` LAST. Macro names unique & uppercase; the reserved gate macro is `IRONMAN` (never `IRON`).
- **Grade vocabulary:** `GRADE_ORDER = ["SS","S","A","B","C","D","E"]` (index 0 = loudest). Reuse `palette.style_for(hue, grade)` for emphasis — no new styling code.
- **Module order (first-match-wins):** `settings → custom → [tailoring] → notable → trophies → gear → quantities → categories → families → untradeables → coins → fallback → meta`.
- **Test data-loading trap:** load `data/*.py` in tests via `subprocess` or `importlib.util.spec_from_file_location`, never `from data.X import` (the `tests/data/__init__.py` package-shadow — passes isolated, ERRORs in full-suite collection).
- **Full suite green:** `./venv/bin/python -m pytest -q --continue-on-collection-errors` (the 4 pre-existing `tests/drop_rates/` collection errors are unrelated).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/osrs_planner/lootfilter/palette.py` (modify) | add `GRADE_ORDER` + `quantity_display_grade(base, count)` | 1 |
| `data/build_loot_importance.py` (create) | editorial tier tables → materialize `loot_importance.json` | 2 |
| `data/loot_importance.json` (create) | committed base-tier records | 2 |
| `data/validate_loot_importance.py` (create) | structural hard-fail gate | 2 |
| `data/verify_loot_importance.py` (create) | per-family coverage report (exit 0) | 3 |
| `src/osrs_planner/lootfilter/emit.py` (modify) | `hue_for()`, `emit_quantities()`, `emit_families` skip-param | 4,5,6 |
| `src/osrs_planner/lootfilter/categories.py` (modify) | split `categorize` (keep) from `category_rules` (trim resources) | 7 |
| `src/osrs_planner/lootfilter/generate.py` (modify) | load importance, wire `quantities`, pass skip-set | 7 |
| `data/validate_loot_filter.py` (modify) | add `quantities` to module-order subsequence | 7 |
| `outputs/gilded-tome-iron.rs2f` (regen) | committed generic filter | 7 |
| `tests/lootfilter/test_golden.py` (modify) | assert `quantities` present, trimmed categories gone | 7 |

---

## Task 1: Quantity display-tier model

**Files:**
- Modify: `src/osrs_planner/lootfilter/palette.py` (append after `GEAR_TIERS`, ~line 134)
- Test: `tests/lootfilter/test_quantity_model.py` (create)

**Interfaces:**
- Produces: `palette.GRADE_ORDER: list[str]` = `["SS","S","A","B","C","D","E"]`; `palette.quantity_display_grade(base_grade: str, count: int) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_quantity_model.py
from osrs_planner.lootfilter.palette import GRADE_ORDER, quantity_display_grade as q

def test_grade_order():
    assert GRADE_ORDER == ["SS", "S", "A", "B", "C", "D", "E"]

def test_base_floor_at_count_one():
    assert q("A", 1) == "A" and q("E", 1) == "E"

def test_ranarr_case_base_A():        # the design's motivating example
    assert q("A", 40) == "S" and q("A", 100) == "SS" and q("A", 9) == "A"

def test_guam_case_base_E():
    assert q("E", 40) == "D" and q("E", 100) == "C" and q("E", 1000) == "B"

def test_caps_at_ss():
    assert q("B", 10_000_000) == "SS" and q("SS", 5) == "SS"

def test_no_float_precision_bug_at_powers_of_ten():
    # integer decades, NOT float log10 (log10(1000)=2.9999.. would misgrade)
    assert q("B", 1000) == "SS" and q("A", 100) == "SS" and q("C", 100) == "A"

def test_count_below_one_is_base():
    assert q("B", 0) == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_quantity_model.py -q`
Expected: FAIL (`ImportError: cannot import name 'GRADE_ORDER'`).

- [ ] **Step 3: Implement**

Append to `src/osrs_planner/lootfilter/palette.py`:

```python
GRADE_ORDER = ["SS", "S", "A", "B", "C", "D", "E"]   # index 0 = loudest; single source for the quantity model

def _decades(count: int) -> int:
    """floor(log10(count)) via integer division — avoids the float log10(1000)=2.9999.. misgrade."""
    d = 0
    while count >= 10:
        count //= 10
        d += 1
    return d

def quantity_display_grade(base_grade: str, count: int) -> str:
    """Promote base_grade one step toward SS per ×10 in pile count, capped at SS (design §3)."""
    bi = GRADE_ORDER.index(base_grade)
    steps = _decades(count) if count >= 1 else 0
    return GRADE_ORDER[max(0, bi - steps)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_quantity_model.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/palette.py tests/lootfilter/test_quantity_model.py
git commit -m "feat(loot-filter): quantity display-tier model (base + ×10 decades, capped SS)"
```

---

## Task 2: Editorial importance data + builder + structural validator

**Files:**
- Create: `data/build_loot_importance.py`, `data/loot_importance.json`, `data/validate_loot_importance.py`
- Test: `tests/lootfilter/test_loot_importance.py` (create)

**Interfaces:**
- Produces: `data/loot_importance.json` = `{"_provenance": {...}, "records": [{"item_id": int, "name": str, "family": str, "base_tier": str, "rationale": str}, ...]}`. `base_tier` ∈ `GRADE_ORDER`. Families: `herb, rune, ore, bar, log, seed, bones, ammo, food, essence, gem, plank`.
- `build_loot_importance.py` is runnable: `./venv/bin/python data/build_loot_importance.py` rewrites the JSON (byte-stable re-run).
- `validate_loot_importance.py` returns 0 on the committed file, 1 on a structural violation.

**Editorial ranking (mine to author; owner reviews the JSON rationales).** The builder resolves each family member to a base tier via the tables below (default catches the long tail — "rank everything, no value fallback"). Tables key on the in-game name.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_loot_importance.py
import json, os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
J = os.path.join(REPO, "data", "loot_importance.json")
V = os.path.join(REPO, "data", "validate_loot_importance.py")
B = os.path.join(REPO, "data", "build_loot_importance.py")

def _recs():
    return json.load(open(J, encoding="utf-8"))["records"]

def test_provenance_editorial():
    assert json.load(open(J, encoding="utf-8"))["_provenance"]["kind"] == "editorial"

def test_every_record_shape_and_tier():
    grades = {"SS", "S", "A", "B", "C", "D", "E"}
    for r in _recs():
        assert set(r) >= {"item_id", "name", "family", "base_tier", "rationale"}
        assert r["base_tier"] in grades and isinstance(r["item_id"], int) and r["rationale"]

def test_ranarr_high_guam_low():        # the design's motivating ranking must hold
    by = {r["name"]: r["base_tier"] for r in _recs()}
    order = {"SS": 0, "S": 1, "A": 2, "B": 3, "C": 4, "D": 5, "E": 6}
    assert order[by["Grimy ranarr weed"]] < order[by["Grimy guam leaf"]]

def test_cheap_staples_not_bottom():    # value would floor these; the ranking must not
    by = {r["name"]: r["base_tier"] for r in _recs()}
    for staple in ("Pure essence", "Coal"):
        assert by[staple] not in ("D", "E"), f"{staple} ranked too low"

def test_builder_is_byte_stable():
    before = open(J, encoding="utf-8").read()
    subprocess.run([sys.executable, B], check=True)
    assert open(J, encoding="utf-8").read() == before

def test_validator_passes_committed():
    assert subprocess.run([sys.executable, V], capture_output=True, text=True).returncode == 0

def test_validator_catches_bad_tier(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"_provenance": {"kind": "editorial"},
        "records": [{"item_id": 995, "name": "Coins", "family": "ore", "base_tier": "Z", "rationale": "x"}]}))
    assert subprocess.run([sys.executable, V, "--file", str(bad)], capture_output=True, text=True).returncode == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_loot_importance.py -q`
Expected: FAIL (files do not exist).

- [ ] **Step 3: Write the builder** (`data/build_loot_importance.py`) — the editorial tier tables:

```python
#!/usr/bin/env python3
"""EDITORIAL: hand-ranked ironman base importance per resource item -> data/loot_importance.json.
Judgment, not a wiki fact (owner-reviewed). Tier tables below ARE the ranking; a per-family default
catches the long tail ("rank everything, no value fallback"). Re-run must be byte-stable."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
from osrs_planner.lootfilter import categories as C

def load(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))["records"]

DICT = load("item_dictionary.json")
NAME2ID = {}                          # prefer canonical page for a name
for r in DICT:
    if r["name"] not in NAME2ID or r.get("is_canonical"):
        NAME2ID[r["name"]] = r["item_id"]
ID2NAME = {r["item_id"]: r["name"] for r in DICT}
FAMS = load("loot_families.json")     # item_id -> family (authority for herb/rune/ore/bar/log/seed/bones/ammo/food)

# --- tier resolvers (name -> (base_tier, rationale)); return None to fall to the family default ---

def herb_tier(n):
    key = n.lower().replace("grimy ", "")
    T = {"ranarr weed": ("A", "prayer/super-restore backbone"),
         "snapdragon": ("A", "super restore/sara brew"), "torstol": ("A", "super combat/anti-venom+"),
         "toadflax": ("B", "sara brew/anti-venom"), "avantoe": ("B", "fishing/hunter/extended"),
         "kwuarm": ("B", "super strength/weapon poison"), "huasca": ("B", "herblore secondary base"),
         "cadantine": ("C", "super defence/restore"), "lantadyme": ("C", "antifire/magic"),
         "dwarf weed": ("C", "ranging"), "irit leaf": ("D", "super attack/antipoison"),
         "harralander": ("D", "energy/combat/restore"), "marrentill": ("E", "antipoison, low"),
         "tarromin": ("E", "strength/serum, low"), "guam leaf": ("E", "attack, trivial")}
    return T.get(key)

def rune_tier(n):
    elem = n.lower().replace(" rune", "")
    T = {**{e: ("A", "alch/high-tier casting/RC target") for e in ("nature", "law", "death", "blood", "soul", "wrath")},
         **{e: ("B", "utility casting") for e in ("cosmic", "chaos", "astral")},
         **{e: ("C", "combo/utility") for e in ("mind", "body", "mist", "dust", "mud", "lava", "smoke", "steam")},
         **{e: ("D", "elemental staple, cheap in bulk") for e in ("fire", "water", "air", "earth")}}
    return T.get(elem)

_METAL = {"ore": {"Runite": "A", "Adamantite": "B", "Mithril": "C", "Coal": "C", "Gold": "C", "Iron": "D", "Silver": "D", "Copper": "E", "Tin": "E"},
          "bar": {"Runite": "A", "Adamantite": "B", "Mithril": "C", "Steel": "C", "Gold": "C", "Iron": "D", "Silver": "D", "Bronze": "E"}}
def ore_tier(n):
    for k, t in _METAL["ore"].items():
        if n.startswith(k):
            return (t, f"{k.lower()} ore — smithing/grind gate")
    return None
def bar_tier(n):
    for k, t in _METAL["bar"].items():
        if n.startswith(k):
            return (t, f"{k.lower()} bar — smithing feedstock")
    return None

def log_tier(n):
    T = {"Magic logs": "A", "Redwood logs": "A", "Yew logs": "B", "Maple logs": "C", "Mahogany logs": "C",
         "Teak logs": "C", "Willow logs": "D"}
    if n in T:
        return (T[n], f"{n.lower()} — firemaking/fletching/construction")
    return None  # Logs/Oak/Achey/Arctic pine/Bark -> default E

def essence_tier(n):
    T = {"Pure essence": ("A", "runecrafting fuel, hoarded"), "Daeyalt essence": ("A", "RC xp premium"),
         "Guardian essence": ("B", "GOTR"), "Rune essence": ("C", "low-level RC")}
    return T.get(n)

_GEM_CUT = {"Zenyte": "A", "Onyx": "A", "Dragonstone": "A", "Diamond": "B", "Ruby": "C",
            "Emerald": "D", "Sapphire": "D", "Opal": "E", "Jade": "E", "Red topaz": "E"}
def gem_tier(n):
    uncut = n.startswith("Uncut ")
    base = (n[len("Uncut "):] if uncut else n).capitalize()   # "sapphire"->"Sapphire", matches _GEM_CUT keys
    if base in _GEM_CUT:
        t = _GEM_CUT[base]
        if uncut:                                            # uncut one tier louder (grind gate = cutting)
            from osrs_planner.lootfilter.palette import GRADE_ORDER
            t = GRADE_ORDER[max(0, GRADE_ORDER.index(t) - 1)]
        return (t, f"{base.lower()} gem — crafting/bolt tips")
    return None

def plank_tier(n):
    T = {"Mahogany plank": ("A", "high construction xp"), "Teak plank": ("B", "construction staple"),
         "Oak plank": ("C", "early construction"), "Plank": ("E", "trivial")}
    return T.get(n)

def bones_tier(n):
    nl = n.lower()
    T = {"superior dragon bones": "A", "dagannoth bones": "A", "ourg bones": "A", "hydra bones": "A",
         "frost dragon bones": "A", "dragon bones": "B", "wyvern bones": "B", "lava dragon bones": "B",
         "wyrm bones": "B", "drake bones": "B", "fayrg bones": "B", "raurg bones": "B",
         "big bones": "C", "babydragon bones": "C", "jogre bones": "C", "zogre bones": "C"}
    if nl in T:
        return (T[nl], f"{nl} — prayer xp per bone")
    if nl == "bones":
        return ("D", "basic prayer xp")
    if nl.endswith(" ashes"):
        A = {"infernal ashes": "A", "malicious ashes": "B", "abyssal ashes": "C",
             "fiendish ashes": "D", "vile ashes": "E"}
        return (A.get(nl, "D"), "ashes — prayer xp")
    if nl.startswith("ensouled ") and nl.endswith(" head"):
        return ("C", "arceuus reanimation xp")
    return None  # other bat/wolf/monkey bones -> default D

def ammo_tier(n):
    nl = n.lower()
    demote = " tip" in nl or "tips" in nl                # tips one tier below finished ammo
    for metal, t in (("dragon", "A"), ("rune", "B"), ("amethyst", "B"), ("adamant", "C"),
                     ("mithril", "D"), ("iron", "E"), ("steel", "E"), ("black", "E"), ("bronze", "E")):
        if nl.startswith(metal):
            from osrs_planner.lootfilter.palette import GRADE_ORDER
            gi = GRADE_ORDER.index(t)
            if demote:
                gi = min(len(GRADE_ORDER) - 1, gi + 1)
            return (GRADE_ORDER[gi], f"{metal} ammo{' tips' if demote else ''}")
    if "cannonball" in nl:
        return ("B", "cannon fodder, iron staple")
    return None

_FOOD_SUPPLY = {"Anglerfish": "A", "Manta ray": "A", "Dark crab": "A", "Cooked karambwan": "A",
                "Shark": "B", "Sea turtle": "B", "Monkfish": "B", "Tuna potato": "B",
                "Swordfish": "C", "Lobster": "C", "Bass": "C"}
def food_tier(n):
    if n in _FOOD_SUPPLY:
        return (_FOOD_SUPPLY[n], "combat supply — don't lose these")
    return None  # everything else -> default E

_DEFAULT = {"herb": ("E", "low-tier herb"), "rune": ("D", "elemental/utility rune"),
            "ore": ("E", "low ore"), "bar": ("E", "low bar"), "log": ("E", "low log"),
            "seed": ("E", "allotment/common seed"), "bones": ("D", "common bones"),
            "ammo": ("E", "low-tier ammo"), "food": ("E", "trivial food"),
            "essence": ("C", "essence"), "gem": ("E", "semi-precious gem"), "plank": ("E", "plank")}
_RESOLVER = {"herb": herb_tier, "rune": rune_tier, "ore": ore_tier, "bar": bar_tier, "log": log_tier,
             "seed": None, "bones": bones_tier, "ammo": ammo_tier, "food": food_tier,
             "essence": essence_tier, "gem": gem_tier, "plank": plank_tier}

def seed_tier(n):
    T = {"Ranarr seed": "A", "Snapdragon seed": "A", "Torstol seed": "A", "Magic seed": "A", "Yew seed": "B",
         "Palm tree seed": "B", "Dragonfruit tree seed": "B", "Toadflax seed": "B", "Avantoe seed": "B",
         "Kwuarm seed": "C", "Cadantine seed": "C", "Lantadyme seed": "C", "Dwarf weed seed": "C",
         "Maple seed": "C", "Willow seed": "D", "Oak seed": "D", "Irit seed": "D", "Harralander seed": "D"}
    if n in T:
        return (T[n], f"{n.lower()} — farming/herblore pipeline")
    return None
_RESOLVER["seed"] = seed_tier

def resolve(item_id, family):
    n = ID2NAME.get(item_id, "")
    r = _RESOLVER[family](n) if _RESOLVER.get(family) else None
    if r is None:
        r = _DEFAULT[family]
    return {"item_id": item_id, "name": n, "family": family, "base_tier": r[0], "rationale": r[1]}

def main():
    records, seen = [], set()
    # 1) loot_families families with id-lists ready
    RANKED = {"herb", "rune", "ore", "bar", "log", "seed", "bones", "ammo", "food"}
    for r in FAMS:
        if r["family"] in RANKED and r["item_id"] not in seen and r["item_id"] in ID2NAME:
            records.append(resolve(r["item_id"], r["family"])); seen.add(r["item_id"])
    # 2) categories-sourced families (name sets -> ids)
    def add_names(names, fam):
        for nm in names:
            iid = NAME2ID.get(nm)
            if iid is not None and iid not in seen:
                records.append(resolve(iid, fam)); seen.add(iid)
    add_names(sorted(C.ESSENCE_NAMES), "essence")
    add_names(sorted(C.PLANK_NAMES), "plank")
    gem_names = sorted(C.CUT_GEMS) + sorted("Uncut " + g.lower() for g in C.CUT_GEMS)
    add_names(gem_names, "gem")
    records.sort(key=lambda r: (r["family"], r["item_id"]))
    out = {"_provenance": {"domain": "loot_importance", "kind": "editorial",
        "note": "Hand-ranked ironman base importance per resource item. Judgment, not a wiki fact; owner-reviewed. "
                "base_tier in {SS,S,A,B,C,D,E}. Quantity escalation (×10/grade) applied at emit time, NOT stored here."},
        "records": records}
    with open(os.path.join(HERE, "loot_importance.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"loot_importance: {len(records)} items ranked")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Materialize the JSON**

Run: `./venv/bin/python data/build_loot_importance.py`
Expected: `loot_importance: <N> items ranked` (N ≈ 900-1100); creates `data/loot_importance.json`.

- [ ] **Step 5: Write the validator** (`data/validate_loot_importance.py`):

```python
#!/usr/bin/env python3
"""Structural gate for data/loot_importance.json (editorial base tiers). Violations -> exit 1."""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GRADES = {"SS", "S", "A", "B", "C", "D", "E"}
RANKED = {"herb", "rune", "ore", "bar", "log", "seed", "bones", "ammo", "food", "essence", "gem", "plank"}
CATS = {"essence", "gem", "plank"}    # membership is categories-sourced, not in loot_families.json

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(HERE, "loot_importance.json"))
    ap.add_argument("--data", default=HERE)
    ns = ap.parse_args()
    data = json.load(open(ns.file, encoding="utf-8"))
    recs = data["records"]
    idict = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "item_dictionary.json"), encoding="utf-8"))["records"]}
    fam_of = {r["item_id"]: r["family"] for r in json.load(open(os.path.join(ns.data, "loot_families.json"), encoding="utf-8"))["records"]}
    errors, seen = [], set()
    if data.get("_provenance", {}).get("kind") != "editorial":
        errors.append("provenance.kind must be 'editorial'")
    for r in recs:
        iid = r.get("item_id")
        if iid not in idict:
            errors.append(f"{iid}: not in item_dictionary")
        if iid in seen:
            errors.append(f"{iid}: duplicate")
        seen.add(iid)
        if r.get("base_tier") not in GRADES:
            errors.append(f"{iid}: bad base_tier {r.get('base_tier')!r}")
        if r.get("family") not in RANKED:
            errors.append(f"{iid}: family {r.get('family')!r} not a ranked family")
        if not r.get("rationale"):
            errors.append(f"{iid}: missing rationale")
        if r.get("family") not in CATS and iid in fam_of and fam_of[iid] != r.get("family"):
            errors.append(f"{iid}: family {r.get('family')!r} != loot_families {fam_of[iid]!r}")
    if errors:
        print(f"LOOT-IMPORTANCE VALIDATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        return 1
    print(f"LOOT-IMPORTANCE VALIDATION PASSED — {len(recs)} items, tiers {sorted(GRADES)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run validator + tests**

Run: `./venv/bin/python data/validate_loot_importance.py`
Expected: `LOOT-IMPORTANCE VALIDATION PASSED — <N> items ...`
Run: `./venv/bin/python -m pytest tests/lootfilter/test_loot_importance.py -q`
Expected: PASS (7 passed). If `test_ranarr_high_guam_low` / `test_cheap_staples_not_bottom` fail, fix the tier tables (not the test — the ranking is the deliverable).

- [ ] **Step 7: Commit**

```bash
git add data/build_loot_importance.py data/loot_importance.json data/validate_loot_importance.py tests/lootfilter/test_loot_importance.py
git commit -m "feat(loot-filter): editorial base-importance data (loot_importance.json) + builder + validator"
```

---

## Task 3: Coverage verifier

**Files:**
- Create: `data/verify_loot_importance.py`
- Test: `tests/lootfilter/test_verify_importance.py` (create)

**Interfaces:**
- Consumes: `data/loot_importance.json`, `data/loot_families.json`.
- Produces: standalone script, exit 0, prints per-family `have N / total M` coverage.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_verify_importance.py
import os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def test_verify_reports_and_exits_zero():
    r = subprocess.run([sys.executable, os.path.join(REPO, "data", "verify_loot_importance.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "coverage" in r.stdout.lower() and "herb" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_verify_importance.py -q`
Expected: FAIL (script missing).

- [ ] **Step 3: Implement** (`data/verify_loot_importance.py`):

```python
#!/usr/bin/env python3
"""Coverage report for data/loot_importance.json: per family, have N / family-total M.
Editorial data -> no source-grounding; reports gaps but never fails (exit 0)."""
import json, os, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))

def main() -> int:
    recs = json.load(open(os.path.join(HERE, "loot_importance.json"), encoding="utf-8"))["records"]
    fams = json.load(open(os.path.join(HERE, "loot_families.json"), encoding="utf-8"))["records"]
    LOOT_FAM = {"herb", "rune", "ore", "bar", "log", "seed", "bones", "ammo", "food"}
    fam_total = Counter(r["family"] for r in fams if r["family"] in LOOT_FAM)
    ranked = defaultdict(set)
    for r in recs:
        ranked[r["family"]].add(r["item_id"])
    ranked_ids = {r["item_id"] for r in recs}
    tier_dist = Counter(r["base_tier"] for r in recs)
    print(f"LOOT-IMPORTANCE COVERAGE — {len(recs)} items ranked; base-tier dist {dict(tier_dist)}")
    for fam in sorted(LOOT_FAM):
        have, tot = len(ranked.get(fam, ())), fam_total.get(fam, 0)
        missing = [r["item_id"] for r in fams if r["family"] == fam and r["item_id"] not in ranked_ids]
        print(f"  {fam:8} have {have}/{tot}" + (f"  (missing {len(missing)})" if missing else ""))
    for fam in ("essence", "gem", "plank"):
        print(f"  {fam:8} have {len(ranked.get(fam, ()))} (categories-sourced)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_verify_importance.py -q && ./venv/bin/python data/verify_loot_importance.py`
Expected: PASS; prints coverage lines (`herb have 46/46`, etc.).

- [ ] **Step 5: Commit**

```bash
git add data/verify_loot_importance.py tests/lootfilter/test_verify_importance.py
git commit -m "feat(loot-filter): loot_importance coverage verifier"
```

---

## Task 4: `hue_for` identity-hue helper

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add near the other helpers, after `_id_list`)
- Test: `tests/lootfilter/test_hue_for.py` (create)

**Interfaces:**
- Consumes: `categories.categorize(name) -> {"id","hue"} | None`; `palette.FAMILY_HUES`.
- Produces: `emit.hue_for(name: str, family: str) -> str` — per-name category hue when `categorize` yields one, else `FAMILY_HUES[family]`, else a neutral grey `"#ff9e9e9e"` (never raises).

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_hue_for.py
from osrs_planner.lootfilter.emit import hue_for
from osrs_planner.lootfilter.palette import FAMILY_HUES

def test_per_name_hue_wins():
    assert hue_for("Coal", "ore") == "#ff2b2b2b"            # categorize() ore per-name (dark), not family
    assert hue_for("Nature rune", "rune") == "#ff2e8b57"    # per-element rune hue
    assert hue_for("Magic logs", "log") == "#ff5090d0"      # per-tree log hue

def test_family_fallback():
    # an item categorize() does not resolve (e.g. an essence name) falls to the family hue
    assert hue_for("Pure essence", "essence") == "#ff7d7da0"  # categorize essence hue OR FAMILY? essence categorizes
    # a family with no per-name hue and no categorize match uses FAMILY_HUES
    assert hue_for("Nonexistent thing", "seed") == FAMILY_HUES["seed"]

def test_unknown_family_grey():
    assert hue_for("???", "not_a_family") == "#ff9e9e9e"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_hue_for.py -q`
Expected: FAIL (`cannot import name 'hue_for'`).

- [ ] **Step 3: Implement** — add to `src/osrs_planner/lootfilter/emit.py`:

```python
from osrs_planner.lootfilter.categories import categorize   # add to the categories import line

def hue_for(name: str, family: str) -> str:
    """Identity hue for a resource item: per-name via categorize() (coal dark, per-element runes,
    per-tree logs, gems, ore/bar), else the family hue, else neutral grey (never raises)."""
    c = categorize(name)
    if c and c.get("hue"):
        return c["hue"]
    return FAMILY_HUES.get(family, "#ff9e9e9e")
```

Note: `categorize("Pure essence")` returns the essence hue `#ff7d7da0`, so `test_family_fallback`'s first assert passes via the per-name branch; the second exercises the `FAMILY_HUES` fallback.

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_hue_for.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_hue_for.py
git commit -m "feat(loot-filter): hue_for identity-hue helper (per-name categorize, family fallback)"
```

---

## Task 5: `emit_quantities()`

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add after `emit_families`)
- Test: `tests/lootfilter/test_emit_quantities.py` (create)

**Interfaces:**
- Consumes: `palette.GRADE_ORDER`, `palette.style_for`, `emit.hue_for`, `emit.emit_module`, `emit.emit_rule`, `emit.emit_style_input`, `emit._id_list`, `emit._macro_name`, `IRONMAN`.
- Produces: `emit.emit_quantities(importance: list[dict], hue_for=hue_for) -> str`. `importance` items are `{item_id, name, family, base_tier}`. Emits a `quantities` module: a `QUANTITY_FLOOR` number input + non-terminal hide rule, then per (family, hue, base_tier) group a set of editable style-inputs, threshold-descending (SS-threshold rule first), each `IRONMAN && id:[…] && quantity:>=T` (T dropped when 1) styled `style_for(hue, display_grade)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_emit_quantities.py
from osrs_planner.lootfilter.emit import emit_quantities

IMP = [
    {"item_id": 207, "name": "Grimy ranarr weed", "family": "herb", "base_tier": "A"},
    {"item_id": 199, "name": "Grimy guam leaf",   "family": "herb", "base_tier": "E"},
    {"item_id": 561, "name": "Nature rune",       "family": "rune", "base_tier": "A"},
]

def test_module_and_floor():
    out = emit_quantities(IMP)
    assert "define:module:quantities" in out
    assert "#define QUANTITY_FLOOR 0" in out
    assert "quantity:<QUANTITY_FLOOR" in out and "apply (IRONMAN" in out   # non-terminal hide

def test_base_A_emits_ss_s_a_thresholds_descending():
    out = emit_quantities([IMP[0]])   # base A -> SS(>=100), S(>=10), A(base, no quantity clause)
    assert "id:[207]" in out
    assert "quantity:>=100" in out and "quantity:>=10)" in out   # >=10 as a full token (closed by ')')
    assert out.index("quantity:>=100") < out.index("quantity:>=10)")   # SS threshold emitted before S

def test_base_E_reaches_deep_thresholds():
    out = emit_quantities([IMP[1]])          # base E -> up to quantity:>=1000000 for SS
    assert "quantity:>=1000000" in out and "id:[199]" in out

def test_per_element_hue_used_not_family():
    out = emit_quantities([IMP[2]])          # nature rune -> per-element green #ff2e8b57, not family indigo
    assert "#ff2e8b57" in out

def test_iron_gated():
    out = emit_quantities(IMP)
    assert out.count("rule (IRONMAN") == out.count("rule (")   # every terminal rule iron-gated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_quantities.py -q`
Expected: FAIL (`cannot import name 'emit_quantities'`).

- [ ] **Step 3: Implement** — add to `src/osrs_planner/lootfilter/emit.py` (extend the palette import):

```python
from osrs_planner.lootfilter.palette import GRADE_ORDER, quantity_display_grade   # add to the palette import block

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_quantities.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_emit_quantities.py
git commit -m "feat(loot-filter): emit_quantities — base tier + ×10 escalation in identity hue"
```

---

## Task 6: `emit_families` skips ranked families

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (`emit_families`)
- Test: `tests/lootfilter/test_emit_families.py` (extend the existing file)

**Interfaces:**
- Produces: `emit.emit_families(family_ids: dict, skip: set[str] = frozenset()) -> str` — additionally skips any family in `skip` (on top of the existing gear/empty/no-hue skips). Backward-compatible default (skips nothing new).

- [ ] **Step 1: Write the failing test** — append to `tests/lootfilter/test_emit_families.py`:

```python
def test_emit_families_honours_skip_set():
    family_ids = {"herb": [100], "utility": [200]}
    out = emit_families(family_ids, skip={"herb"})
    assert "id:[100]" not in out and "FAM_HERB" not in out   # herb skipped (owned by quantities)
    assert "id:[200]" in out                                 # utility still emitted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_families.py::test_emit_families_honours_skip_set -q`
Expected: FAIL (`emit_families() got an unexpected keyword argument 'skip'`).

- [ ] **Step 3: Implement** — modify `emit_families` signature + guard:

```python
def emit_families(family_ids, skip=frozenset()):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_families.py -q`
Expected: PASS (both the existing and new test).

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_emit_families.py
git commit -m "feat(loot-filter): emit_families skip-set (ranked families owned by quantities)"
```

---

## Task 7: Integration — trim categories, wire generate, regen byte-stable filter

This is the only task that changes the committed filter output. It trims `category_rules()` of the
resource rows now owned by `quantities`, wires `quantities` into `generate_filter`, regenerates the
committed filter, and re-greens the golden / byte-stable / validator gates.

**Files:**
- Modify: `src/osrs_planner/lootfilter/categories.py` (trim `category_rules()`; keep `categorize()` whole)
- Modify: `src/osrs_planner/lootfilter/generate.py` (load importance, insert `quantities`, pass skip-set)
- Modify: `data/validate_loot_filter.py` (add `quantities` to the module-order subsequence)
- Modify: `tests/lootfilter/test_golden.py` (assert `quantities` present; trimmed category rules gone)
- Regen: `outputs/gilded-tome-iron.rs2f`
- Test: `tests/lootfilter/test_generate.py` (extend — module order includes quantities)

**Interfaces:**
- Consumes: `emit.emit_quantities`, `emit.hue_for`, `emit.emit_families(skip=…)`, `palette.GRADE_ORDER`.
- Produces: `generate.load_importance(data_dir) -> list[dict]`; updated module order.

- [ ] **Step 1: Write the failing tests**

Append to `tests/lootfilter/test_generate.py`:

```python
def test_module_order_has_quantities_between_gear_and_categories():
    from osrs_planner.lootfilter.generate import generate_filter
    f = generate_filter()
    order = ["settings", "custom", "notable", "trophies", "gear", "quantities",
             "categories", "families", "untradeables", "coins", "fallback"]
    idxs = [f.find(f"define:module:{m}") for m in order]
    assert all(i != -1 for i in idxs), [m for m, i in zip(order, idxs) if i == -1]
    assert idxs == sorted(idxs), "modules out of order"

def test_quantities_supersedes_resource_categories():
    from osrs_planner.lootfilter.generate import generate_filter
    from osrs_planner.lootfilter.categories import categorize
    f = generate_filter()
    # coal still styled (dark hue present via quantities) but the standalone "Coal" CATEGORY macro is gone
    assert "#ff2b2b2b" in f and "CAT_COAL" not in f
    assert categorize("Coal")["id"] == "ores"      # categorize() itself is UNCHANGED (still resolves)
```

Append to `tests/lootfilter/test_golden.py`:

```python
def test_quantities_module_present():
    assert "define:module:quantities" in F and "#define QUANTITY_FLOOR 0" in F
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_generate.py::test_module_order_has_quantities_between_gear_and_categories tests/lootfilter/test_golden.py::test_quantities_module_present -q`
Expected: FAIL (no quantities module yet).

- [ ] **Step 3: Trim `category_rules()`** — in `src/osrs_planner/lootfilter/categories.py`, replace the body of `category_rules()` so it emits ONLY the non-resource remainder (gear-metal cosmetics, planks→REMOVED, teleports, charged jewellery, potions). Remove the ores/bars/runes/gems/essence/ammo/logs/herbs/seeds/bones/food rows. **Leave `categorize()` and every table (`ORE_NAMES`, `RUNE_COLORS`, …) untouched** — `hue_for` depends on them.

```python
def category_rules():
    """(id, display, include_patterns, hue, exclude_patterns); the resource rows (ores/bars/runes/
    gems/essence/ammo/logs/herbs/seeds/bones/planks/food) now live in emit_quantities — this keeps
    only the non-bulk remainder. categorize() (the hue authority) is unchanged."""
    out = []
    for metal, hue in MATERIAL_COLORS.items():
        out.append(("gear", f"{metal.title()} gear", [f"{metal.title()} {p}" for p in GEAR_PIECES], hue, []))
    out.append(("teleports", "Teleports", TELEPORT_PATTERNS, _TELEPORT_HUE, []))
    out.append(("charged_jewellery", "Charged jewellery", JEWELLERY_PATTERNS, _JEWELLERY_HUE, []))
    for disp, pats, base in DIVINE_POTIONS:
        out.append(("potions", disp, pats, base, [], _DIVINE_BORDER))
    for disp, pats, hue in POTION_FAMILIES:
        out.append(("potions", disp, pats, hue, []))
    out.append(("potions", "Potions", ["*(1)", "*(2)", "*(3)", "*(4)"], _POTION_HUE, _POTION_EXCLUDES))
    return out
```

- [ ] **Step 4: Wire `generate_filter`** — in `src/osrs_planner/lootfilter/generate.py`:

Add a loader (after `load_family_ids`):

```python
def load_importance(data_dir: str = DATA) -> list[dict]:
    """Editorial base-importance records for emit_quantities (design §4)."""
    return json.load(open(os.path.join(data_dir, "loot_importance.json"), encoding="utf-8"))["records"]
```

In `generate_filter`, compute the skip-set and insert `quantities` above `categories`, and pass the
skip-set to `emit_families`. Replace the `parts += [...]` block:

```python
    importance = load_importance(data_dir)
    ranked_families = {r["family"] for r in importance}
    parts += [emit.emit_notable(load_recommended_ids(data_dir), load_rare_ids(data_dir)),
              emit.emit_trophies(clog),
              emit.emit_gear(load_gear_records(data_dir)),
              emit.emit_quantities(importance),           # ABOVE categories: resource piles, base tier + ×10 escalation
              emit.emit_categories(),                     # trimmed to gear-metal/teleports/jewellery/potions
              emit.emit_families(load_family_ids(data_dir), skip=ranked_families),
              emit.emit_untradeables(), emit.emit_coins(), emit.emit_fallback(),
              emit.emit_meta(title, description)]
```

- [ ] **Step 5: Update the filter validator** — in `data/validate_loot_filter.py`, add `quantities` to the `order` list:

```python
    order = ["settings", "custom", "notable", "trophies", "gear", "quantities", "categories", "families", "fallback"]
```

- [ ] **Step 6: Regenerate the committed filter**

Run: `./venv/bin/python scripts/lootfilter_demo.py`
Expected: prints `generic: .../gilded-tome-iron.rs2f | bytes <N> | rules <R>` (R noticeably higher than before — the quantity ladders) and a `tailored:` line. This rewrites `outputs/gilded-tome-iron.rs2f`.

- [ ] **Step 7: Run the full gate**

```bash
./venv/bin/python data/validate_loot_filter.py            # module order + IRON-gating + colours + macros
./venv/bin/python data/validate_loot_importance.py
./venv/bin/python data/verify_loot_importance.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: validators PASS; `test_byte_stable` PASS (committed == fresh); `test_golden` PASS; full suite green (only the 4 pre-existing `tests/drop_rates/` collection errors). If `test_generate`/`test_golden` reference a trimmed macro that still leaks, fix the trim; if byte-stable fails, you forgot to regen (Step 6).

- [ ] **Step 8: Commit**

```bash
git add src/osrs_planner/lootfilter/categories.py src/osrs_planner/lootfilter/generate.py data/validate_loot_filter.py outputs/gilded-tome-iron.rs2f tests/lootfilter/test_generate.py tests/lootfilter/test_golden.py
git commit -m "feat(loot-filter): wire quantities module; trim resource categories; byte-stable regen"
```

---

## Final delivery (controller-driven, not a TDD task)

After all tasks pass and the whole-branch review is clean:

1. **Regenerate the tailored Tiger0295 build.** The `quantities` module is account-independent, so it
   is already in `generate_filter`'s `parts` for the tailored path too. Fetch tiger0295's public
   collection-log (TempleOSRS via `osrs_planner.account.temple.parse_temple_clog`), build the account
   state (`osrs_planner.account.state.build_account_state("ironman", clog_obtained=…)`, empty bank),
   call `generate_filter(account_state=st, title="Tiger0295", description=<clog summary>)`, and write
   `outputs/gilded-tome-tiger0295.rs2f`. Commit it.
2. **Push + open PR**; hand the owner a commit-SHA raw URL for `outputs/gilded-tome-tiger0295.rs2f`
   to re-import into filterscape.xyz (commit-SHA URL busts FilterScape's parse-cache).
3. **Owner review gate:** the base tiers in `loot_importance.json` are editorial — surface the file
   (or a tier summary) for the owner to sanity-check and retune before/after merge.
4. Update memory (`project_runelite_loot_filters.md`, `MEMORY.md`) and `CLAUDE.md` with the
   quantity-tiers layer.

---

## Notes for the implementer

- **Byte-stability lives only in Task 7.** Tasks 1-6 add unwired pieces (model, data, helpers,
  emitters) that do NOT change `generate_filter()` output, so `test_byte_stable` stays green
  throughout. Task 7 is where the output changes and gets regenerated in the same commit.
- **The tier tables in Task 2 are the editorial deliverable.** If `test_ranarr_high_guam_low` or
  `test_cheap_staples_not_bottom` fail, fix the ranking tables — never weaken the test.
- **Rule-count / byte growth is expected** (each ranked resource emits a ladder of editable
  pickers). `validate_loot_filter.py` prints the rule count and byte size; there is no hard cap, but
  if the filter roughly triples in size, note it in the task report so the reviewer can weigh whether
  to make quantity tiers plain (non-editable) rules in a follow-up.
- **Do NOT touch `kg/*.json`** — this is filter-side only; the graph is unchanged.
