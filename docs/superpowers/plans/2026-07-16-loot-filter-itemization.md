# Loot-Filter Itemization (v3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the shareable ironman loot filter so far more drops carry a correct family colour, gear upgrades and important iron resources/uniques stand out, and the user can hand-recolour any item in the FilterScape UI.

**Architecture:** Two new **filter-side** data bricks — `recommended_equipment` (wiki Bucket) and `loot_families` (derived taxonomy) — feed the existing `src/osrs_planner/lootfilter/` emitter. The emitter grows new layers (custom highlight groups → notable → families/gear → value ramp) but keeps rule-count proportional to *colours*, not items (big `id:[…]` lists). Everything is source-grounded, verifier-gated, and byte-stable-regenerated. The KG (`kg/`, `assemble.py`) is untouched.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON data; the FilterScape `.rs2f` DSL; pytest. No new dependencies.

## Global Constraints

- **Run Python only via `./venv/bin/python`** (3.14).
- **Never fabricate:** every derived datum cites `source_url` + a verbatim `source_token`. Hues and gear-score weights are **editorial** → owner-review gate, not validator-checked.
- **Report-not-fail discipline:** structural violations hard-fail (exit 1); resolution/coverage residuals are printed and exit 0. Build **skips** unresolvable items, never invents them.
- **Byte-stable filter:** `open("outputs/gilded-tome-iron.rs2f").read() == generate_filter()` must hold (the `tests/lootfilter/test_byte_stable.py` gate). Regenerate the committed artifact via `write_filter(path, account_state=None)` — there is no `--update-golden` CLI.
- **Committed-data envelope:** every `data/*.json` brick output is `{"_provenance": {...}, "records": [...]}`, records deterministically sorted before writing.
- **FilterScape parser rules (do not break):** the filter MUST start with a module declaration; `meta{}` goes LAST; the macro name `IRON` is forbidden (collides with a built-in — use `IRONMAN`); every `rule (`/`apply (` is `IRONMAN`-gated; colours are 9-char `#aarrggbb`.
- **Test-collection gotcha:** load `data/*.py` modules in tests via `importlib.util.spec_from_file_location`, NOT `from data.X import …` (the `tests/data/__init__.py` package-shadow bug). Run the FULL suite before claiming green: `./venv/bin/python -m pytest -q --continue-on-collection-errors`.
- **Branch:** `feat/loot-filter-itemization` (already created off `main`, spec committed at `f452bc9`).

---

## File structure

**New (filter-side data bricks, all in `data/`):**
- `data/fetch_recommended_equipment.py` — wiki Bucket fetcher → `data/raw/recommended_equipment_bucket.json`
- `data/parse_recommended_equipment.py` — raw → `data/recommended_equipment.json`
- `data/verify_recommended_equipment.py` — structural (exit 1) + coverage (exit 0)
- `data/build_loot_families.py` — derives `data/loot_families.json` from equipment + recipe KG + name-suffix + overrides
- `data/loot_family_overrides.json` — owner escape hatch (hand-authored)
- `data/verify_loot_families.py` — structural (exit 1) + coverage (exit 0)

**Modified (the emitter package + validator):**
- `src/osrs_planner/lootfilter/palette.py` — family hue maps; make `style_for` table-driven; add `gear_score`
- `src/osrs_planner/lootfilter/categories.py` — consume `loot_families.json` for membership
- `src/osrs_planner/lootfilter/emit.py` — `emit_custom_highlights`, `emit_notable`, `emit_gear`
- `src/osrs_planner/lootfilter/generate.py` — new module order + `load_*` for the two new bricks
- `data/validate_loot_filter.py` — extend module-order assertion
- `outputs/gilded-tome-iron.rs2f` — regenerated committed artifact

**Tests:** one `tests/lootfilter/test_*.py` per new emitter function + `tests/data/test_*` per brick, reusing existing patterns.

---

## Phase 0 — Prerequisite: single-source the palette emphasis table

### Task 0: Make `style_for` read the `VALUE_GRADES` fields it currently ignores

**Files:**
- Modify: `src/osrs_planner/lootfilter/palette.py:35-53` (`style_for`)
- Test: `tests/lootfilter/test_palette.py`

**Interfaces:**
- Produces: `style_for(hue, grade, border=None)` — unchanged signature; now `beam`/`sound` come from the `VALUE_GRADES` emphasis dict, not hardcoded grade-membership literals.

**Context:** Today `VALUE_GRADES` rows carry `"beam"`/`"sound"`/`"bg_alpha"` keys that `style_for` never reads (it re-decides via `if grade in ("SS","S")`). Two sources of truth. This task makes the table authoritative so later itemization builds on live data. It must NOT change the emitted bytes (the current hardcoded logic and the table already agree).

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_palette.py  (add)
from osrs_planner.lootfilter.palette import style_for, VALUE_GRADES

def test_style_for_beam_comes_from_table_not_hardcode():
    # Flip the S-grade table row's beam off; style_for must reflect the TABLE.
    orig = dict(next(e for g,_m,e in VALUE_GRADES if g == "S"))
    row = next(e for g,_m,e in VALUE_GRADES if g == "S")
    row["beam"] = False
    try:
        s = style_for("#ff40e0d0", "S")
        assert "showLootbeam" not in s, "beam must be driven by the table's `beam` flag"
    finally:
        row.clear(); row.update(orig)

def test_style_for_beam_on_by_table():
    s = style_for("#ff40e0d0", "SS")
    assert s.get("showLootbeam") == "true" and s["lootbeamColor"] == "#ff40e0d0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_palette.py::test_style_for_beam_comes_from_table_not_hardcode -v`
Expected: FAIL (beam still hardcoded, ignores the flipped table flag).

- [ ] **Step 3: Rewrite `style_for` to read the table**

```python
# palette.py — replace the tail of style_for (the `if grade in (...)` block)
def style_for(hue: str, grade: str, border: str | None = None) -> dict[str, str]:
    emph = next(e for g, _m, e in VALUE_GRADES if g == grade)
    if grade in ("D", "E"):
        tc = ("#9e" if grade == "E" else "#ff") + hue[3:]
        s = {"textColor": tc, "textAccent": "1", "fontType": "1"}
        if grade == "E":
            s["menuSort"] = "-10000"
        return s
    s = {"backgroundColor": hue, "borderColor": border or _border_on(hue), "textColor": _text_on(hue),
         "fontType": str(emph["fontType"]), "textAccent": "3", "icon": "CurrentItem()"}
    if emph.get("sound"):
        s["sound"] = "3925"
    if emph.get("beam"):
        s["showLootbeam"] = "true"; s["lootbeamColor"] = hue
    return s
```

