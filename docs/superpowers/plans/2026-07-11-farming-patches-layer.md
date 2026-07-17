# Farming Patches Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ~90 `farming_patch:` nodes (one per patch-type × place) to the committed knowledge graph, each `located_in` its skeleton place, sourced from the OSRS wiki farming-patch tables.

**Architecture:** A bottom-up layer on the shop/NPC template — a fetch brick commits raw wiki table wikitext, a deterministic parser turns tables into typed patch rows, a builder resolves each row's `[[Place]]` link to a committed `place:` node and emits nodes + `located_in` edges, the assembler re-keys them into `kg/*.json`, and two verifiers (structural hard-fail + coverage report) gate it. Design spec: `docs/superpowers/specs/2026-07-11-farming-patches-layer-design.md`.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON graph; pytest; `urllib` against the OSRS Wiki `action=query`/`action=bucket` APIs.

## Global Constraints

Every task's requirements implicitly include these (values copied from the spec):

- **Python only via `./venv/bin/python`** (3.14). Full test suite: `./venv/bin/python -m pytest -q --continue-on-collection-errors` (the 4 `tests/drop_rates/` collection errors are pre-existing & unrelated — ignore them).
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run must produce **identical bytes**. Verified by a subprocess test.
- **Never fabricate:** every node traces to `source_url` + a **verbatim** `source_token`. Unresolved place / unparseable row → **reported by the coverage verifier, never invented**.
- **Report-not-fail vs hard-fail split:** structural violations (a node's datum not tracing to a snapshot row) → `verify_farming_patches.py` exits 1. Resolution/coverage residuals (FLAGs, deferred tail) → `verify_farming_coverage.py` exits 0.
- **NO coordinates this slice (spec D5):** the parser must never read `{{Map}}` coords or store a coordinate. `data` keys are exactly `patch_type`, `gardener` (optional), `source_url`, `source_token`.
- **`patch_type` is a closed vocab (spec D8):** the core 9 are locked in the parser's `_TYPE_PAGE` map + the verifiers' `CORE` set `{herb, allotment, flower, bush, hops, tree, fruit_tree, spirit_tree, coral}`; special-crop types are enumerated from the `Special patches/Patches` parse and validated by the hard-fail verifier (a node's `patch_type` must equal a parsed table type, else exit 1) — so no type can be fabricated outside the parsed source.
- **id = `farming_patch:` + `slugify(patch_type)` + `-` + `<place_slug>`** — `slugify` is dash-only (no underscores: `slugify("fruit_tree") == "fruit-tree"`); `<place_slug>` = the resolved place id's slug, or (FLAG) the trailing-link slug. Identity = (patch_type, place). **Injective by a committed fail-fast — NO order-dependent `-k` fallback** (that reintroduces the churn PR #26 killed).
- **`located_in` edges:** `cond_group=None`, `data={}`, `src`=patch (child), `dst`=`place:` (parent). Exactly matches the committed shop/npc `located_in` shape.
- **Tests that load `data/*.py` must use `importlib.util.spec_from_file_location`**, NOT `from data.X import` — `tests/data/__init__.py` shadows the `data` package in full-suite collection (passes isolated, ERRORs in the full run). Always run the FULL suite before claiming green.

---

### Task 1: Schema + enum foundation (flip `farming_patch` live)

Prove the vocabulary before any node is emitted: add the `NodeKind` enum member (the hard load-time gate), update its golden set-equality test, flip the schema entry live, and widen `located_in`'s domain. No instances yet — the graph is unchanged, `validate_kg` stays green.

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py:36` (add one `NodeKind` member)
- Modify: `tests/engine/test_kg_model.py:14-22` (add `"farming_patch"` to the golden set)
- Modify: `kg/schema.json:75` (flip `farming_patch` `reserved`→`live` + `data_keys`)
- Modify: `kg/schema.json:123` (add `farming_patch` to `located_in.domain`)

**Interfaces:**
- Produces: `NodeKind.FARMING_PATCH` (value `"farming_patch"`) — consumed by the builder (Task 4) and every node it emits.

- [ ] **Step 1: Update the golden enum test to expect the new member (failing test)**

In `tests/engine/test_kg_model.py`, add `"farming_patch"` to the expected set in `test_node_kind_members_match_schema_taxonomy`:

```python
def test_node_kind_members_match_schema_taxonomy():
    assert {k.value for k in NodeKind} == {
        "skill", "item", "monster", "quest", "access", "region",
        "account_type", "gear_loadout", "activity", "diary",
        "combat_achievement", "minigame", "clog_slot", "goal",
        "recipe", "equipment_bonuses",
        "place", "npc", "shop",
        "facility",
        "farming_patch",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py::test_node_kind_members_match_schema_taxonomy -q`
Expected: FAIL — the actual `{k.value for k in NodeKind}` lacks `"farming_patch"`.

- [ ] **Step 3: Add the enum member**

In `src/osrs_planner/engine/kg/model.py`, add one line immediately after the `FACILITY` member (line 36):

```python
    FACILITY = "facility"              # processing station (anvil/furnace/altar/range); requires_facility target
    FARMING_PATCH = "farming_patch"    # place x patch-type instance (P8); located_in a place
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py -q`
Expected: PASS (all model tests).

- [ ] **Step 5: Flip the schema entry live + widen the `located_in` domain**

In `kg/schema.json`, replace the `farming_patch` node-kind entry (line 75):

```json
    "farming_patch": {"status": "live", "key_prefix": "farming_patch:<slug>", "id_basis": "slug", "notes": "place x patch-type instance (P8); located_in a place. Roster slice: patch_type/gardener/provenance; instance_of + patch_type-node deferred.", "data_keys": ["patch_type", "gardener", "source_url", "source_token"]},
```

And in the `located_in` edge-kind entry (line 123), add `"farming_patch"` to `domain`:

```json
    "located_in": {"status": "live", "domain": ["place", "npc", "monster", "scenery", "shop", "farming_patch"], "range": ["place"], "dst": "required", "cond_group": "forbidden", "reified": false, "notes": "Containment TREE (decision 1): world > kingdom > city > district > scenery. farming_patch is a leaf child of a place."},
```

- [ ] **Step 6: Verify the graph still validates (unchanged) and is byte-stable**

Run: `./venv/bin/python data/validate_kg.py && ./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/`
Expected: validate_kg prints its normal summary with no new VIOLATION; `git diff --stat kg/` shows **no change** to `kg/*.json` (no farming nodes emitted yet).

- [ ] **Step 7: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py tests/engine/test_kg_model.py kg/schema.json
git commit -m "feat(farming): NodeKind.FARMING_PATCH + schema live + located_in domain widen"
```

---

### Task 2: Fetch brick + committed raw snapshots

Pull the farming-patch source from the wiki's structured layer — the category roster (the completeness anchor) + the raw wikitext of the location tables — and commit both as reproducible `data/raw/` snapshots. The deterministic parse lives in Task 3; this task is the network I/O + a pure infobox-classifier helper.

**Files:**
- Create: `data/fetch_farming_patches.py`
- Create (by running it): `data/raw/wiki_farming_patch_category.json`, `data/raw/wiki_farming_patch_tables.json`
- Test: `tests/data/test_fetch_farming_patches.py`

**Interfaces:**
- Produces: `classify_member(infoboxes: list[str]) -> str` returning one of `"patch_type" | "umbrella" | "place" | "npc" | "other"` — consumed by the coverage verifier (Task 6).
- Produces snapshot shapes: `wiki_farming_patch_category.json = {"_provenance": {...}, "members": {name: {"infoboxes": [...], "classification": str, "source_url": str}}}`; `wiki_farming_patch_tables.json = {"_provenance": {...}, "tables": {page: {"source_url": str, "wikitext": str}}}`.

- [ ] **Step 1: Write the failing test for the pure classifier helper**

```python
# tests/data/test_fetch_farming_patches.py
import importlib.util, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

def _load(mod_name, rel):
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

fetch = _load("fetch_farming_patches", "data/fetch_farming_patches.py")

def test_classify_member_routes_by_infobox():
    assert fetch.classify_member(["Infobox Scenery"]) == "patch_type"
    assert fetch.classify_member(["Infobox Location"]) == "place"     # Coral Nurseries
    assert fetch.classify_member(["Infobox NPC"]) == "npc"            # Chet
    assert fetch.classify_member([]) == "other"

def test_classify_member_umbrella_by_name_is_caller_concern():
    # Special patches has an Infobox but is treated as an umbrella by the coverage verifier,
    # not here; classify_member only reads infoboxes. Scenery -> patch_type.
    assert fetch.classify_member(["Infobox Scenery"]) == "patch_type"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/data/test_fetch_farming_patches.py -q`
Expected: FAIL — `data/fetch_farming_patches.py` does not exist / `classify_member` undefined.

- [ ] **Step 3: Write the fetch brick**

```python
# data/fetch_farming_patches.py
#!/usr/bin/env python3
"""Fetch the farming-patch source (CC BY-NC-SA 3.0) into committed raw snapshots.

Two snapshots, both deterministic (sorted keys, _provenance-stamped):
  wiki_farming_patch_category.json = Category:Farming patches members + each member's
      {{Infobox X}} classification (the completeness anchor + classifier).
  wiki_farming_patch_tables.json   = raw wikitext of the /Patches location tables
      (Task 3 parses these; committed so the parse is offline-reproducible).
The category is the SOURCE OF TRUTH (a curated index page is never a census). No inference here.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://oldschool.runescape.wiki/api.php"
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
RAW = Path(__file__).resolve().parent / "raw"

# The location-table pages to snapshot (the transcluded /Patches subpages + the inline coral table).
# Herb & Flower have NO own subpage — Allotment/Patches is the sole source for all three (spec D6).
TABLE_PAGES = [
    "Allotment patch/Patches",
    "Bush patch/Patches",
    "Hops patch/Patches",
    "Tree patch/Patches",
    "Fruit tree patch/Patches",
    "Spirit Tree (Farming)/Patches",   # Spirit tree/Patches redirects here
    "Special patches/Patches",
    "Coral nursery (patch)",           # inline coral table (no /Patches subpage)
]

_SCENERY = {"Infobox Scenery", "Infobox Construction"}


def classify_member(infoboxes):
    """Classify a Category:Farming patches member by the {{Infobox X}} on its page."""
    s = set(infoboxes or [])
    if "Infobox NPC" in s:
        return "npc"            # Chet
    if "Infobox Location" in s:
        return "place"          # Coral Nurseries (the underwater place, not a patch)
    if s & _SCENERY:
        return "patch_type"     # Allotment/Herb/.../Coral nursery (patch)
    return "other"


def _get(params):
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def _infoboxes_in(wikitext):
    """Sorted distinct {{Infobox X}} template names in a page's wikitext."""
    names = set(re.findall(r"\{\{\s*(Infobox [A-Za-z][A-Za-z ]*?)\s*[\|\}]", wikitext or ""))
    return sorted(names)


def _wikitext_of(titles):
    """title -> wikitext for a batch of titles (redirects resolved)."""
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        d = _get({"action": "query", "prop": "revisions", "rvslots": "main",
                  "rvprop": "content", "redirects": "1", "titles": "|".join(batch)})
        pages = d.get("query", {}).get("pages", {})
        norm = {n["from"]: n["to"] for n in d.get("query", {}).get("normalized", [])}
        redir = {r["from"]: r["to"] for r in d.get("query", {}).get("redirects", [])}
        resolved = {t: redir.get(norm.get(t, t), norm.get(t, t)) for t in batch}
        by_title = {p["title"]: p for p in pages.values() if "title" in p}
        for t in batch:
            p = by_title.get(resolved[t])
            wt = ""
            if p and p.get("revisions"):
                wt = p["revisions"][0]["slots"]["main"]["*"]
            out[t] = wt
        time.sleep(0.2)
    return out


def fetch_category_members():
    members = []
    cont = {}
    while True:
        d = _get({"action": "query", "list": "categorymembers",
                  "cmtitle": "Category:Farming patches", "cmlimit": "500",
                  "cmtype": "page", **cont})
        members += [m["title"] for m in d["query"]["categorymembers"]]
        if "continue" in d:
            cont = d["continue"]
        else:
            break
    return sorted(members)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    members = fetch_category_members()
    member_wt = _wikitext_of(members)
    cat = {}
    for name in members:
        ibs = _infoboxes_in(member_wt[name])
        cat[name] = {"infoboxes": ibs, "classification": classify_member(ibs),
                     "source_url": "https://oldschool.runescape.wiki/w/" +
                                   urllib.parse.quote(name.replace(" ", "_"))}
    _write(RAW / "wiki_farming_patch_category.json",
           {"_provenance": {"domain": "oldschool.runescape.wiki",
                            "source": "Category:Farming patches (action=query list=categorymembers)",
                            "license": "CC BY-NC-SA 3.0", "member_count": len(members)},
            "members": cat})

    table_wt = _wikitext_of(TABLE_PAGES)
    tables = {p: {"source_url": "https://oldschool.runescape.wiki/w/" +
                                urllib.parse.quote(p.replace(" ", "_")),
                  "wikitext": table_wt[p]} for p in TABLE_PAGES}
    _write(RAW / "wiki_farming_patch_tables.json",
           {"_provenance": {"domain": "oldschool.runescape.wiki",
                            "source": "farming /Patches subpages + inline coral table (action=query prop=revisions)",
                            "license": "CC BY-NC-SA 3.0", "pages": TABLE_PAGES},
            "tables": tables})
    print(f"wrote {len(members)} category members, {len(TABLE_PAGES)} tables")


def _write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the classifier test to verify it passes**

Run: `./venv/bin/python -m pytest tests/data/test_fetch_farming_patches.py -q`
Expected: PASS.

- [ ] **Step 5: Run the fetch to produce the committed snapshots, then eyeball them**

Run: `./venv/bin/python data/fetch_farming_patches.py`
Expected: `wrote 12 category members, 8 tables`. Then open `data/raw/wiki_farming_patch_category.json` and confirm the classification: 9 `patch_type`, 1 `other` (Special patches — it has a Scenery infobox so may read `patch_type`; that's fine, the coverage verifier treats "Special patches" as the umbrella by NAME), `Coral Nurseries` = `place`, `Chet` = `npc`. Open `data/raw/wiki_farming_patch_tables.json` and skim each table's `wikitext` — **this is the ground truth Task 3's parser + fixtures must match.**

- [ ] **Step 6: Commit**

```bash
git add data/fetch_farming_patches.py tests/data/test_fetch_farming_patches.py \
        data/raw/wiki_farming_patch_category.json data/raw/wiki_farming_patch_tables.json
git commit -m "feat(farming): fetch brick + committed category + table wikitext snapshots"
```

---

### Task 3: The wikitable parser (`farming_tables.py`)

The deterministic heart: turn raw table wikitext into typed patch rows. This is where the anti-fabrication rules live (per-row type emission; trailing-anchor place link; 0..n gardeners). Pure, offline, heavily tested on fixtures taken from the Task 2 snapshot.

> **⚠️ REVISED DURING EXECUTION (proven against the real committed snapshot — THIS GOVERNS; the parser code in Step 3 below is SUPERSEDED).**
> Task 2's fetch revealed the real wikitext is more complex than assumed (the `Allotment patch/Patches` table is a `{{!}}`-escaped parameterized template with `{{#if}}`/`{{#ifeq}}` guards; `Special patches/Patches` bundles 4 sub-tables; the coral page has 2 tables; only 3 of 12 category members carry an on-page infobox). A redesign was prototyped and **run against the real snapshot: 77 rows → 76 distinct (patch_type, place) nodes, id-injective, 0 unparsed, all 9 core types + 12 special crops, 72 parented / 4 FLAG.**
> **Do this instead of Step 3 below:** create `kg_ingest/builders/farming_tables.py` by copying the proven reference **verbatim** — `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/.superpowers/sdd/reference-farming_tables.py` (245 lines). Do NOT re-derive the parser. It preserves the public names the plan's tests use (`parse_patch_tables`, `split_cells`, `types_in_cell`, `trailing_place_link`, `gardeners_in`, `PAGE_DEFAULT_TYPE`) and adds `find_tables`, `section_of`, `header_columns`, `keep_table`, `normalize`, `special_type`.
> **Design (proven):** table-first — `find_tables` → `keep_table(cols)` keeps a table iff it has BOTH a `Location` and a `Map`/`Image` column (auto-skips the Activity sub-table [D4] + the coral-frags stats table); `normalize` expands `{{!}}-`→`\n|-` THEN `{{!}}`→`\n|` (order matters); per-row type from the Types cell links (the `{{#ifeq}}` guards need no evaluation — the Types cell already lists exactly the types present); `trailing_place_link` truncates the location cell at the first `<br`/`<ref`/`(requires`/`gardener` then takes the LAST `[[link]]`; `special_type` reads a special crop's Type-cell label; `gardeners_in` 0..n.
> **Step 1 tests:** the plan's original unit tests below still PASS verbatim with the proven code (they exercise the preserved public helpers) — keep them, and ADD unit tests for `keep_table` (Location+Map → True; Location-only → False), `normalize` (`{{!}}`→`|`), and `special_type` (`[[Grape seeds\|Grape]]`→`grape`, leading `Hardwood`→`hardwood`).
> **Step 5 census (the real proof) — assert against the committed snapshot:** `len(parse_patch_tables(tables)) == 77`; distinct `(patch_type, place_link)` count `== 76`; the `patch_type` set ⊇ the 9 core (`herb, allotment, flower, bush, hops, tree, fruit_tree, spirit_tree, coral`) AND the 12 special crops (`cactus, redwood, calquat, celastrus, crystal, hardwood, belladonna, hespori, anima, grape, mushroom, seaweed`); no blank/placeholder `patch_type`; every kept row has a `place_link`.
> **Owner decision (confirmed):** quest-gated patches are INCLUDED and disclosed — do NOT filter on "requires completion" (they are real, source-grounded rows; the parser correctly keeps them). Only the cleanly-separable Activity/minigame table is deferred (the keep-table gate skips it automatically).

**Files:**
- Create: `kg_ingest/builders/farming_tables.py`
- Test: `tests/kg_ingest/test_farming_tables.py`

**Interfaces:**
- Consumes: the `tables` dict from `wiki_farming_patch_tables.json` (Task 2).
- Produces: `parse_patch_tables(tables: dict) -> list[dict]` where each row = `{"patch_type": str, "place_link": str|None, "gardeners": list[str], "location_raw": str, "source_page": str, "source_url": str, "row_index": int}`. Consumed by the builder (Task 4).
- Produces: `PAGE_DEFAULT_TYPE: dict[str,str|None]` (page → its single patch_type, or None for multi-type pages) and helper functions `split_rows`, `split_cells`, `types_in_cell`, `trailing_place_link`, `gardeners_in`.

- [ ] **Step 1: Write failing tests for the cell/row splitters and the type/place/gardener extractors**

Create `tests/kg_ingest/test_farming_tables.py`:

```python
from kg_ingest.builders.farming_tables import (
    split_rows, split_cells, types_in_cell, trailing_place_link, gardeners_in,
    parse_patch_tables, PAGE_DEFAULT_TYPE,
)

def test_split_cells_respects_template_and_link_pipes():
    row = "| *[[Herb patch|Herb]] || North of [[Catherby]] || {{Map|2810,3464|r=6}}"
    cells = split_cells(row)
    assert cells[0].strip() == "*[[Herb patch|Herb]]"
    assert cells[1].strip() == "North of [[Catherby]]"
    assert cells[2].strip() == "{{Map|2810,3464|r=6}}"   # pipe inside {{ }} not split

def test_types_in_cell_reads_the_bullet_links():
    cell = "*[[Allotment patch|Allotment]]\n*[[Flower patch|Flower]]\n*[[Herb patch|Herb]]"
    assert types_in_cell(cell) == ["allotment", "flower", "herb"]

def test_types_in_cell_herb_only_row_yields_only_herb():
    # the anti-fabrication case: a herb-only site must NOT emit allotment/flower
    assert types_in_cell("*[[Herb patch|Herb]]") == ["herb"]

def test_types_in_cell_flower_only_row_yields_only_flower():
    assert types_in_cell("*[[Flower patch|Flower]]") == ["flower"]

def test_trailing_place_link_takes_the_last_link():
    assert trailing_place_link("[[Hemenster|North]] of [[Ardougne]]") == "Ardougne"
    assert trailing_place_link("South of [[Falador]]") == "Falador"
    assert trailing_place_link("Roof of the [[Troll Stronghold (location)|Troll Stronghold]]") == "Troll Stronghold (location)"
    assert trailing_place_link("no link here") is None

def test_gardeners_in_parses_zero_one_and_many():
    assert gardeners_in("South of [[Falador]]<br>''Gardener: [[Elstan]]''") == ["Elstan"]
    assert gardeners_in("[[Catherby]]<br>''Gardeners: [[A]] or [[B]]''") == ["A", "B"]
    assert gardeners_in("[[Weiss]]") == []

def test_page_default_type_map_covers_the_single_type_subpages():
    assert PAGE_DEFAULT_TYPE["Bush patch/Patches"] == "bush"
    assert PAGE_DEFAULT_TYPE["Fruit tree patch/Patches"] == "fruit_tree"
    assert PAGE_DEFAULT_TYPE["Spirit Tree (Farming)/Patches"] == "spirit_tree"
    assert PAGE_DEFAULT_TYPE["Allotment patch/Patches"] is None   # multi-type: read the cell
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_farming_tables.py -q`
Expected: FAIL — module `kg_ingest.builders.farming_tables` does not exist.

- [ ] **Step 3: Write the parser**

```python
# kg_ingest/builders/farming_tables.py
"""Deterministic parser for the OSRS farming-patch location tables (spec §7).

Turns the committed table wikitext (wiki_farming_patch_tables.json) into typed patch
rows. Anti-fabrication rules live here: type emission is PER-ROW from the actual
"Types" cell links (never a fixed 3-way expansion), the place is the TRAILING [[Place]]
link (not first-wins), gardeners are 0..n. NO coordinates are read (spec D5). Pure.
"""
from __future__ import annotations
import re

# Which single patch_type a page's rows are, or None for the multi-type / umbrella pages.
PAGE_DEFAULT_TYPE = {
    "Allotment patch/Patches": None,        # allotment/flower/herb — read the Types cell
    "Bush patch/Patches": "bush",
    "Hops patch/Patches": "hops",
    "Tree patch/Patches": "tree",
    "Fruit tree patch/Patches": "fruit_tree",
    "Spirit Tree (Farming)/Patches": "spirit_tree",
    "Special patches/Patches": None,        # umbrella — type from the row's Type/section
    "Coral nursery (patch)": "coral",
}

# Map a linked patch-type PAGE title -> the closed patch_type token.
_TYPE_PAGE = {
    "allotment patch": "allotment", "flower patch": "flower", "herb patch": "herb",
    "bush patch": "bush", "hops patch": "hops", "tree patch": "tree",
    "fruit tree patch": "fruit_tree", "spirit tree": "spirit_tree",
    "coral nursery (patch)": "coral", "coral nursery": "coral",
}


def split_rows(wikitext):
    """Table rows: the segments between `|-` markers, dropping the header/caption pre-amble."""
    body = wikitext or ""
    parts = re.split(r"\n\|\-+", body)
    return [p for p in parts[1:]] if len(parts) > 1 else []


def split_cells(row_text):
    """Split a row into cells on `|`/`||` at brace/bracket depth 0 (so pipes inside
    {{Map|..}} and [[A|B]] never split a cell). Leading cell markers stripped."""
    cells, buf, depth = [], [], 0
    i, s = 0, row_text
    while i < len(s):
        two = s[i:i + 2]
        if two in ("{{", "[["):
            depth += 1; buf.append(two); i += 2; continue
        if two in ("}}", "]]"):
            depth = max(0, depth - 1); buf.append(two); i += 2; continue
        if depth == 0 and (two == "||" or (s[i] == "|" and (i == 0 or s[i - 1] == "\n"))):
            cells.append("".join(buf)); buf = []
            i += 2 if two == "||" else 1; continue
        buf.append(s[i]); i += 1
    cells.append("".join(buf))
    # drop a possible empty pre-first-pipe fragment; strip inline attribute prefixes like `class="x"|`
    out = []
    for c in cells:
        c = re.sub(r'^\s*[a-zA-Z-]+="[^"]*"\s*\|', "", c)
        out.append(c)
    return [c for c in out if c.strip() != ""] or out


def _links(text):
    return re.findall(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", text or "")


def types_in_cell(cell):
    """The patch_types explicitly linked in a Types cell, de-duped in first-seen order.
    Empty if the cell links no patch-type page (caller falls back to the page default)."""
    out = []
    for target in _links(cell):
        t = _TYPE_PAGE.get(target.strip().lower())
        if t and t not in out:
            out.append(t)
    return out


def trailing_place_link(location_cell):
    """The LAST [[link]] target in the location portion (the 'of X' anchor). The gardener
    portion is stripped first. None if no link. Fixes the multi-link mis-home (spec §7)."""
    loc = re.split(r"gardener", location_cell or "", flags=re.IGNORECASE)[0]
    links = _links(loc)
    return links[-1].strip() if links else None


def gardeners_in(location_cell):
    """0..n gardener names from the 'Gardener(s): ...' tail; [] if none."""
    m = re.split(r"gardener[s]?\s*:", location_cell or "", flags=re.IGNORECASE)
    if len(m) < 2:
        return []
    return [g.strip() for g in _links(m[1])]


def parse_patch_tables(tables):
    """All patch rows across the committed tables. Rows without a resolvable patch_type
    are dropped (never a placeholder). Special-patches type comes from the row's Type cell
    links or, failing that, its section header slug; the raked-only Activity sub-table
    (spec D4) is skipped by header."""
    rows = []
    for page, rec in sorted(tables.items()):
        default = PAGE_DEFAULT_TYPE.get(page)
        wikitext = rec.get("wikitext", "")
        section = None
        for m in re.finditer(r"(={2,}\s*(?P<h>.+?)\s*={2,})|(?P<row>\n\|\-+[^\0]*?(?=\n\|\-|\n\|\}|\Z))",
                             wikitext):
            if m.group("h") is not None:
                section = m.group("h").strip()
                continue
            row_text = m.group("row")
            if _skip_section(page, section):
                continue
            cells = split_cells(row_text)
            if len(cells) < 2:
                continue
            # locate the Types cell (has patch links) and the Location cell (has a place link + maybe gardener)
            type_cell = next((c for c in cells if types_in_cell(c)), cells[0])
            loc_cell = next((c for c in cells if trailing_place_link(c)), None)
            if loc_cell is None:
                continue
            types = types_in_cell(type_cell) or ([default] if default else _section_type(section))
            for t in [x for x in types if x]:
                rows.append({
                    "patch_type": t,
                    "place_link": trailing_place_link(loc_cell),
                    "gardeners": gardeners_in(loc_cell),
                    "location_raw": loc_cell.strip(),
                    "source_page": page,
                    "source_url": rec.get("source_url", ""),
                    "row_index": len(rows),
                })
    return rows


def _skip_section(page, section):
    # Special patches has a raked-only "Activity"/minigame sub-table (Tithe/CoX/Miscellania) — deferred (spec D4).
    return page == "Special patches/Patches" and section is not None and \
        re.search(r"activit|minigame|raked", section, re.IGNORECASE) is not None


def _section_type(section):
    """Best-effort special-crop type from a section header (e.g. 'Cactus patches' -> ['cactus'])."""
    if not section:
        return []
    slug = re.sub(r"\bpatches?\b", "", section, flags=re.IGNORECASE).strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return [slug] if slug else []
```

> **Implementer note (honest scrape caveat):** the `parse_patch_tables` section/row regex and the special-patches section handling are written against the representative shapes seen during source discovery. After Task 2 commits the real snapshot, **run `parse_patch_tables` on it, print the distinct `(source_page, patch_type)` pairs, and confirm** every core type + coral + the special crops (cactus, redwood, calquat, celastrus, crystal, teak/hardwood, belladonna, hespori, anima, grape, mushroom, seaweed) appears and no fabricated/blank type does. Add a fixture test for any row shape the regex misses. The Task 6 coverage verifier + hard-fail verifier are the safety net, but fix surprises here.

- [ ] **Step 4: Run the parser tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_farming_tables.py -q`
Expected: PASS.

- [ ] **Step 5: Add + run an end-to-end parse test against the committed snapshot**

Append to `tests/kg_ingest/test_farming_tables.py`:

```python
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_parse_real_snapshot_covers_core_types_no_blanks():
    tables = json.loads((ROOT / "data" / "raw" / "wiki_farming_patch_tables.json").read_text())["tables"]
    rows = parse_patch_tables(tables)
    types = {r["patch_type"] for r in rows}
    for core in ("herb", "allotment", "flower", "bush", "hops", "tree", "fruit_tree", "spirit_tree", "coral"):
        assert core in types, f"{core} missing from parsed rows"
    assert "" not in types and all(r["patch_type"] for r in rows)   # never a blank/placeholder type
    assert all(r["place_link"] for r in rows)                        # every kept row has a place link
```

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_farming_tables.py -q`
Expected: PASS. If a core type is missing, fix the parser/fixtures per the implementer note before continuing.

- [ ] **Step 6: Commit**

```bash
git add kg_ingest/builders/farming_tables.py tests/kg_ingest/test_farming_tables.py
git commit -m "feat(farming): deterministic wikitable parser (per-row type, trailing-anchor place, 0..n gardeners)"
```

---

### Task 4: The builder (`farming.py`)

Resolve each parsed row's place link to a committed `place:` node, group by (patch_type, place) into one node per instance, and emit `located_in` edges. This is where the id-injectivity fail-fast and the in-builder collapse (no `dedup_nodes` crash) live.

> **⚠️ REVISION (governs over the Step 3 code below):** the coral node must RETAIN its gardener (`Chet`). Coral appears in two rows — the coral page (with `Gardener: [[Chet]]`) and the `Special patches` table (no gardener) — that collapse to one node. The plan's tie-break `(location_raw, source_url, row_index)` happens to pick the gardener-less Special row. **Fix:** make the group winner prefer a row WITH a non-empty gardener — change the winner key to `(0 if <this row's gardeners> else 1, location_raw, source_url, row_index)` so a gardener'd row wins. Add a builder test: two rows for `("coral", "Coral Nurseries")`, one `gardeners=["Chet"]` and one `gardeners=[]`, collapse to ONE node whose `data["gardener"] == "Chet"`. (The parser row's `place_link` for both coral rows is `Coral Nurseries` → resolves to the existing `place:coral-nurseries`; the two rows also confirm the multi-source-same-id collapse path.)

**Files:**
- Create: `kg_ingest/builders/farming.py`
- Test: `tests/kg_ingest/test_farming_builder.py`

**Interfaces:**
- Consumes: `parse_patch_tables(...)` output (Task 3); `place_nodes: list[Node]`; `overrides: dict` (`place_overrides`, `force_exclude`); the shop helpers `build_place_name_index`, `_norm` (imported from `kg_ingest.builders.shops` / `world`).
- Produces: `build_farming_patches(patch_rows, place_nodes, overrides) -> (nodes, edges, {})`; `resolve_place(place_link, name_index, place_overrides) -> str|None`; `_farming_slug(patch_type, place_component) -> str`.

- [ ] **Step 1: Write failing builder tests**

```python
# tests/kg_ingest/test_farming_builder.py
from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType
from kg_ingest.builders.farming import build_farming_patches, resolve_place

def _places(*names):
    return [Node(id=f"place:{n.lower().replace(' ', '-')}", kind=NodeKind.PLACE,
                 name=n, slug=n.lower().replace(" ", "-"), data={}) for n in names]

def _row(pt, link, page="Herb patch/Patches", gardeners=None, loc=None, idx=0):
    return {"patch_type": pt, "place_link": link, "gardeners": gardeners or [],
            "location_raw": loc or f"[[{link}]]", "source_page": page,
            "source_url": f"https://oldschool.runescape.wiki/w/{page.replace(' ', '_')}",
            "row_index": idx}

def test_emits_node_and_located_in_for_resolved_place():
    nodes, edges, groups = build_farming_patches(
        [_row("herb", "Catherby", gardeners=["Dantaera"])], _places("Catherby"), {})
    assert groups == {}
    n = next(x for x in nodes if x.id == "farming_patch:herb-catherby")
    assert n.kind == NodeKind.FARMING_PATCH and n.name == "Herb patch (Catherby)"
    assert n.data["patch_type"] == "herb" and n.data["gardener"] == "Dantaera"
    assert n.data["source_token"] == "[[Catherby]]"
    e = next(x for x in edges if x.src == n.id)
    assert e.type == EdgeType.LOCATED_IN and e.dst == "place:catherby"
    assert e.cond_group is None and e.data == {}

def test_underscore_patch_type_slugs_to_dash():
    nodes, _, _ = build_farming_patches([_row("fruit_tree", "Catherby")], _places("Catherby"), {})
    assert any(n.id == "farming_patch:fruit-tree-catherby" for n in nodes)

def test_unresolved_place_is_flag_no_edge():
    nodes, edges, _ = build_farming_patches([_row("herb", "Nowhereton")], _places("Catherby"), {})
    assert any(n.id == "farming_patch:herb-nowhereton" for n in nodes)
    assert edges == []   # FLAG: node kept, no located_in

def test_place_override_resolves_a_flag():
    ov = {"place_overrides": [{"location": "Ortus Farm", "place_id": "place:catherby"}]}
    nodes, edges, _ = build_farming_patches([_row("herb", "Ortus Farm")], _places("Catherby"), ov)
    assert any(e.dst == "place:catherby" for e in edges)

def test_multi_source_same_id_collapses_to_one_byte_identical_node():
    # coral appears in the inline table AND the Special-patches row -> same (type, place) -> ONE node
    rows = [_row("coral", "Coral Nurseries", page="Coral nursery (patch)", gardeners=["Chet"], idx=0),
            _row("coral", "Coral Nurseries", page="Special patches/Patches", gardeners=["Chet"], idx=1)]
    nodes, edges, _ = build_farming_patches(rows, _places("Coral Nurseries"), {})
    coral = [n for n in nodes if n.id == "farming_patch:coral-coral-nurseries"]
    assert len(coral) == 1                      # collapsed in the builder (no dedup_nodes crash)
    assert len([e for e in edges if e.src == "farming_patch:coral-coral-nurseries"]) == 1

def test_same_type_place_from_two_rows_collapses_not_raises():
    # two rows for the same (type, resolved place) — one via override — collapse to ONE node,
    # never a -k suffix. (The injectivity `raise` in the builder is a defensive guard: (type,
    # place_comp) -> id is injective by construction with real data, so it fires only on a
    # contrived type/place slug clash, which valid data cannot produce.)
    rows = [_row("herb", "Catherby", idx=0), _row("herb", "Catherby Alt", idx=1)]
    ov = {"place_overrides": [{"location": "Catherby Alt", "place_id": "place:catherby"}]}
    nodes, _, _ = build_farming_patches(rows, _places("Catherby"), ov)
    assert sum(1 for n in nodes if n.id == "farming_patch:herb-catherby") == 1
    assert not any(n.id.startswith("farming_patch:herb-catherby-") for n in nodes)  # no -k

def test_deterministic_order_independent():
    a = build_farming_patches([_row("herb", "Catherby", idx=0), _row("bush", "Catherby", idx=1)],
                              _places("Catherby"), {})[0]
    b = build_farming_patches([_row("bush", "Catherby", idx=0), _row("herb", "Catherby", idx=1)],
                              _places("Catherby"), {})[0]
    assert [n.id for n in a] == [n.id for n in b]

def test_resolve_place_uses_norm_index():
    from kg_ingest.builders.farming import _name_index
    idx = _name_index(_places("Port Phasmatys"))
    assert resolve_place("Port Phasmatys", idx, []) == "place:port-phasmatys"
    assert resolve_place("Nonexistent", idx, []) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_farming_builder.py -q`
Expected: FAIL — `kg_ingest.builders.farming` does not exist.

- [ ] **Step 3: Write the builder**

```python
# kg_ingest/builders/farming.py
"""build_farming_patches — the farming-patch roster (objects/resources slice 2).

One node per (patch_type x place). Each parsed row's TRAILING [[Place]] link is resolved
to a committed place: node (place_overrides > _norm name-index; else FLAG, no edge). Rows
sharing (patch_type, place) COLLAPSE in the builder to one byte-identical Node + one
located_in edge (dedup_nodes raises on same-id-different-content, so we must). id is
injective by a fail-fast; NO order-dependent -k fallback (spec D7). Never fabricates.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, slugify
from kg_ingest.builders.world import _norm

_EDGE_BAND = 0xE8000000        # farming-src family; cosmetic — assemble.rekey replaces it

# Display names for the closed patch_type vocab (spec D8). Special crops fall back to Title-case.
_TYPE_NAME = {
    "herb": "Herb", "allotment": "Allotment", "flower": "Flower", "bush": "Bush",
    "hops": "Hops", "tree": "Tree", "fruit_tree": "Fruit tree", "spirit_tree": "Spirit tree",
    "coral": "Coral",
}


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _name_index(place_nodes):
    """_norm(place name) -> place id over the committed place graph (shops.py pattern)."""
    idx: dict[str, str] = {}
    for n in sorted(place_nodes, key=lambda n: n.id):
        if n.id.startswith("place:"):
            idx.setdefault(_norm(n.name), n.id)
    return idx


def resolve_place(place_link, name_index, place_overrides):
    """place_override (by link text) > _norm name-index. None -> FLAG (caller emits no edge)."""
    if place_link is None:
        return None
    for o in place_overrides or []:
        if o["location"] == place_link:
            return o["place_id"]
    return name_index.get(_norm(place_link))


def _type_name(pt: str) -> str:
    return _TYPE_NAME.get(pt) or pt.replace("_", " ").capitalize()


def build_farming_patches(patch_rows, place_nodes, overrides):
    overrides = overrides or {}
    place_overrides = overrides.get("place_overrides", [])
    name_index = _name_index(place_nodes)

    # group rows by (patch_type, place_component). place_component = resolved place slug, else
    # slugify(place_link) for a FLAG. Each group -> ONE node (deterministic pick), one edge if resolved.
    groups: dict[tuple, dict] = {}
    for r in patch_rows:
        pt = r["patch_type"]
        pid = resolve_place(r.get("place_link"), name_index, place_overrides)
        place_comp = pid.split(":", 1)[1] if pid else slugify(r.get("place_link") or "unknown")
        key = (pt, place_comp)
        cand = {
            "patch_type": pt, "place_id": pid, "place_comp": place_comp,
            "gardener": " or ".join(r.get("gardeners") or []) or None,
            "source_url": r.get("source_url", ""),
            "source_token": r.get("location_raw", ""),
            "sort": (r.get("location_raw", ""), r.get("source_url", ""), r.get("row_index", 0)),
        }
        prev = groups.get(key)
        # deterministic winner: smallest (source_token, source_url, row_index) — order-independent
        if prev is None or cand["sort"] < prev["sort"]:
            if prev is not None:
                cand["place_id"] = cand["place_id"] or prev["place_id"]
            groups[key] = cand

    nodes: list[Node] = []
    edges: list[Edge] = []
    by_id: dict[str, tuple] = {}
    for (pt, place_comp), g in sorted(groups.items()):
        nid = _farming_slug(pt, place_comp)
        if nid in by_id and by_id[nid] != (pt, place_comp):
            raise ValueError(
                f"farming_patch id collision at {nid!r}: (patch_type,place) "
                f"{by_id[nid]} and {(pt, place_comp)} produce the same id (unrecoverable; "
                f"disambiguate via farming_overrides, never a -k fallback)")
        by_id[nid] = (pt, place_comp)
        data = {"patch_type": pt, "source_url": g["source_url"], "source_token": g["source_token"]}
        if g["gardener"]:
            data["gardener"] = g["gardener"]
        place_name = (g["place_id"] or "").split(":", 1)[-1].replace("-", " ").title() \
            if g["place_id"] else place_comp.replace("-", " ").title()
        nodes.append(Node(id=nid, kind=NodeKind.FARMING_PATCH,
                          name=f"{_type_name(pt)} patch ({place_name})",
                          slug=nid.split(":", 1)[1], data=data))
        if g["place_id"]:
            edges.append(Edge(id=_edge_id(nid, "located_in"), type=EdgeType.LOCATED_IN,
                              src=nid, dst=g["place_id"], cond_group=None, data={}))
        # place_id None -> unparented FLAG (no edge), reported by verify_farming_coverage
    return nodes, edges, {}


def _farming_slug(patch_type: str, place_component: str) -> str:
    return f"farming_patch:{slugify(patch_type)}-{place_component}"
```

- [ ] **Step 4: Run the builder tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_farming_builder.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/farming.py tests/kg_ingest/test_farming_builder.py
git commit -m "feat(farming): builder — (type x place) roster, in-builder collapse, injective id, located_in"
```

---

### Task 5: Assembly wiring + starter overrides

Wire the builder into `assemble.py` after `build_map` (so the place index spans `world+map` nodes), with a seeded `rekey`. Add the owner-authored `farming_overrides.json` seeded with the review's known place_overrides + exclusions. Assemble must stay byte-stable.

> **⚠️ REVISION (governs):** (1) The proven census is **76 nodes**, not ~90 — the Step 2 test `assert len(fp) >= 80` is WRONG; it is corrected to `>= 70` below. (2) Add **two more** `place_overrides` to `farming_overrides.json` (both target places verified to exist): `Vinery → place:hosidius` (the Grape/Vinery cell names `[[Hosidius]]` as its parent; the trailing anchor `Vinery` isn't a skeleton place) and `Mushroom Forest → place:fossil-island` (the hardwood cell names `[[Fossil Island]]`; `Mushroom Forest` isn't a skeleton place). Leave `Locus Oasis` and `McGrubor's Wood` as **disclosed FLAGs** (genuine skeleton gaps — the coverage verifier reports them; do NOT invent placements). Expected result: **74 parented / 2 FLAG.**

**Files:**
- Modify: `kg_ingest/assemble.py` (path constants ~305; loaders ~373; wiring block after the facility block ~588; `dedup_nodes` concat ~644)
- Create: `data/map/farming_overrides.json`
- Test: `tests/kg_ingest/test_farming_in_graph.py`

**Interfaces:**
- Consumes: `build_farming_patches` (Task 4); the committed table snapshot (Task 2); `world_nodes + map_nodes` place index (assemble.py:549 pattern).
- Produces: `farming_patch:` nodes + `located_in` edges in `kg/{nodes,edges}.json`.

- [ ] **Step 1: Write the starter overrides file**

```json
{
  "_provenance": {
    "description": "Owner-authored escape hatch for the farming-patch layer (spec §4c). place_overrides map an unresolved location link -> a committed place id; force_exclude documents category members that are not patches (coverage verifier).",
    "accessed": "2026-07-11"
  },
  "force_exclude": [
    {"value": "Chet", "reason": "NPC (coral gardener) swept into Category:Farming patches; kept only as a gardener field", "source_url": "https://oldschool.runescape.wiki/w/Chet"},
    {"value": "Coral Nurseries", "reason": "the underwater LOCATION page (Infobox Location), not a patch; the patch is 'Coral nursery (patch)'", "source_url": "https://oldschool.runescape.wiki/w/Coral_Nurseries"}
  ],
  "place_overrides": [
    {"location": "Varrock Castle", "place_id": "place:varrock", "reason": "flower patch; Castle is inside Varrock", "source_url": "https://oldschool.runescape.wiki/w/Varrock_Castle"},
    {"location": "Falador Park", "place_id": "place:falador", "reason": "tree patch; Park is inside Falador", "source_url": "https://oldschool.runescape.wiki/w/Falador_Park"},
    {"location": "Gnome Stronghold", "place_id": "place:gnome-stronghold", "reason": "redirect target the _norm resolver does not follow", "source_url": "https://oldschool.runescape.wiki/w/Tree_Gnome_Stronghold"},
    {"location": "Tree Gnome maze", "place_id": "place:tree-gnome-village", "reason": "fruit tree patch in the maze", "source_url": "https://oldschool.runescape.wiki/w/Tree_Gnome_Village"},
    {"location": "Underwater", "place_id": "place:fossil-island", "reason": "Fossil Island underwater area", "source_url": "https://oldschool.runescape.wiki/w/Fossil_Island"},
    {"location": "Draynor Manor", "place_id": "place:draynor-village", "reason": "belladonna patch by Draynor Manor", "source_url": "https://oldschool.runescape.wiki/w/Draynor_Manor"},
    {"location": "Ortus Farm", "place_id": "place:civitas-illa-fortis", "reason": "Varlamore allotment/flower/herb hub", "source_url": "https://oldschool.runescape.wiki/w/Ortus_Farm"}
  ]
}
```

> **Implementer note:** after Step 5's assemble + Task 6's coverage report, revisit this file — add a `place_override` for any remaining trivially-resolvable FLAG, or leave it FLAGged (disclosed) if the skeleton genuinely lacks the place. Every `place_id` here MUST exist in `kg/nodes.json` (the verifier checks located_in dsts).

- [ ] **Step 2: Write the failing in-graph test**

```python
# tests/kg_ingest/test_farming_in_graph.py
import json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]

def _nodes():
    return json.loads((ROOT / "kg" / "nodes.json").read_text())

def _edges():
    return json.loads((ROOT / "kg" / "edges.json").read_text())

def test_farming_nodes_present_and_well_formed():
    fp = [n for n in _nodes() if n["id"].startswith("farming_patch:")]
    assert len(fp) >= 70, f"expected ~76 farming patches, got {len(fp)}"
    herb = next((n for n in fp if n["id"] == "farming_patch:herb-catherby"), None)
    assert herb is not None and herb["kind"] == "farming_patch"
    assert herb["data"]["patch_type"] == "herb"
    assert herb["data"]["source_token"] and herb["data"]["source_url"]

def test_farming_located_in_edge_targets_a_real_place():
    place_ids = {n["id"] for n in _nodes() if n["id"].startswith("place:")}
    fp_ids = {n["id"] for n in _nodes() if n["id"].startswith("farming_patch:")}
    li = [e for e in _edges() if e["type"] == "located_in" and e["src"].startswith("farming_patch:")]
    assert any(e["src"] == "farming_patch:herb-catherby" and e["dst"] == "place:catherby" for e in li)
    for e in li:
        assert e["src"] in fp_ids and e["dst"] in place_ids   # no dangling edges
        assert e["cond_group"] is None and e["data"] == {}

def test_assemble_is_byte_stable():
    p = ROOT / "kg" / "nodes.json"
    before = p.read_bytes()
    subprocess.run([sys.executable, "-m", "kg_ingest.assemble"], cwd=ROOT, check=True)
    assert p.read_bytes() == before, "assemble is not byte-stable"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_farming_in_graph.py -q`
Expected: FAIL — no `farming_patch:` nodes in the committed graph yet.

- [ ] **Step 4: Wire the builder into `assemble.py`**

Add the import near the other builder imports (after line 43):

```python
from kg_ingest.builders.farming import build_farming_patches
```

Add path constants after `FACILITY_OVERRIDES_PATH` (line 303):

```python
FARMING_TABLES_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "wiki_farming_patch_tables.json"
FARMING_OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "data" / "map" / "farming_overrides.json"
```

Add loaders after `_load_facility_overrides` (line 372):

```python
def _load_farming_tables() -> dict | None:
    if not FARMING_TABLES_PATH.exists():
        return None
    return json.loads(FARMING_TABLES_PATH.read_text())["tables"]


def _load_farming_overrides() -> dict:
    if not FARMING_OVERRIDES_PATH.exists():
        return {"force_exclude": [], "place_overrides": []}
    d = json.loads(FARMING_OVERRIDES_PATH.read_text())
    return {"force_exclude": d.get("force_exclude", []), "place_overrides": d.get("place_overrides", [])}
```

Add the wiring block immediately after the facility block (after line 588, before the recipe roster block):

```python
    # Farming-patch layer (objects/resources slice 2): (patch_type x place) instances located_in
    # the skeleton. Place index spans world+map (build_map-owned places too). farming-src located_in
    # -> its OWN seeded rekey (fresh owner namespace, but seeded for uniformity). Never fabricates.
    fp_nodes: list[Node] = []
    _fp_tables = _load_farming_tables()
    if _fp_tables is not None:
        from kg_ingest.builders.farming_tables import parse_patch_tables
        _fp_place_nodes = [n for n in (world_nodes + map_nodes) if n.kind == NodeKind.PLACE]
        fp_nodes, fp_edges, _ = build_farming_patches(
            parse_patch_tables(_fp_tables), _fp_place_nodes, _load_farming_overrides())
        _seed_fp: dict[str, int] = {}
        for _e in edges:
            _seed_fp[_e.src] = _seed_fp.get(_e.src, 0) + 1
        fp_nodes, fp_edges, _ = rekey(fp_nodes, fp_edges, {}, edge_index_seed=_seed_fp)
        edges = edges + fp_edges
        owned_ids = owned_ids | {n.id for n in fp_nodes}
```

Add `fp_nodes` to the `dedup_nodes` concat (line 644), after `fac_nodes`:

```python
    nodes = dedup_nodes(
        q_nodes + g_nodes + cg_nodes + d_nodes + dg_nodes + content_nodes + r_nodes + i_nodes + eqb_nodes + world_nodes + map_nodes + sh_nodes + npc_nodes + fac_nodes + fp_nodes + rr_nodes + s_nodes
    )
```

- [ ] **Step 5: Assemble, validate, and run the in-graph test**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python data/validate_kg.py && ./venv/bin/python -m pytest tests/kg_ingest/test_farming_in_graph.py -q`
Expected: assemble writes the graph; `validate_kg` prints no new VIOLATION (the `located_in` domain now admits `farming_patch`, the kind is live); the in-graph test PASSES. Then re-run assemble once more and confirm `git diff --stat kg/` is stable across the second run.

- [ ] **Step 6: Commit**

```bash
git add kg_ingest/assemble.py data/map/farming_overrides.json tests/kg_ingest/test_farming_in_graph.py kg/nodes.json kg/edges.json
git commit -m "feat(farming): assemble wiring (after build_map, seeded rekey) + starter overrides; ~90 patches in graph"
```

---

### Task 6: Verifiers (structural hard-fail + coverage report)

The source-grounding gates: one hard-fails if any node's datum doesn't trace to a real table row; one reports coverage against the 12-member category (every type yielded ≥1 node) and itemizes the FLAG residual + the disclosed deferrals.

> **⚠️ REVISION (governs over the coverage-verifier code below):** only **3** of the 12 category members carry an on-page infobox, so `classify_member` returns `patch_type` for just 3 (Coral nursery (patch)/Flower patch/Spirit tree) and `other` for the 6 infobox-less patch pages + Special patches. The coverage verifier therefore must **NOT** enumerate the roster types via `classification == "patch_type"`. Replace that logic with a committed name→role map:
> ```python
> # The 12 Category:Farming patches members -> roster role (NOT infobox-derived; only 3 carry
> # an on-page infobox). This is the completeness anchor.
> MEMBER_TYPE = {
>     "Allotment patch": "allotment", "Flower patch": "flower", "Herb patch": "herb",
>     "Bush patch": "bush", "Hops patch": "hops", "Tree patch": "tree",
>     "Fruit tree patch": "fruit_tree", "Spirit tree": "spirit_tree", "Coral nursery (patch)": "coral",
> }
> MEMBER_UMBRELLA = {"Special patches"}            # yields the special crops
> MEMBER_EXCLUDE  = {"Coral Nurseries", "Chet"}    # place / npc -> force_exclude, no node
> ```
> Cross-check: (a) every `MEMBER_TYPE` value appears in ≥1 node's `patch_type` — keep the `core types present: 9/9` assertion (it's correct); (b) the umbrella yielded ≥1 special-crop node; (c) the 2 excludes are in `farming_overrides.json` `force_exclude` and produced no node. Report the member line as `12 members = 9 patch-type + 1 umbrella + 1 place + 1 npc` (a fixed string, NOT computed from `classification`). `classify_member` stays as-is for Task 2's own shape test; the coverage verifier just must not depend on it for the roster. Also report the FLAG list (expect 2: Locus Oasis, McGrubor's Wood) and the disclosed deferrals (Activity/minigame table; coords; per-site patch_count; quest-gating-as-a-field; instance_of/patch_type nodes).

**Files:**
- Create: `data/verify_farming_patches.py`
- Create: `data/verify_farming_coverage.py`
- Test: append to `tests/kg_ingest/test_farming_in_graph.py`

**Interfaces:**
- Consumes: `kg/nodes.json`, `kg/edges.json`, both raw snapshots, `farming_overrides.json`, `parse_patch_tables` (Task 3), `classify_member` (Task 2).

- [ ] **Step 1: Write the structural hard-fail verifier**

```python
# data/verify_farming_patches.py
#!/usr/bin/env python3
"""Structural source-grounding gate for the farming-patch layer (hard-fail, exit 1 on violation).

Every farming_patch node must: (1) have a patch_type in the closed vocab; (2) trace its
source_token to a real parsed table row; (3) if located_in, target a real committed place.
Never fabricated. Reuses the committed snapshot + the deterministic parser.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.farming_tables import parse_patch_tables  # noqa: E402

CORE = {"herb", "allotment", "flower", "bush", "hops", "tree", "fruit_tree", "spirit_tree", "coral"}


def main() -> int:
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    tables = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_farming_patch_tables.json"),
                            encoding="utf-8"))["tables"]
    rows = parse_patch_tables(tables)
    row_types = {r["patch_type"] for r in rows}
    row_tokens = {r["location_raw"].strip() for r in rows}
    place_ids = {n["id"] for n in nodes if n["id"].startswith("place:")}
    fp = [n for n in nodes if n["id"].startswith("farming_patch:")]

    violations = []
    for n in fp:
        pt = n["data"].get("patch_type", "")
        if pt not in row_types and pt not in CORE:
            violations.append(f"[type] {n['id']}: patch_type {pt!r} not a parsed table type")
        if n["data"].get("source_token", "").strip() not in row_tokens:
            violations.append(f"[grounding] {n['id']}: source_token not traceable to a table row")
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    for e in edges:
        if e["type"] == "located_in" and e["src"].startswith("farming_patch:"):
            if e["dst"] not in place_ids:
                violations.append(f"[place] {e['src']}: located_in {e['dst']} is not a committed place")

    if violations:
        print(f"FARMING VERIFICATION FAILED — {len(violations)} violation(s):")
        for v in violations[:60]:
            print("  " + v)
        return 1
    print(f"FARMING VERIFICATION PASSED — {len(fp)} farming_patch nodes source-grounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write the coverage report verifier**

```python
# data/verify_farming_coverage.py
#!/usr/bin/env python3
"""Coverage gate for the farming-patch layer. REPORTS (never fails, exit 0): of the 12
Category:Farming patches members, which patch-type members yielded >=1 node; the
parented/FLAG split; and the DISCLOSED deferrals (activity + quest tail, coords,
patch_count collapse) so no gap is hidden.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.farming_tables import parse_patch_tables  # noqa: E402


def main() -> int:
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    cat = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_farming_patch_category.json"),
                         encoding="utf-8"))["members"]
    tables = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_farming_patch_tables.json"),
                            encoding="utf-8"))["tables"]
    rows = parse_patch_tables(tables)

    fp = [n for n in nodes if n["id"].startswith("farming_patch:")]
    located = {e["src"] for e in edges if e["type"] == "located_in" and e["src"].startswith("farming_patch:")}
    parented = [n for n in fp if n["id"] in located]
    flagged = [n for n in fp if n["id"] not in located]
    node_types = {n["data"]["patch_type"] for n in fp}

    print("FARMING COVERAGE (report-not-fail):")
    print(f"  category members: {len(cat)} "
          f"({sum(1 for m in cat.values() if m['classification'] == 'patch_type')} patch-type, "
          f"1 umbrella, 1 place, 1 npc)")
    print(f"  parsed rows: {len(rows)}  ->  farming_patch nodes: {len(fp)}")
    print(f"  parented (located_in): {len(parented)}   FLAG (unresolved place): {len(flagged)}")
    for n in sorted(flagged, key=lambda n: n["id"]):
        print(f"     - {n['id']}  (token: {n['data'].get('source_token','')!r})")
    # per-type presence cross-check (the completeness probe)
    core = ["herb", "allotment", "flower", "bush", "hops", "tree", "fruit_tree", "spirit_tree", "coral"]
    missing = [t for t in core if t not in node_types]
    print(f"  core types present: {len(core) - len(missing)}/{len(core)}"
          + (f"  MISSING: {missing}" if missing else ""))
    print("  DEFERRED (disclosed): activity+quest tail (Tithe/CoX/Miscellania + 5 quest patches); "
          "coordinates (chunk-geometry layer); per-site patch_count (Grape 12->1, etc.); "
          "instance_of + patch_type nodes (P8).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Write the verifier-passes test**

Append to `tests/kg_ingest/test_farming_in_graph.py`:

```python
def test_verify_farming_patches_passes():
    r = subprocess.run([sys.executable, "data/verify_farming_patches.py"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

def test_verify_farming_coverage_runs_clean():
    r = subprocess.run([sys.executable, "data/verify_farming_coverage.py"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "core types present: 9/9" in r.stdout, r.stdout
```

- [ ] **Step 4: Run the verifiers + tests**

Run: `./venv/bin/python data/verify_farming_patches.py && ./venv/bin/python data/verify_farming_coverage.py && ./venv/bin/python -m pytest tests/kg_ingest/test_farming_in_graph.py -q`
Expected: hard-fail verifier prints `PASSED`; coverage prints the report with `core types present: 9/9`; tests PASS. If a core type is missing or a node isn't grounded, fix the parser (Task 3) / overrides (Task 5) — do NOT weaken the verifier.

- [ ] **Step 5: Commit**

```bash
git add data/verify_farming_patches.py data/verify_farming_coverage.py tests/kg_ingest/test_farming_in_graph.py
git commit -m "feat(farming): structural hard-fail verifier + coverage report (category cross-check + FLAG residual)"
```

---

### Task 7: Full-suite green + docs + memory

Confirm the whole layer is green in the full suite (the package-shadow gotcha), record the final counts, and update the project's living docs.

**Files:**
- Modify: `CLAUDE.md` (status line + counts)
- Modify: `docs/superpowers/plans/2026-07-11-farming-patches-layer.md` (check off completed tasks — optional)

- [ ] **Step 1: Run the FULL test suite**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all farming tests green; only the 4 pre-existing `tests/drop_rates/` collection errors remain. If a farming test passed in isolation but ERRORs here, it's the `tests/data` package-shadow — switch that test to `importlib.util.spec_from_file_location` loading.

- [ ] **Step 2: Capture the final graph counts**

Run: `./venv/bin/python -c "import json; n=json.load(open('kg/nodes.json')); e=json.load(open('kg/edges.json')); fp=[x for x in n if x['id'].startswith('farming_patch:')]; li=[x for x in e if x['type']=='located_in' and x['src'].startswith('farming_patch:')]; print('nodes',len(n),'edges',len(e),'farming_patch',len(fp),'located_in',len(li))"`
Expected: prints the totals — record them for the commit message + CLAUDE.md.

- [ ] **Step 3: Update `CLAUDE.md`**

Update the `⭐ Current direction` line and the `Status:` line to record the farming-patch layer as merged (objects/resources slice 2), with the new node/edge totals and the disclosed residuals (FLAG count, deferred activity/quest tail, coords, patch_count, instance_of/patch_type-node P8 gap). Move "farming patches" from the NOW/NEXT list to done; keep gather sites (blocked) · transport · placed facilities as the remaining objects/resources work.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/plans/2026-07-11-farming-patches-layer.md
git commit -m "docs(farming): CLAUDE.md status + counts — objects/resources slice 2 (farming patches) done"
```

- [ ] **Step 5: Final verification before opening a PR**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python data/validate_kg.py && ./venv/bin/python data/verify_farming_patches.py && ./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: byte-stable assemble, validate_kg green, farming verifier PASSED, full suite green (minus the 4 pre-existing drop_rates errors). The branch is ready for a whole-branch review + PR.

---

## Notes for the implementer

- **The scrape is the risk.** Tasks 3–6 are gated by the committed snapshot from Task 2. Always run the fetch first, then validate the parser against the *real* wikitext (Task 3 Step 5) before trusting the downstream tasks. The hard-fail verifier + coverage cross-check catch grounding/completeness regressions, but fix root causes in the parser/overrides, never by weakening a gate.
- **Never fabricate.** A row you can't parse or a place you can't resolve is a FLAG the coverage verifier discloses — not a guessed node or edge.
- **Byte-stability is non-negotiable.** Re-run `assemble` twice and diff `kg/` after every graph-touching task.
- **Whole-branch review.** After Task 7, request an opus whole-branch review (the facility/recipe-layer pattern) before merging; adversarially verify the parser's type-emission against the live tables one more time.
