# Repair Edges (`repairs`) — Slice 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model item repair as a new `repairs` edge (item→item, broken→repaired), the structural inverse of slice-3's `degrades_to` broken terminal, for Dharok's helm and the Barrelchest anchor.

**Architecture:** Add `EdgeType.REPAIRS` (additive) + a new `repairs` schema entry; a new pure builder `kg_ingest/builders/repairs.py` reads a curated `data/repair_paths.json` and emits one `broken→repaired` edge per record; `assemble.py` runs it before `build_items` (so Barrelchest's variants auto-import) and — because `repairs` is item-`src` — folds its edges into the existing SHARED `rekey` with `build_items`' `same_entity` and slice-3's `degrades_to`. Design spec: `docs/superpowers/specs/2026-06-25-repair-edges-design.md`.

**Tech Stack:** Python 3.14 (`./venv/bin/python`), committed JSON, `pytest`. No new dependencies.

## Global Constraints

- Run everything via `./venv/bin/python` (Python 3.14). (If a focused `pytest` run hangs unusually long, retry once — transient machine load, not necessarily a code hang.)
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run produces identical bytes.
- **Gates stay green:** `./venv/bin/python data/validate_kg.py` exit 0; `./venv/bin/python data/validate_cost.py` exit 0; golden (`tests/kg_ingest/test_golden_set.py`) + slice-1/2/3 tests (`test_items_in_graph.py`, `test_recipes_in_graph.py`, `test_degrade_paths_in_graph.py`, `test_competency_questions.py`) pass; full `pytest` green except the 4 pre-existing `tests/drop_rates/` collection errors (`No module named 'data._toa_drop_rates'`).
- **Additive ontology extension:** `repairs` is NEW. Add the enum member AND a new `kg/schema.json` `edge_kinds.repairs` entry. The `model-enum ⊆ schema` invariant must stay green.
- **Pure transition edge:** `repairs` carries NO `data` (`reified: false`, like `supersedes`). The repair fee and NPC/facility are deferred (cost layer / `service` edge).
- **Never fabricate.** `data/repair_paths.json` is editorial: every record carries `source_url` + a verbatim `source_token`; owner-reviewed.
- **Edge ids:** `repairs` is item-`src`. Builder-local edge ids in a disjoint band (`0xC0000000`). `repairs` edges are re-keyed TOGETHER with `build_items`' `same_entity` AND slice-3's `degrades_to` edges in ONE `rekey(i_nodes, i_edges + dg_edges + rp_edges, {})` call.
- **Repair data (wiki-sourced, owner-verifies):** Dharok's helm = broken item 4884 (Dharok's helm 0) → repaired item 4716 (Dharok's helm, Undamaged). Barrelchest anchor = broken item 10888 → repaired item 10887 (Fixed).

---

### Task 1: Add `EdgeType.REPAIRS` + new schema edge entry

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py` (`EdgeType`)
- Modify: `kg/schema.json` (new `edge_kinds.repairs`)
- Test: `tests/engine/test_kg_model.py`

**Interfaces:**
- Produces: `EdgeType.REPAIRS` (`"repairs"`) — consumed by Task 2's builder and Task 4's assemble.

- [ ] **Step 1: Write the failing test**

Add to `tests/engine/test_kg_model.py`:
```python
def test_repairs_edge_exists_and_declared_live():
    from osrs_planner.engine.kg.model import EdgeType
    assert EdgeType.REPAIRS.value == "repairs"
    import json, pathlib
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    d = schema["edge_kinds"]["repairs"]
    assert d["status"] == "live" and d["domain"] == ["item"] and d["range"] == ["item"]
    assert d["dst"] == "required" and d["cond_group"] == "forbidden" and d["reified"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py::test_repairs_edge_exists_and_declared_live -v`
Expected: FAIL — `AttributeError: REPAIRS` / `KeyError: 'repairs'`.

- [ ] **Step 3: Add the enum member**

In `src/osrs_planner/engine/kg/model.py`, in `class EdgeType`, after `DEGRADES_TO = "degrades_to"` add:
```python
    REPAIRS = "repairs"                # restore-from-broken (inverse of degrades_to's broken terminal); item->item
```

- [ ] **Step 4: Add the schema edge entry**

In `kg/schema.json`, in the `"edge_kinds"` object, add a new entry right after the `"degrades_to"` entry:
```json
    "repairs": {"status": "live", "domain": ["item"], "range": ["item"], "dst": "required", "cond_group": "forbidden", "reified": false, "notes": "Restore-from-broken (additive extension; inverse of degrades_to's broken terminal). broken-variant -> repaired-variant. Pure structural transition; the repair fee is account-aware (cost layer) and the NPC/facility is the reserved service edge."},
```

- [ ] **Step 5: Run tests to verify they pass (incl. the model-enum⊆schema invariant)**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py tests/kg_ingest/test_validate_kg_schema.py::test_model_enums_are_all_declared_in_schema -v`
Expected: PASS (repairs now declared in both the enum and the schema).

- [ ] **Step 6: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py kg/schema.json tests/engine/test_kg_model.py
git commit -m "feat(kg): add EdgeType.REPAIRS + schema entry (additive extension)"
```

---

### Task 2: `build_repairs` builder

**Files:**
- Create: `kg_ingest/builders/repairs.py`
- Test: `tests/kg_ingest/test_repairs_builder.py`

**Interfaces:**
- Produces: `build_repairs(records: list[dict]) -> tuple[list[Node], list[Edge], dict]` — each record `{slug, page, broken:item_id, repaired:item_id, ...}` → one `repairs` edge `item:<broken> → item:<repaired>` with `data={}`. Returns `(nodes=[], edges, {})` — emits NO nodes.
- Consumes: `EdgeType.REPAIRS` (Task 1); `kg_ingest.ids.item_id`/`_stable_hash`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kg_ingest/test_repairs_builder.py`:
```python
from kg_ingest.builders.repairs import build_repairs
from osrs_planner.engine.kg.model import EdgeType

REC = [
    {"slug": "repair-dharoks-helm", "page": "Dharok's helm", "broken": 4884, "repaired": 4716},
    {"slug": "repair-barrelchest-anchor", "page": "Barrelchest anchor", "broken": 10888, "repaired": 10887},
]

def test_one_repairs_edge_per_record_item_src_empty_data():
    nodes, edges, groups = build_repairs(REC)
    assert nodes == [] and groups == {}
    pairs = [(e.src, e.dst) for e in edges if e.type is EdgeType.REPAIRS]
    assert ("item:4884", "item:4716") in pairs        # Dharok's helm broken -> undamaged
    assert ("item:10888", "item:10887") in pairs      # Barrelchest broken -> fixed
    assert all(e.data == {} and e.cond_group is None for e in edges)   # pure transition
    assert all(e.src.startswith("item:") for e in edges)               # item-src

def test_repairs_edges_are_deterministic():
    e1 = build_repairs(REC)[1]
    e2 = build_repairs(REC)[1]
    assert [(e.id, e.src, e.dst) for e in e1] == [(e.id, e.src, e.dst) for e in e2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_repairs_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: kg_ingest.builders.repairs`.

- [ ] **Step 3: Write the builder**

Create `kg_ingest/builders/repairs.py`:
```python
"""build_repairs — emit repairs edges (broken -> repaired); slice 4.

The structural inverse of degrades_to's broken terminal. One repairs edge per
record, pure transition (no data). Emits NO nodes — endpoints are slice-3 nodes
or auto-imported by build_items. repairs is ITEM-src; assemble re-keys these
TOGETHER with build_items' same_entity AND degrades_to edges (shared per-owner index).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType
from kg_ingest.ids import _stable_hash, item_id

_EDGE_BAND = 0xC0000000  # repairs builder-local edge ids (rekeyed in assemble)


def _edge_id(src_id: str) -> int:
    # one outgoing repairs edge per broken item, so a single per-src slot suffices
    return _EDGE_BAND | _stable_hash(f"{src_id}#repairs")


def build_repairs(records):
    nodes = []
    edges = []
    for rec in records:
        src = item_id(rec["broken"])
        edges.append(Edge(id=_edge_id(src), type=EdgeType.REPAIRS, src=src,
                          dst=item_id(rec["repaired"]), cond_group=None, data={}))
    return nodes, edges, {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_repairs_builder.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/repairs.py tests/kg_ingest/test_repairs_builder.py
git commit -m "feat(kg): build_repairs — broken->repaired transition edges"
```

---

### Task 3: Curated `repair_paths.json` + `verify_repair_paths.py`

**Files:**
- Create: `data/repair_paths.json`
- Create: `data/verify_repair_paths.py`
- Test: `tests/kg_ingest/test_verify_repair_paths.py`

**Interfaces:**
- Produces: the committed repair data (consumed by Task 4) + a CLI verifier returning exit 0/1.

- [ ] **Step 1: Create `data/repair_paths.json`** (wiki-sourced; owner verifies)

```json
{
  "_provenance": {
    "note": "curated item repair transitions (broken->repaired); editorial — owner-reviewed",
    "license": "CC BY-NC-SA 3.0",
    "accessed": "2026-06-25"
  },
  "records": [
    { "slug": "repair-dharoks-helm", "page": "Dharok's helm", "broken": 4884, "repaired": 4716,
      "source_url": "https://oldschool.runescape.wiki/w/Dharok's_helm",
      "source_token": "Players can talk to any of the NPCs listed below and they will repair the items for a price" },
    { "slug": "repair-barrelchest-anchor", "page": "Barrelchest anchor", "broken": 10888, "repaired": 10887,
      "source_url": "https://oldschool.runescape.wiki/w/Barrelchest_anchor",
      "source_token": "Players receive this item in a broken state and must pay Smith on the docks of Mos Le'Harmless a fee of 230,000 coins to repair the anchor." }
  ]
}
```

- [ ] **Step 2: Write the failing verifier test**

Create `tests/kg_ingest/test_verify_repair_paths.py`:
```python
import os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _run():
    return subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_repair_paths.py")],
                          capture_output=True, text=True)

def test_verifier_passes_on_committed_repair_paths():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "REPAIR-PATHS VERIFICATION PASSED" in r.stdout
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_repair_paths.py -v`
Expected: FAIL — `verify_repair_paths.py` does not exist.

- [ ] **Step 4: Write the verifier**

Create `data/verify_repair_paths.py`:
```python
#!/usr/bin/env python3
"""Source-grounding gate for data/repair_paths.json (editorial repair layer).

Checks: every `broken` + `repaired` id resolves in item_dictionary.json and shares
the record's `page` (page_name); broken != repaired; slug unique; source_url +
non-empty source_token. Exits non-zero on any violation. Mirrors
data/verify_degrade_paths.py.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
PATHS = os.path.join(ROOT, "data", "repair_paths.json")


def main() -> int:
    errors: list[str] = []
    with open(DICT, encoding="utf-8") as f:
        id_to_page = {r["item_id"]: r["page_name"] for r in json.load(f)["records"]}
    with open(PATHS, encoding="utf-8") as f:
        doc = json.load(f)
    seen: set[str] = set()
    for rec in doc["records"]:
        slug = rec.get("slug", "")
        if not slug or slug in seen:
            errors.append(f"[slug] missing/duplicate slug {slug!r}")
        seen.add(slug)
        if not rec.get("source_url"):
            errors.append(f"[source] {slug!r} missing source_url")
        if not rec.get("source_token"):
            errors.append(f"[source] {slug!r} missing source_token")
        page = rec.get("page")
        broken, repaired = rec.get("broken"), rec.get("repaired")
        if broken == repaired:
            errors.append(f"[same] {slug!r} broken == repaired ({broken})")
        for label, iid in (("broken", broken), ("repaired", repaired)):
            if iid not in id_to_page:
                errors.append(f"[item] {slug!r} {label} id {iid!r} not in item_dictionary")
            elif id_to_page[iid] != page:
                errors.append(f"[page] {slug!r} {label} id {iid!r} page {id_to_page[iid]!r} != {page!r}")
    if errors:
        print(f"REPAIR-PATHS VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("REPAIR-PATHS VERIFICATION PASSED — all repair paths source-grounded.")
    print(f"  paths: {len(doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test + verifier to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_repair_paths.py -v && ./venv/bin/python data/verify_repair_paths.py`
Expected: PASS; verifier prints `REPAIR-PATHS VERIFICATION PASSED`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add data/repair_paths.json data/verify_repair_paths.py tests/kg_ingest/test_verify_repair_paths.py
git commit -m "data(kg): curated repair paths (dharoks helm, barrelchest anchor) + verifier"
```

---

### Task 4: Wire into `assemble.py` (extend the shared rekey) + regenerate

**Files:**
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_repairs_in_graph.py`

**Interfaces:**
- Consumes: `build_repairs` (Task 2), `data/repair_paths.json` (Task 3), the slice-3 shared-rekey wiring (existing).

- [ ] **Step 1: Write the failing integration test**

Create `tests/kg_ingest/test_repairs_in_graph.py`:
```python
import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_repairs_edges_and_barrelchest_autoimport():
    s = JsonKGStore.from_dir(KG)
    # Dharok's helm broken -> undamaged (endpoints from slice 3)
    dh = [e for e in s.edges if e.type is EdgeType.REPAIRS and e.src == "item:4884"]
    assert len(dh) == 1 and dh[0].dst == "item:4716" and dh[0].data == {}
    # Barrelchest anchor: both variants auto-imported + the repairs edge
    assert s.node("item:10887") is not None and s.node("item:10888") is not None
    bc = [e for e in s.edges if e.type is EdgeType.REPAIRS and e.src == "item:10888"]
    assert len(bc) == 1 and bc[0].dst == "item:10887"

def test_all_edge_ids_unique_with_three_item_src_edge_types():
    # same_entity + degrades_to + repairs are all item-src and share one rekey call;
    # the committed graph must have zero duplicate edge ids.
    s = JsonKGStore.from_dir(KG)
    ids = [e.id for e in s.edges]
    assert len(ids) == len(set(ids)), "duplicate edge id in committed graph"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_repairs_in_graph.py -v`
Expected: FAIL — repairs edges / Barrelchest nodes don't exist yet.

- [ ] **Step 3: Add the loader + import in `assemble.py`**

Near the other `_load_*` helpers in `kg_ingest/assemble.py`, add:
```python
REPAIR_PATHS_PATH = Path(__file__).resolve().parents[1] / "data" / "repair_paths.json"


def _load_repair_path_records() -> list[dict]:
    if not REPAIR_PATHS_PATH.exists():
        return []
    return json.loads(REPAIR_PATHS_PATH.read_text())["records"]
```
And add the builder import with the others:
```python
from kg_ingest.builders.repairs import build_repairs
```

- [ ] **Step 4: Extend the shared item-`src` rekey to include `rp_edges`**

In `assemble.assemble()`, find the slice-3 region: it builds `_degrade_nodes, dg_edges = build_degrade_paths(...)`, then `referenced_all = _collect_referenced_ids(edges + dg_edges, groups)`, runs `build_items`, then `rekey(i_nodes, i_edges + dg_edges, {})`. Make these three edits:

(a) After the `build_degrade_paths(...)` line, add the repairs builder:
```python
    _repair_nodes, rp_edges, _ = build_repairs(_load_repair_path_records())  # _repair_nodes == []
```
(b) Change the reference-collection line to include `rp_edges`:
```python
    referenced_all = _collect_referenced_ids(edges + dg_edges + rp_edges, groups)
```
(c) Change the SHARED rekey line to include `rp_edges` (all three item-`src` edge types in one call):
```python
    i_nodes, item_edges, _ = rekey(i_nodes, i_edges + dg_edges + rp_edges, {})
```
(The `edges = edges + item_edges`, the global edge-id assert, `build_supporting`, and `dedup_nodes` lines stay unchanged — `build_repairs` emits no nodes.)

- [ ] **Step 5: Regenerate the committed graph**

Run: `./venv/bin/python -m kg_ingest.assemble`
Expected: writes `kg/*.json` without error (the edge-id assert passes — the shared rekey now covers same_entity + degrades_to + repairs).

- [ ] **Step 6: Verify byte-stability, validators, golden, integration**

Run:
```bash
./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/   # second run: NO further change
./venv/bin/python data/validate_kg.py            # exit 0 (repairs item->item, dst required clean)
./venv/bin/python data/validate_cost.py          # exit 0
./venv/bin/python data/verify_repair_paths.py    # exit 0
./venv/bin/python -m pytest tests/kg_ingest/test_golden_set.py tests/kg_ingest/test_items_in_graph.py tests/kg_ingest/test_recipes_in_graph.py tests/kg_ingest/test_degrade_paths_in_graph.py tests/kg_ingest/test_repairs_in_graph.py -q
```
Expected: assemble idempotent; validators exit 0; golden + slice-1/2/3 + new integration tests PASS. If the edge-id assert RAISES, the shared rekey wiring is wrong (rp_edges re-keyed separately). If `validate_kg` reports `[ref]`, a Barrelchest id didn't import — check it resolves in `item_dictionary.json`.

- [ ] **Step 7: Commit (graph + wiring together)**

```bash
git add kg_ingest/assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_repairs_in_graph.py
git commit -m "feat(kg): wire build_repairs into the shared rekey; regenerate graph with repairs"
```

---

### Task 5: Repair competency question

**Files:**
- Modify: `kg/competency_questions.json`
- Modify: `tests/kg_ingest/test_competency_questions.py`

**Interfaces:**
- Consumes: the committed KG (Task 4) + `repairs` edges.

- [ ] **Step 1: Add the CQ record to `kg/competency_questions.json` (red-first via unknown method)**

Append to the `records` array (after the last record — note the leading comma):
```json
    ,{ "id": "cq-dharoks-helm-repairable",
      "question": "Can a broken Dharok's helm be repaired?",
      "method": "is_repairable", "target": "item:4884", "expect_min": 1 }
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL — the runner has no `is_repairable` branch, so it raises `AssertionError: unknown method 'is_repairable'`.

- [ ] **Step 3: Add the runner method + dispatch branch**

In `tests/kg_ingest/test_competency_questions.py`, add a helper next to `_members`/`_family`/`_recipe_materials`/`_is_destroyed`:
```python
def _is_repairable(store, target):
    # the repaired-item set reachable from the broken target via a repairs edge
    return {e.dst for e in store.edges if e.type is EdgeType.REPAIRS and e.src == target}
```
And add a branch to the method dispatch in `test_all_competency_questions_pass` (before the final `else: raise`):
```python
        elif cq["method"] == "is_repairable":
            answer = _is_repairable(store, cq["target"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS — `item:4884` (broken Dharok's helm) has a `repairs` edge to `item:4716`, so the answer set is `{item:4716}` (size 1 ≥ expect_min 1).

- [ ] **Step 5: Final full-suite gate**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 6: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): competency question — broken Dharok's helm is repairable"
```

---

## Self-Review

**Spec coverage:** §2 model + schema → Task 1; §3 repairs model → Task 2; §4 data + verifier → Task 3; §5 builder + shared item-`src` rekey (extend to 3 edge types) + Barrelchest auto-import → Tasks 2/4; §6 success + the all-ids-unique test → Task 4; §6 CQ → Task 5. Deferred items (§8) correctly absent.

**Placeholder scan:** none — all code/commands concrete; repair ids + source tokens are the wiki-sourced real values (owner verifies), not placeholders.

**Type consistency:** `build_repairs(records)` signature consistent (Tasks 2/4); `EdgeType.REPAIRS`, the `broken`/`repaired`/`page`/`slug` record keys, and the `item:<id>` ids consistent across Tasks 2/3/4/5; the assemble edits (`rp_edges`, `i_edges + dg_edges + rp_edges`) match the slice-3 shared-rekey wiring they extend.