- [ ] **Step 4: Run the palette test + the byte-stable gate**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_palette.py tests/lootfilter/test_byte_stable.py -v`
Expected: PASS (the byte-stable test proves the emitted output is unchanged — table and old hardcode agreed).

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/palette.py tests/lootfilter/test_palette.py
git commit -m "refactor(loot-filter): style_for reads VALUE_GRADES beam/sound (kill dead-table divergence)"
```

---

## Phase 1 — The `recommended_equipment` brick

### Task 1: Fetch the `recommended_equipment` Bucket → `data/raw/`

**Files:**
- Create: `data/fetch_recommended_equipment.py`
- (Output, git-ignored during dev then committed): `data/raw/recommended_equipment_bucket.json`

**Interfaces:**
- Produces: a raw snapshot `{"_provenance": {...}, "bucket": [{"page_name": str, "json": str}, ...]}`.

**Context:** Clone `data/fetch_recipes.py`. The Bucket returns `{"bucket": [...], "error": None}`; each row is `{"page_name", "json"}` where `json` is a STRING. Verified live: 454 rows / 146 pages.

- [ ] **Step 1: Write the fetcher**

```python
# data/fetch_recommended_equipment.py
"""Fetch the OSRS-wiki `recommended_equipment` Bucket (written by Module:Recommended equipment)
into data/raw/. Same action=bucket API as fetch_recipes.py. Run: python data/fetch_recommended_equipment.py"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
BASE = "https://oldschool.runescape.wiki/api.php"; PAGE = 5000
FIELDS = ["page_name", "json"]

def run_query(q):
    url = BASE + "?action=bucket&format=json&query=" + urllib.parse.quote(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
        return json.load(r)

def fetch_all():
    sel = ",".join(f"'{f}'" for f in FIELDS)
    rows, off = [], 0
    while True:
        d = run_query(f"bucket('recommended_equipment').select({sel}).offset({off}).limit({PAGE}).run()")
        if d.get("error"):
            raise RuntimeError(f"recommended_equipment offset={off}: {d['error']}")
        b = d.get("bucket", [])
        rows.extend(b)
        print(f"  recommended_equipment: offset={off} got {len(b)} (total {len(rows)})")
        if len(b) < PAGE:
            break
        off += PAGE; time.sleep(0.5)
    rows.sort(key=lambda r: (str(r.get("page_name") or ""), str(r.get("json") or "")))
    return rows

def main():
    os.makedirs(RAW, exist_ok=True)
    rows = fetch_all()
    out = {"_provenance": {"domain": "recommended_equipment",
                           "source_url": "https://oldschool.runescape.wiki/w/Module:Recommended_equipment",
                           "license": "CC BY-NC-SA 3.0", "extraction_method": "Bucket API action=bucket",
                           "query": "bucket('recommended_equipment').select('page_name','json').run() [paginated]",
                           "row_count": len(rows)},
           "bucket": rows}
    with open(os.path.join(RAW, "recommended_equipment_bucket.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(rows)} rows -> data/raw/recommended_equipment_bucket.json")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the fetcher (network)**

Run: `./venv/bin/python data/fetch_recommended_equipment.py`
Expected: prints pagination lines and `wrote 4xx rows -> data/raw/recommended_equipment_bucket.json` (≈454).

- [ ] **Step 3: Sanity-check the snapshot**

Run: `./venv/bin/python -c "import json; d=json.load(open('data/raw/recommended_equipment_bucket.json')); print(len(d['bucket']), 'rows'); print(d['bucket'][0]['page_name'])"`
Expected: `~454 rows` and a page name.

- [ ] **Step 4: Commit**

```bash
git add data/fetch_recommended_equipment.py data/raw/recommended_equipment_bucket.json
git commit -m "feat(loot-filter): fetch recommended_equipment Bucket -> data/raw/"
```

---

### Task 2: Parse raw → `data/recommended_equipment.json`

**Files:**
- Create: `data/parse_recommended_equipment.py`
- Create (output): `data/recommended_equipment.json`
- Test: `tests/data/test_recommended_equipment.py`

**Interfaces:**
- Produces: `{"_provenance": {...}, "records": [{"item_name","item_id","page_name","style","slot","source_url","source_token"}]}` — one record per (item, page, slot). `item_id` resolved via `item_dictionary.json`; unresolved names are collected into `_unresolved` and disclosed, not emitted as records.

**Context:** The `json` field is a STRING → `json.loads` → `{"Recommended Equipment": {slot: [html_cell...]}, "style": txt}`. Clean names come from the regex `\[\[File:[^\]]*?\|link=([^\]|]+)\]\]` (verified). Resolve names to ids against `data/item_dictionary.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_recommended_equipment.py
import importlib.util, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
parse = _load("parse_recq", "data/parse_recommended_equipment.py")

def test_extract_link_names():
    cell = ('{"Recommended Equipment":{"cape":['
            '"<span>[[File:Graceful cape.png|link=Graceful cape]]</span>[[Graceful cape|Graceful cape]]"]}}')
    got = parse.extract_slot_items(cell)
    assert got == [("cape", "Graceful cape")]

def test_extract_skips_non_link_noise():
    assert parse.extract_slot_items('{"Recommended Equipment":{"ammo":["Arrows"]}}') == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/data/test_recommended_equipment.py -v`
Expected: FAIL (`extract_slot_items` not defined).

- [ ] **Step 3: Write the parser**

```python
# data/parse_recommended_equipment.py
"""Build data/recommended_equipment.json from the committed raw Bucket snapshot.
Clean item names come from the [[File:...|link=NAME]] targets in each rendered cell.
Run: python data/parse_recommended_equipment.py"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
LINK_RE = re.compile(r"\[\[File:[^\]]*?\|link=([^\]|]+)\]\]")
SRC_BASE = "https://oldschool.runescape.wiki/w/"

def extract_slot_items(json_str):
    """[(slot, item_name), ...] from a Bucket `json` string; dedup within a (slot) preserving order."""
    obj = json.loads(json_str)
    eq = obj.get("Recommended Equipment") or {}
    out, seen = [], set()
    for slot, cells in eq.items():
        for cell in (cells if isinstance(cells, list) else [cells]):
            for name in LINK_RE.findall(cell):
                key = (slot, name)
                if key not in seen:
                    seen.add(key); out.append((slot, name))
    return out

def build_records(bucket_rows, dict_recs):
    by_name = {}
    for r in dict_recs:
        by_name.setdefault(r["name"], r["item_id"])
    records, unresolved = [], {}
    for row in bucket_rows:
        page = row.get("page_name") or ""
        try:
            style = (json.loads(row["json"]).get("style") or "")
        except Exception:
            style = ""
        for slot, name in extract_slot_items(row["json"]):
            iid = by_name.get(name)
            if iid is None:
                unresolved[name] = unresolved.get(name, 0) + 1
                continue
            records.append({"item_name": name, "item_id": iid, "page_name": page, "style": style,
                            "slot": slot, "source_url": SRC_BASE + page.replace(" ", "_"),
                            "source_token": page})
    records.sort(key=lambda r: (r["item_id"], r["page_name"], r["slot"]))
    return records, unresolved

def main():
    raw = json.load(open(os.path.join(RAW, "recommended_equipment_bucket.json"), encoding="utf-8"))["bucket"]
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    records, unresolved = build_records(raw, dict_recs)
    distinct = sorted({r["item_id"] for r in records})
    envelope = {"_provenance": {"domain": "recommended_equipment",
                    "source_url": "https://oldschool.runescape.wiki/w/Module:Recommended_equipment",
                    "license": "CC BY-NC-SA 3.0", "record_count": len(records),
                    "distinct_items": len(distinct), "unresolved_names": len(unresolved),
                    "note": "one record per (item, page, slot); item names from [[File:|link=]] targets"},
                "records": records, "_unresolved": sorted(unresolved)}
    with open(os.path.join(HERE, "recommended_equipment.json"), "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(records)} records / {len(distinct)} distinct items; {len(unresolved)} unresolved names")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the unit test**

Run: `./venv/bin/python -m pytest tests/data/test_recommended_equipment.py -v`
Expected: PASS.

- [ ] **Step 5: Build the committed file + eyeball**

Run: `./venv/bin/python data/parse_recommended_equipment.py`
Expected: `wrote ~2xxx records / ~960 distinct items; ~N unresolved names`. Spot-check: `./venv/bin/python -c "import json; d=json.load(open('data/recommended_equipment.json')); print(d['_provenance']['distinct_items']); print([r['item_name'] for r in d['records'][:5]])"`

- [ ] **Step 6: Commit**

```bash
git add data/parse_recommended_equipment.py data/recommended_equipment.json tests/data/test_recommended_equipment.py
git commit -m "feat(loot-filter): parse recommended_equipment -> committed data (960 distinct items)"
```

---

### Task 3: Verify `recommended_equipment` (structural + coverage)

**Files:**
- Create: `data/verify_recommended_equipment.py`
- Test: `tests/data/test_verify_recommended_equipment.py`

**Interfaces:**
- Produces: CLI `main() -> int`. Structural checks hard-fail (exit 1): every record has `item_id` resolving in `item_dictionary.json`, non-empty `source_token`+`source_url`. Coverage (exit 0): prints distinct-item count, unresolved-name count, clog overlap.

**Context:** Clone the `errors`-list shape of `data/verify_item_families.py` (structural) plus a coverage tail like `data/verify_recipe_coverage.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_verify_recommended_equipment.py
import subprocess, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def test_verifier_passes_committed():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "data/verify_recommended_equipment.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASSED" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/data/test_verify_recommended_equipment.py -v`
Expected: FAIL (verifier file missing).

- [ ] **Step 3: Write the verifier**

```python
# data/verify_recommended_equipment.py
"""Source-grounding gate for data/recommended_equipment.json. Structural -> exit 1; coverage -> exit 0."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def main() -> int:
    data = json.load(open(os.path.join(HERE, "recommended_equipment.json"), encoding="utf-8"))
    recs = data["records"]
    dict_ids = {r["item_id"] for r in json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]}
    clog_ids = {r["item_id"] for r in json.load(open(os.path.join(HERE, "collection_log.json"), encoding="utf-8"))["records"]}
    errors = []
    for r in recs:
        if r["item_id"] not in dict_ids:
            errors.append(f"{r['item_name']} ({r['item_id']}) not in item_dictionary")
        if not r.get("source_token") or not r.get("source_url"):
            errors.append(f"{r['item_name']}: missing source_token/source_url")
    if errors:
        print(f"RECOMMENDED-EQUIPMENT VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    distinct = {r["item_id"] for r in recs}
    non_clog = distinct - clog_ids
    print(f"RECOMMENDED-EQUIPMENT VERIFICATION PASSED — {len(recs)} records / {len(distinct)} distinct items source-grounded.")
    print(f"  coverage: {len(non_clog)} distinct items NOT in the collection log (the complementary gap); "
          f"{len(data.get('_unresolved', []))} unresolved names disclosed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the verifier + its test**

Run: `./venv/bin/python data/verify_recommended_equipment.py && ./venv/bin/python -m pytest tests/data/test_verify_recommended_equipment.py -v`
Expected: `PASSED` with `~555 distinct items NOT in the collection log`, and test PASS.

- [ ] **Step 5: Commit**

```bash
git add data/verify_recommended_equipment.py tests/data/test_verify_recommended_equipment.py
git commit -m "feat(loot-filter): verify_recommended_equipment (grounding + clog-gap coverage)"
```

---

## Phase 2 — The `loot_families` brick

### Task 4: Build `data/loot_families.json` (derived taxonomy)

**Files:**
- Create: `data/build_loot_families.py`
- Create: `data/loot_family_overrides.json` (start `{"_provenance": {"note": "owner overrides"}, "records": []}`)
- Create (output): `data/loot_families.json`
- Test: `tests/data/test_loot_families.py`

**Interfaces:**
- Produces: `{"_provenance": {...}, "records": [{"item_id","family","source_signal","source_token","source_url"}]}`, one record per classified item, most-specific signal winning. Families: `gear`, `utility`, `herb`, `potion`, `food`, `raw_fish`, `seed`, `ore`, `bar`, `log`, `rune`, `ammo`, `gem`, `bones`, `secondary`, plus override-supplied families.

**Context:** Derivation signals, in precedence order (first match wins), all grounded:
1. **overrides** (`loot_family_overrides.json`) — `source_signal="override"`.
2. **name-suffix families** (highest precision): seed/ore/bar/log/rune/ammo/gem/bones by suffix over `item_dictionary.json` names — `source_signal="name_suffix:<suffix>"`, `source_token=<the name>`.
3. **recipe-derived** herb (grimy→clean Herblore, verified 38 recipes) / food (Cooking-produced) / potion (Herblore-produced) — `source_signal="recipe:<skill>"`, `source_token=<recipe page or item name>`.
4. **equipment** gear (has a combat score > 0) vs utility (equippable, score ≤ 0) from `items_equipment.json` — `source_signal="equipment_slot:<slot>"` / `"equipment_utility"`.

Grimy→clean and equipment shapes are verified. Keep the builder deterministic (sort records by `item_id`).

- [ ] **Step 1: Write the failing test (the load-bearing derivations)**

```python
# tests/data/test_loot_families.py
import importlib.util, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b = _load("build_loot_families", "data/build_loot_families.py")

def test_suffix_family_seed():
    fam, sig = b.suffix_family("Ranarr seed")
    assert fam == "seed" and sig.startswith("name_suffix")

def test_grimy_herb_family_from_kg():
    fams = b.recipe_families()          # {item_name: (family, signal)}
    assert fams.get("Grimy ranarr", (None,))[0] == "herb"
    assert fams.get("Ranarr weed", (None,))[0] == "herb"

def test_gear_vs_utility_split():
    # a real combat body has family gear; a statless equippable is utility
    eq = b.equipment_families()         # {item_id: (family, signal)}
    # Bandos chestplate id 11832 (combat) -> gear ; Games necklace(8) id 3853 -> utility
    assert eq.get(11832, (None,))[0] == "gear"
    assert eq.get(3853, (None,))[0] == "utility"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/data/test_loot_families.py -v`
Expected: FAIL (functions not defined). *(If the sample item ids differ, correct them from a quick `grep` of `items_equipment.json` before implementing — do not guess.)*

- [ ] **Step 3: Write the builder**

```python
# data/build_loot_families.py
"""Derive data/loot_families.json: item_id -> resource family, from equipment slot + recipe grammar
+ name suffix + owner overrides. Filter-side (read by lootfilter, NOT assemble.py). Deterministic.
Run: python data/build_loot_families.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = "https://oldschool.runescape.wiki/w/"

# (suffix, family) — order matters; longer/more-specific suffixes first.
SUFFIX_FAMILIES = [(" seedling", "seed"), (" seed", "seed"), (" logs", "log"), (" log", "log"),
                   (" ore", "ore"), (" bar", "bar"), (" rune", "rune"), (" arrow", "ammo"),
                   (" bolts", "ammo"), (" dart", "ammo"), (" javelin", "ammo"), (" bones", "bones"),
                   (" ashes", "bones")]

def suffix_family(name):
    low = name.lower()
    for suf, fam in SUFFIX_FAMILIES:
        if low.endswith(suf):
            return fam, f"name_suffix:{suf.strip()}"
    return None, None

def _kg():
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))["nodes"]
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))["edges"]
    return nodes, edges

def recipe_families():
    """{item_name: (family, signal)} — herb (grimy->clean Herblore), food (Cooking-produced)."""
    nodes, edges = _kg()
    by_id = {n["id"]: n for n in nodes}
    cons, prod = {}, {}
    for e in edges:
        if e["type"] == "consumes": cons.setdefault(e["src"], []).append(e["dst"])
        elif e["type"] == "produces": prod.setdefault(e["src"], []).append(e["dst"])
    nm = lambda nid: (by_id.get(nid) or {}).get("name")
    out = {}
    for n in nodes:
        if n.get("kind") != "recipe":
            continue
        xp = (n.get("data") or {}).get("xp") or {}
        prods = [nm(p) for p in prod.get(n["id"], []) if nm(p)]
        conss = [nm(c) for c in cons.get(n["id"], []) if nm(c)]
        if "Herblore" in xp:
            grimy = [c for c in conss if c.startswith("Grimy ")]
            if grimy:                                  # a cleaning recipe: Grimy X -> X
                for c in grimy:
                    out.setdefault(c, ("herb", "recipe:Herblore"))
                for p in prods:                        # the produced clean herb(s)
                    out.setdefault(p, ("herb", "recipe:Herblore"))
        if "Cooking" in xp:
            for p in prods:
                out.setdefault(p, ("food", "recipe:Cooking"))
    return out

def equipment_families():
    """{item_id: (family, signal)} — gear (combat score > 0) vs utility (equippable, <= 0)."""
    recs = json.load(open(os.path.join(HERE, "items_equipment.json"), encoding="utf-8"))["records"]
    out = {}
    for r in recs:
        iid = r.get("item_id")
        if iid is None:
            continue
        s = r["stats"]; g = lambda k: s.get(k) if isinstance(s.get(k), (int, float)) else 0
        atk = max(g("stab_attack_bonus"), g("slash_attack_bonus"), g("crush_attack_bonus"),
                  g("range_attack_bonus"), g("magic_attack_bonus"))
        dfn = g("stab_defence_bonus")+g("slash_defence_bonus")+g("crush_defence_bonus")+g("range_defence_bonus")+g("magic_defence_bonus")
        score = atk + dfn + g("strength_bonus") + g("ranged_strength_bonus") + g("magic_damage_bonus") + g("prayer_bonus")
        fam = "gear" if score > 0 else "utility"
        out[iid] = (fam, f"equipment_slot:{r['slot']}" if fam == "gear" else "equipment_utility")
    return out

def build():
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    name_to_id = {}
    for r in dict_recs:
        name_to_id.setdefault(r["name"], r["item_id"])
    id_to_name = {r["item_id"]: r["name"] for r in dict_recs}
    overrides = json.load(open(os.path.join(HERE, "loot_family_overrides.json"), encoding="utf-8"))["records"]
    rec_fams = recipe_families()
    eq_fams = equipment_families()

    fam_by_id = {}  # item_id -> (family, signal, source_token)
    def claim(iid, fam, sig, token):
        if iid is not None and iid not in fam_by_id:
            fam_by_id[iid] = (fam, sig, token)

    # precedence: overrides > name-suffix > recipe > equipment
    for o in overrides:
        claim(o["item_id"], o["family"], "override", o.get("source_token", id_to_name.get(o["item_id"], "")))
    for name, iid in name_to_id.items():
        fam, sig = suffix_family(name)
        if fam:
            claim(iid, fam, sig, name)
    for name, (fam, sig) in rec_fams.items():
        claim(name_to_id.get(name), fam, sig, name)
    for iid, (fam, sig) in eq_fams.items():
        claim(iid, fam, sig, id_to_name.get(iid, ""))

    records = [{"item_id": iid, "family": fam, "source_signal": sig,
                "source_token": token, "source_url": SRC + (id_to_name.get(iid, "").replace(" ", "_"))}
               for iid, (fam, sig, token) in fam_by_id.items()]
    records.sort(key=lambda r: r["item_id"])
    return records

def main():
    records = build()
    from collections import Counter
    dist = Counter(r["family"] for r in records)
    env = {"_provenance": {"domain": "loot_families", "license": "CC BY-NC-SA 3.0",
                "note": "derived filter-side taxonomy; precedence override>suffix>recipe>equipment",
                "record_count": len(records), "family_distribution": dict(dist)},
           "records": records}
    with open(os.path.join(HERE, "loot_families.json"), "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(records)} records; families: {dict(dist)}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the unit tests**

Run: `./venv/bin/python -m pytest tests/data/test_loot_families.py -v`
Expected: PASS. If a sample id was wrong, fix the TEST id from `items_equipment.json`, not the builder.

- [ ] **Step 5: Build + eyeball the distribution**

Run: `./venv/bin/python data/build_loot_families.py`
Expected: `wrote ~5xxx records; families: {'gear': ~2600, 'utility': ~1600, 'ammo': ~360, ...}`. Confirm gear+utility+resource families sum in the thousands.

- [ ] **Step 6: Commit**

```bash
git add data/build_loot_families.py data/loot_family_overrides.json data/loot_families.json tests/data/test_loot_families.py
git commit -m "feat(loot-filter): derive loot_families.json (equipment + recipe + suffix, ~59% classified)"
```

---

### Task 5: Verify `loot_families` (structural + coverage)

**Files:**
- Create: `data/verify_loot_families.py`
- Test: `tests/data/test_verify_loot_families.py`

**Interfaces:**
- Produces: CLI `main() -> int`. Structural (exit 1): every record `item_id` in `item_dictionary.json`; every record has `source_signal`+`source_token`+`source_url`; a `source_signal` starting `recipe:`/`name_suffix:`/`equipment_`/`override` (closed vocab). Coverage (exit 0): print per-family counts + % of dictionary classified.

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_verify_loot_families.py
import subprocess, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def test_verifier_passes_committed():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "data/verify_loot_families.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASSED" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/data/test_verify_loot_families.py -v`
Expected: FAIL (missing file).

- [ ] **Step 3: Write the verifier**

```python
# data/verify_loot_families.py
"""Source-grounding gate for data/loot_families.json. Structural -> exit 1; coverage -> exit 0."""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
VALID_PREFIX = ("recipe:", "name_suffix:", "equipment_slot:", "equipment_utility", "override")

def main() -> int:
    data = json.load(open(os.path.join(HERE, "loot_families.json"), encoding="utf-8"))
    recs = data["records"]
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    dict_ids = {r["item_id"] for r in dict_recs}
    errors, seen = [], set()
    for r in recs:
        if r["item_id"] not in dict_ids:
            errors.append(f"{r['item_id']}: not in item_dictionary")
        if r["item_id"] in seen:
            errors.append(f"{r['item_id']}: duplicate family assignment")
        seen.add(r["item_id"])
        if not (r.get("source_signal") and r.get("source_token") and r.get("source_url")):
            errors.append(f"{r['item_id']}: missing source_signal/token/url")
        if not any(str(r.get("source_signal","")).startswith(p) for p in VALID_PREFIX):
            errors.append(f"{r['item_id']}: bad source_signal '{r.get('source_signal')}'")
    if errors:
        print(f"LOOT-FAMILIES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    dist = Counter(r["family"] for r in recs)
    pct = 100.0 * len({r["item_id"] for r in recs}) / len(dict_ids)
    print(f"LOOT-FAMILIES VERIFICATION PASSED — {len(recs)} items classified into {len(dist)} families.")
    print(f"  coverage: {pct:.1f}% of the {len(dict_ids)}-item dictionary; families: {dict(dist)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the verifier + test**

Run: `./venv/bin/python data/verify_loot_families.py && ./venv/bin/python -m pytest tests/data/test_verify_loot_families.py -v`
Expected: `PASSED`, coverage printed, test PASS.

- [ ] **Step 5: Commit**

```bash
git add data/verify_loot_families.py tests/data/test_verify_loot_families.py
git commit -m "feat(loot-filter): verify_loot_families (grounding + coverage report)"
```

---

## Phase 3 — Emitter + generator

### Task 6: Family hue map + `gear_score` in `palette.py`

**Files:**
- Modify: `src/osrs_planner/lootfilter/palette.py` (add `FAMILY_HUES`, `gear_score`, `GEAR_TIERS`)
- Test: `tests/lootfilter/test_palette.py`

**Interfaces:**
- Produces: `FAMILY_HUES: dict[str,str]` (family → 9-char ARGB; **owner-reviewed editorial defaults**); `gear_score(stats: dict) -> int`; `GEAR_TIERS: list[tuple[str,int]]` (grade, min-percentile-or-score) for within-slot tiering.

**Context:** Hues are editorial — ship sensible defaults reusing existing palette values where a family already has a colour (e.g. reuse the ore/log/rune maps). New families (herb/seed/secondary/utility/food) get defaults the owner refines in live iteration. This is a genuine owner-review gate, not a placeholder.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_palette.py  (add)
from osrs_planner.lootfilter.palette import FAMILY_HUES, gear_score

def test_every_family_has_a_valid_hue():
    for fam in ("gear","utility","herb","potion","food","raw_fish","seed","ore","bar","log",
                "rune","ammo","gem","bones","secondary"):
        h = FAMILY_HUES[fam]
        assert len(h) == 9 and h.startswith("#")

def test_gear_score_ranks_combat_over_cosmetic():
    combat = {"stab_defence_bonus": 100, "slash_defence_bonus": 100}
    cosmetic = {k: 0 for k in ("stab_defence_bonus",)}
    assert gear_score(combat) > gear_score(cosmetic) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_palette.py::test_every_family_has_a_valid_hue -v`
Expected: FAIL (`FAMILY_HUES` undefined).

- [ ] **Step 3: Add the family hues + gear score**

```python
# palette.py  (append)
# Family identity hues (design §3). EDITORIAL — owner-reviewed; refined in live in-game iteration.
FAMILY_HUES = {
    "gear":      "#ff8fa4b8",  # neutral steel — gear tiers escalate via emphasis, not hue
    "utility":   "#ff4dd0e1",  # cyan-teal (teleports/tools/charged jewellery neighbourhood)
    "herb":      "#ff2f7d3a",  # herb green
    "potion":    "#ff9b30c0",  # potion violet (per-liquid sub-hues stay in categories.py)
    "food":      "#ffe0533a",  # warm coral (matches existing _FOOD_HUE)
    "raw_fish":  "#ff7fb0c0",  # pale sea-blue
    "seed":      "#ff6b8f3a",  # seed olive
    "ore":       "#ffa05a3a",  # ore earth (ores keep per-name hues in categories.py)
    "bar":       "#ffb5892a",  # bar bronze-amber
    "log":       "#ffb8895a",  # log tan (matches existing LOG_COLORS oak)
    "rune":      "#ff7060d0",  # rune indigo (per-element hues stay in categories.py)
    "ammo":      "#ff8c2f5b",  # deep wine (matches existing _AMMO_HUE)
    "gem":       "#ff30c0a0",  # gem teal-green
    "bones":     "#ffc7b9a0",  # bone (matches existing _PRAYER_HUE)
    "secondary": "#ffb0a060",  # secondary khaki
}

def gear_score(stats: dict) -> int:
    """Combat quality of an equipment stat block (design §7). Editorial weights."""
    g = lambda k: stats.get(k) if isinstance(stats.get(k), (int, float)) else 0
    atk = max(g("stab_attack_bonus"), g("slash_attack_bonus"), g("crush_attack_bonus"),
              g("range_attack_bonus"), g("magic_attack_bonus"))
    dfn = (g("stab_defence_bonus")+g("slash_defence_bonus")+g("crush_defence_bonus")
           + g("range_defence_bonus")+g("magic_defence_bonus"))
    return atk + dfn + g("strength_bonus") + g("ranged_strength_bonus") + g("magic_damage_bonus") + g("prayer_bonus")

# Within-slot gear tiers: fraction of the slot's max score -> emphasis grade (design §7).
GEAR_TIERS = [("S", 0.80), ("A", 0.55), ("B", 0.30), ("C", 0.0)]
```

- [ ] **Step 4: Run tests + byte-stable**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_palette.py -v`
Expected: PASS. (No emitter wired yet → byte-stable unaffected.)

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/palette.py tests/lootfilter/test_palette.py
git commit -m "feat(loot-filter): family hue map + gear_score/GEAR_TIERS (editorial defaults)"
```

---

### Task 7: `emit_gear()` — stat-tiered gear module

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add `emit_gear`)
- Test: `tests/lootfilter/test_emit_gear.py`

**Interfaces:**
- Consumes: `FAMILY_HUES`, `gear_score`, `GEAR_TIERS`, `style_for`, `emit_style_input`, `emit_module`, `_id_list`, `_macro_name`.
- Produces: `emit_gear(gear_records) -> str` where `gear_records = [{"item_id","slot","stats"}]` (the equipment records for `gear`-family items). Emits, per slot, per-tier `id:[…]` picker rules (top tier brightest). One module `gear`.

**Context:** Model on `emit_trophies` (`emit.py:91`). Compute each slot's max score, bucket items into `GEAR_TIERS` by `score/max`, emit one editable style-input per (slot, tier) over that tier's id-list. Hue = `FAMILY_HUES["gear"]`; emphasis grade from the tier.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_emit_gear.py
from osrs_planner.lootfilter.emit import emit_gear

def test_gear_module_tiers_by_slot():
    recs = [
        {"item_id": 100, "slot": "body", "stats": {"stab_defence_bonus": 200}},  # top
        {"item_id": 101, "slot": "body", "stats": {"stab_defence_bonus": 10}},   # low
    ]
    out = emit_gear(recs)
    assert "define:module:gear" in out
    assert "id:[100]" in out and "id:[101]" in out
    # top item must be in a higher grade rule than the low item (S before C in emit order)
    assert out.index("id:[100]") < out.index("id:[101]")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_gear.py -v`
Expected: FAIL (`emit_gear` undefined).

- [ ] **Step 3: Implement `emit_gear`**

```python
# emit.py  (add; import FAMILY_HUES, gear_score, GEAR_TIERS, style_for from palette)
def emit_gear(gear_records) -> str:
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
            frac = score / top
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
```

- [ ] **Step 4: Run the test**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_gear.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_emit_gear.py
git commit -m "feat(loot-filter): emit_gear — stat-tiered gear by slot"
```

---

### Task 8: `emit_notable()` — recommended + rare + value lift

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add `emit_notable`)
- Test: `tests/lootfilter/test_emit_notable.py`

**Interfaces:**
- Consumes: `emit_style_input`, `emit_module`, `_id_list`, `emit_rule`, `IRONMAN`.
- Produces: `emit_notable(recommended_ids, rare_ids) -> str`. Emits one module `notable` with: a border-lift editable style over `recommended_ids` (no beam), a beam style over `rare_ids`, and a `value:>=500000` beam rule. Beam colour uses each rule's own hue (a notable violet + the value-red already in the fallback palette). Clog trophies stay in `emit_trophies` (unchanged).

**Context:** Beam policy §5: recommended-only = border lift, NO beam; rare + value≥500k = beam. Model id-list rules on `emit_trophies`.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_emit_notable.py
from osrs_planner.lootfilter.emit import emit_notable

def test_notable_module_layers():
    out = emit_notable(recommended_ids=[10, 11], rare_ids=[20])
    assert "define:module:notable" in out
    assert "id:[10, 11]" in out          # recommended list
    assert "id:[20]" in out              # rare list beams
    assert "value:>=500000" in out       # value safety-net beam
    # recommended-only rule must NOT carry a beam; the rare + value rules must
    assert out.count("showLootbeam = true") >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_notable.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `emit_notable`**

```python
# emit.py  (add)
_NOTABLE_HUE = "#ffd08a20"   # amber "known target" border for recommended items
_RARE_HUE = "#ffff45d6"      # magenta rare-drop beam
_VALUE_HUE = "#ffff2b2b"     # red high-value beam (matches FALLBACK_HUES SS)

def emit_notable(recommended_ids, rare_ids) -> str:
    used, lines = set(), []
    if recommended_ids:
        style = {"backgroundColor": _NOTABLE_HUE, "borderColor": "#ffffffff",
                 "textColor": _text_on(_NOTABLE_HUE), "fontType": "2", "textAccent": "3"}
        lines.append(emit_style_input("notable", "Recommended-for-activity", "Notable",
            _macro_name("NOTABLE", "recommended", used), f"{IRONMAN} && {_id_list(recommended_ids)}", style))
    if rare_ids:
        style = {"backgroundColor": _RARE_HUE, "borderColor": "#ffffffff", "textColor": _text_on(_RARE_HUE),
                 "fontType": "3", "textAccent": "3", "showLootbeam": "true", "lootbeamColor": _RARE_HUE, "sound": "3925"}
        lines.append(emit_style_input("notable", "Rare drop", "Notable",
            _macro_name("NOTABLE", "rare", used), f"{IRONMAN} && {_id_list(rare_ids)}", style))
    vstyle = {"backgroundColor": _VALUE_HUE, "borderColor": "#ffffffff", "textColor": _text_on(_VALUE_HUE),
              "fontType": "3", "textAccent": "3", "showLootbeam": "true", "lootbeamColor": _VALUE_HUE, "sound": "3925"}
    lines.append(emit_style_input("notable", "High value (>=500k)", "Notable",
        _macro_name("NOTABLE", "value", used), f"{IRONMAN} && value:>=500000", vstyle))
    return emit_module("notable", "Notable", "\n".join(lines), "Recommended / rare / high-value")
```

- [ ] **Step 4: Run the test**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_notable.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_emit_notable.py
git commit -m "feat(loot-filter): emit_notable — recommended border + rare/value beams (>=500k)"
```

---

### Task 9: `emit_custom_highlights()` — manual override groups + hide bank

**Files:**
- Modify: `src/osrs_planner/lootfilter/emit.py` (add `emit_custom_highlights`)
- Test: `tests/lootfilter/test_emit_custom.py`

**Interfaces:**
- Produces: `emit_custom_highlights(free=6, tiers=("SS","S","A","B","C")) -> str`. One module `custom` emitted directly under settings. For each free slot: a `stringlist` input + a `style` input + an `apply`/`rule` matching `name:$LIST`. For each tier slot: a `stringlist` that injects into that notable tier's style. Plus a hide-bank (`Hide-listed`, `Hide-if-quantity-under-N`). All empty/off by default.

**Context:** FilterScape has no native per-item override (spec §2); this is the reference-filter pattern. Free-solo `stringlist` chip boxes accept arbitrary typed item names. Uses `emit_style_input` + a `stringlist`-input helper (new tiny helper `emit_list_input`).

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_emit_custom.py
from osrs_planner.lootfilter.emit import emit_custom_highlights

def test_custom_module_has_free_and_hide_slots():
    out = emit_custom_highlights(free=6)
    assert "define:module:custom" in out
    assert out.count("type: stringlist") >= 6          # >=6 free-color name lists
    assert "type: style" in out                        # each free slot has a style picker
    assert "Hide" in out                               # hide bank present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_custom.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the helper + `emit_custom_highlights`**

```python
# emit.py  (add)
def emit_list_input(module_id: str, label: str, group: str, macro: str, default: str = "") -> str:
    """A `type: stringlist` input + its #define (default empty). Users type item names into it."""
    decl = f"/*@ define:input:{module_id}\ntype: stringlist\nlabel: {label}\ngroup: {group}\n*/"
    return f"{decl}\n#define {macro} [{default}]"

def emit_custom_highlights(free: int = 6, tiers=("SS", "S", "A", "B", "C")) -> str:
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
```

- [ ] **Step 4: Run the test**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_emit_custom.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_emit_custom.py
git commit -m "feat(loot-filter): emit_custom_highlights — manual override groups + hide bank"
```

---

### Task 10: `categories.py` consumes `loot_families.json`

**Files:**
- Modify: `src/osrs_planner/lootfilter/categories.py` (add `families_by_id()` loader + family→hue lookup)
- Modify: `src/osrs_planner/lootfilter/emit.py` (`emit_categories` emits one id-list picker per family from the data)
- Test: `tests/lootfilter/test_categories.py`

**Interfaces:**
- Produces: `categories.families_by_id(data_dir) -> dict[int, str]` (item_id → family). `emit_categories(family_ids)` where `family_ids = {family: [item_id, ...]}` emits one editable style-input per family over its id-list, hue from `FAMILY_HUES`. The legacy name-glob families (potion sub-liquids, teleport, charged_jewellery) that must stay open remain as today.

**Context:** Today `emit_categories()` iterates `category_rules()` (name globs). New: derive membership id-lists from `loot_families.json`, emit per-family. Keep the hand-authored name-glob families that have no clean signal (potion liquids etc.) as a supplementary pass.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_categories.py  (add)
from osrs_planner.lootfilter import categories

def test_families_by_id_loads():
    fams = categories.families_by_id()
    assert isinstance(fams, dict) and len(fams) > 3000
    assert set(fams.values()) & {"gear", "herb", "ore", "ammo"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_categories.py::test_families_by_id_loads -v`
Expected: FAIL (`families_by_id` undefined).

- [ ] **Step 3: Add the loader + the family emitter**

```python
# categories.py  (add)
import json, os
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")

def families_by_id(data_dir: str = _DATA) -> dict:
    recs = json.load(open(os.path.join(data_dir, "loot_families.json"), encoding="utf-8"))["records"]
    return {r["item_id"]: r["family"] for r in recs}
```

```python
# emit.py  (add new function; leave existing emit_categories for the name-glob supplement or rename)
def emit_families(family_ids) -> str:
    """One editable style-input per family, over its id-list. family_ids: {family: [item_id]}."""
    from osrs_planner.lootfilter.palette import FAMILY_HUES
    used, lines = set(), []
    for fam in sorted(family_ids):
        ids = family_ids[fam]
        if not ids or fam not in FAMILY_HUES:
            continue
        if fam == "gear":       # gear handled by emit_gear (stat-tiered) — skip here
            continue
        lines.append(emit_style_input("families", fam.replace("_", " ").title(), "Families",
            _macro_name("FAM", fam, used), f"{IRONMAN} && {_id_list(ids)}",
            _flat_panel(FAMILY_HUES[fam])))
    return emit_module("families", "Resource families", "\n".join(lines), "By derived family")
```

- [ ] **Step 4: Run the test**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_categories.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/categories.py src/osrs_planner/lootfilter/emit.py tests/lootfilter/test_categories.py
git commit -m "feat(loot-filter): emit_families from loot_families.json (per-family id-list pickers)"
```

---

### Task 11: `generate.py` — wire the new module order

**Files:**
- Modify: `src/osrs_planner/lootfilter/generate.py`
- Test: `tests/lootfilter/test_generate.py`

**Interfaces:**
- Consumes: all `emit_*` functions above + the new `load_*`.
- Produces: `generate_filter(account_state=None, ...)` emitting the §8 order: `settings → custom → notable → trophies → gear → families → coins → fallback → meta` (tailoring, when present, stays above trophies as today).

**Context:** Add loaders mirroring `load_clog_ids`. `load_recommended_ids` → `data/recommended_equipment.json`. `load_rare_ids` → `data/drop_rates.json` (rarer than 1/512). `load_gear_records`/`load_family_ids` → `data/loot_families.json` + `data/items_equipment.json`. Splice into the `parts` list.

- [ ] **Step 1: Write the failing test**

```python
# tests/lootfilter/test_generate.py  (add)
from osrs_planner.lootfilter.generate import generate_filter

def test_new_module_order():
    F = generate_filter()
    order = [F.index(f"define:module:{m}") for m in
             ("settings", "custom", "notable", "trophies", "gear", "families", "fallback")]
    assert order == sorted(order), "modules must be emitted in the §8 order"

def test_meta_is_last_and_starts_with_module():
    F = generate_filter()
    assert F.startswith("/*@ define:module:")
    assert F.rstrip().endswith("}") and F.index("meta {") > F.index("define:module:fallback")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_generate.py::test_new_module_order -v`
Expected: FAIL (no `custom`/`notable`/`gear`/`families` modules yet).

- [ ] **Step 3: Add loaders + new `parts` order**

```python
# generate.py  (add loaders)
def load_recommended_ids(data_dir: str = DATA) -> list[int]:
    recs = json.load(open(os.path.join(data_dir, "recommended_equipment.json"), encoding="utf-8"))["records"]
    return sorted({r["item_id"] for r in recs})

def load_rare_ids(data_dir: str = DATA, floor: float = 1/512) -> list[int]:
    recs = json.load(open(os.path.join(data_dir, "drop_rates.json"), encoding="utf-8"))["records"]
    rare = set()
    for r in recs:
        rate = r.get("drop_rate")
        if rate is not None and rate <= floor:
            rare.add(r["item_id"])
    return sorted(rare)

def load_gear_records(data_dir: str = DATA):
    from osrs_planner.lootfilter import categories
    fams = categories.families_by_id(data_dir)
    eq = json.load(open(os.path.join(data_dir, "items_equipment.json"), encoding="utf-8"))["records"]
    return [{"item_id": r["item_id"], "slot": r["slot"], "stats": r["stats"]}
            for r in eq if r.get("item_id") is not None and fams.get(r["item_id"]) == "gear"]

def load_family_ids(data_dir: str = DATA) -> dict:
    from collections import defaultdict
    from osrs_planner.lootfilter import categories
    out = defaultdict(list)
    for iid, fam in categories.families_by_id(data_dir).items():
        out[fam].append(iid)
    return dict(out)
```

```python
# generate.py  (replace the parts assembly in generate_filter)
    parts = [emit.emit_settings(), emit.emit_custom_highlights()]
    if account_state is not None:
        parts.append(tailor.emit_tailoring(account_state, set(clog), value_index=load_value_index(data_dir),
                                           rarity_index=load_clog_rarity(data_dir)))
    parts += [emit.emit_notable(load_recommended_ids(data_dir), load_rare_ids(data_dir)),
              emit.emit_trophies(clog),
              emit.emit_gear(load_gear_records(data_dir)),
              emit.emit_families(load_family_ids(data_dir)),
              emit.emit_untradeables(), emit.emit_coins(), emit.emit_fallback(),
              emit.emit_meta(title, description)]
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run the generate tests**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_generate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/lootfilter/generate.py tests/lootfilter/test_generate.py
git commit -m "feat(loot-filter): wire custom/notable/gear/families into the module order"
```

---

## Phase 4 — Validate, regenerate, and gate

### Task 12: Extend `validate_loot_filter.py` module-order assertion

**Files:**
- Modify: `data/validate_loot_filter.py:36-38`
- Test: `tests/lootfilter/test_validate.py`

**Interfaces:**
- Produces: the validator asserts the new module order `settings < custom < notable < trophies < gear < families < fallback`.

- [ ] **Step 1: Update the assertion**

```python
# validate_loot_filter.py — replace the module-order block (:36-38)
    order = ["settings", "custom", "notable", "trophies", "gear", "families", "fallback"]
    idxs = [text.find(f"define:module:{m}") for m in order]
    for m, i in zip(order, idxs):
        check(i != -1, f"module {m} missing")
    check(idxs == sorted(idxs), "modules out of order")
```

- [ ] **Step 2: Run validator test (will fail until Task 13 regenerates the artifact)**

Run: `./venv/bin/python -m pytest tests/lootfilter/test_validate.py -v`
Expected: may FAIL until the committed `.rs2f` is regenerated (Task 13). That is expected ordering — proceed to Task 13, then both pass.

- [ ] **Step 3: Commit**

```bash
git add data/validate_loot_filter.py
git commit -m "feat(loot-filter): validator enforces the new module order"
```

---

### Task 13: Regenerate the committed artifact + full green

**Files:**
- Modify: `outputs/gilded-tome-iron.rs2f` (regenerated)
- Modify: `tests/lootfilter/test_golden.py` (update spot-checks for the new modules)

**Interfaces:** none — this task makes the byte-stable gate and the full suite pass.

- [ ] **Step 1: Regenerate the committed filter**

Run:
```bash
./venv/bin/python -c "from osrs_planner.lootfilter.generate import write_filter; import os; \
write_filter(os.path.join('outputs','gilded-tome-iron.rs2f'), account_state=None)"
```
Expected: file rewritten (larger than before; ~150–250 KB).

- [ ] **Step 2: Run the structural validator on the regenerated file**

Run: `./venv/bin/python data/validate_loot_filter.py`
Expected: `PASSED` with the new rule/byte counts. Fix any violation it reports (e.g. an ungated rule) at the emitter level, then regenerate.

- [ ] **Step 3: Update golden spot-checks**

```python
# tests/lootfilter/test_golden.py — add assertions for the new layers
def test_new_layers_present():
    F = open(os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"), encoding="utf-8").read()
    for mod in ("custom", "notable", "gear", "families"):
        assert f"define:module:{mod}" in F
    assert "value:>=500000" in F           # value safety-net beam
```

- [ ] **Step 4: Run the FULL suite**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all loot-filter tests PASS (the 4 pre-existing `tests/drop_rates/` collection errors are unrelated per CLAUDE.md). In particular `tests/lootfilter/test_byte_stable.py` PASSES (committed == fresh).

- [ ] **Step 5: Commit**

```bash
git add outputs/gilded-tome-iron.rs2f tests/lootfilter/test_golden.py
git commit -m "feat(loot-filter): regenerate committed iron filter with itemization layers"
```

---

## Verification (end-to-end)

1. **Bricks reproduce:** `./venv/bin/python data/parse_recommended_equipment.py && ./venv/bin/python data/build_loot_families.py` — re-run produces byte-identical committed JSON (deterministic sort).
2. **Grounding gates green:** `./venv/bin/python data/verify_recommended_equipment.py && ./venv/bin/python data/verify_loot_families.py && ./venv/bin/python data/validate_loot_filter.py` — all print `PASSED`.
3. **Byte-stable + suite:** `./venv/bin/python -m pytest -q --continue-on-collection-errors` — loot-filter tests green, `test_byte_stable.py` proves `outputs/gilded-tome-iron.rs2f` == `generate_filter()`.
4. **FilterScape smoke test (manual):** import `outputs/gilded-tome-iron.rs2f` via a commit-SHA raw URL into filterscape.xyz; confirm it parses (starts with a module, meta last), the Custom-highlights module shows editable name lists + style pickers, and the Families/Gear modules render colour pickers. Type an item name into "Custom highlight 1 — items", set a colour, confirm it previews.
5. **Owner review (editorial):** the owner reviews `FAMILY_HUES`, the gear-score weights, and the beam thresholds in live in-game iteration (the PR #12 screenshot-by-screenshot pattern), refining hues against the wiki models.

---

## Notes for the executor

- **Owner-review gates are not blockers to code completion** — ship sensible editorial defaults (`FAMILY_HUES`, gear weights); the owner refines them live. They are marked editorial precisely because no validator can check them.
- **If a sample item id in a test is wrong** (ids drift), correct the TEST against `items_equipment.json`/`item_dictionary.json` — never bend the builder to a wrong id.
- **`SHOW_VALUE` default-off** (spec §8): add a `boolean` input to `emit_settings` defaulting the on-item value text off; the value ramp still functions. Fold this into Task 11 if not already present in settings.
- **Quantity-aware promotion (§7.1)** is explicitly phase-2/optional — do NOT build it in this plan; the base itemization ships first.
