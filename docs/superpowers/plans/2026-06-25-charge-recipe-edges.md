# Charge Recipe Edges — Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model OSRS item charging as v2's reified `recipe` relation (`recipe --consumes--> --produces-->`), the first edge-layer slice, for Scythe of vitur + Ring of suffering.

**Architecture:** Add `NodeKind.RECIPE` + `EdgeType.CONSUMES`/`PRODUCES` (additive); a new pure builder `kg_ingest/builders/recipes.py` reads a curated `data/charge_recipes.json` and emits recipe nodes + consumes/produces edges; `assemble.py` runs it *before* `build_items` so the consumed material ids auto-import via the slice-1 referenced mechanism. Adds a global edge-id-uniqueness assert. Design spec: `docs/superpowers/specs/2026-06-25-charge-recipe-edges-design.md`.

**Tech Stack:** Python 3.14 (`./venv/bin/python`), committed JSON, `pytest`. No new dependencies.

## Global Constraints

- Run everything via `./venv/bin/python` (Python 3.14).
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run produces identical bytes.
- **Gates stay green:** `./venv/bin/python data/validate_kg.py` exit 0; `./venv/bin/python data/validate_cost.py` exit 0; golden (`tests/kg_ingest/test_golden_set.py`) + slice-1 (`tests/kg_ingest/test_items_in_graph.py`, `test_competency_questions.py`) tests pass; full `pytest` green except the 4 pre-existing `tests/drop_rates/` collection errors (`No module named 'data._toa_drop_rates'`).
- **Schema changes are additive only.** `recipe`/`consumes`/`produces` are already declared in `kg/schema.json` (status `reserved`); this slice flips them to `live` and adds the enum members. No re-ingest.
- **Never fabricate.** `data/charge_recipes.json` is editorial: every recipe carries `source_url` + a verbatim `source_token`, and the quantities are wiki-sourced + owner-reviewed.
- **Node/edge ids:** recipe nodes `recipe:<slug>`; `consumes`/`produces` are recipe-`src` edges. Builder-local edge ids in a disjoint band (`0x60000000`), re-keyed to global ids by `assemble.rekey`.
- **Charge data (wiki-sourced, owner-verifies):** Scythe of vitur = 1 vial of blood (item 22446) + 200 blood runes (item 11697) → 100 charges, capacity 20000; subject = uncharged scythe item 22486; produces = charged scythe item 22325. Ring of suffering = 1 ring of recoil (item 2550) → 40 charges, capacity 100000; subject = uncharged ring item 19550; produces = recoil ring item 20655.

---

### Task 1: Add `RECIPE` / `CONSUMES` / `PRODUCES` + flip schema status

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py` (`NodeKind`, `EdgeType`)
- Modify: `kg/schema.json` (`recipe` node + `consumes`/`produces` edge status; recipe `data_keys`; `vocab`)
- Test: `tests/engine/test_kg_model.py`

**Interfaces:**
- Produces: `NodeKind.RECIPE` (`"recipe"`), `EdgeType.CONSUMES` (`"consumes"`), `EdgeType.PRODUCES` (`"produces"`) — consumed by Task 2's builder and Task 4's assemble.

- [ ] **Step 1: Write the failing test**

Add to `tests/engine/test_kg_model.py`:
```python
def test_recipe_kind_and_consumes_produces_edges_exist():
    from osrs_planner.engine.kg.model import NodeKind, EdgeType
    assert NodeKind.RECIPE.value == "recipe"
    assert EdgeType.CONSUMES.value == "consumes"
    assert EdgeType.PRODUCES.value == "produces"

def test_schema_declares_recipe_consumes_produces_live():
    import json, pathlib
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    assert schema["node_kinds"]["recipe"]["status"] == "live"
    assert schema["edge_kinds"]["consumes"]["status"] == "live"
    assert schema["edge_kinds"]["produces"]["status"] == "live"
    assert "charge_yield" in schema["node_kinds"]["recipe"]["data_keys"]
    assert schema["vocab"]["consumes_role"] == ["material", "subject"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py::test_recipe_kind_and_consumes_produces_edges_exist tests/engine/test_kg_model.py::test_schema_declares_recipe_consumes_produces_live -v`
Expected: FAIL — `AttributeError: RECIPE` / `'reserved' != 'live'`.

- [ ] **Step 3: Add the enum members**

In `src/osrs_planner/engine/kg/model.py`, in `class NodeKind`, after the last member add:
```python
    RECIPE = "recipe"                  # reified production/charging process (decision 3 / spec §3-4)
```
In `class EdgeType`, after `SAME_ENTITY = "same_entity"` add:
```python
    CONSUMES = "consumes"              # recipe -> item input (destroyed/transformed); reified {qty, role}
    PRODUCES = "produces"              # recipe -> item output; reified {qty}
```

- [ ] **Step 4: Flip schema status + extend recipe data_keys + add vocab**

In `kg/schema.json`:
- In `node_kinds.recipe`, change `"status": "reserved"` to `"status": "live"`, and change its `"data_keys"` to `["xp", "ticks", "charge_yield", "charge_capacity", "notes"]`.
- In `edge_kinds.consumes`, change `"status": "reserved"` to `"status": "live"`.
- In `edge_kinds.produces`, change `"status": "reserved"` to `"status": "live"`.
- In the top-level `"vocab"` object, add a key: `"consumes_role": ["material", "subject"]`.

- [ ] **Step 5: Run tests to verify they pass (incl. the model-enum⊆schema invariant)**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py tests/kg_ingest/test_validate_kg_schema.py::test_model_enums_are_all_declared_in_schema -v`
Expected: PASS (recipe/consumes/produces already declared in schema, so the subset invariant stays green).

- [ ] **Step 6: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py kg/schema.json tests/engine/test_kg_model.py
git commit -m "feat(kg): add NodeKind.RECIPE + EdgeType.CONSUMES/PRODUCES (schema live)"
```

---

### Task 2: `build_recipes` builder

**Files:**
- Create: `kg_ingest/builders/recipes.py`
- Test: `tests/kg_ingest/test_recipes_builder.py`

**Interfaces:**
- Produces: `build_recipes(records: list[dict]) -> tuple[list[Node], list[Edge], dict]` — each record `{slug, name, produces:{item_id,qty}, subject:{item_id,qty}, materials:[{item_id,qty,...}], charge_yield, charge_capacity, notes?}` → a `recipe:<slug>` node + a `consumes` edge per material (`role: material`) + a `consumes` edge for the subject (`role: subject`) + one `produces` edge. Returns `(nodes, edges, {})`.
- Consumes: `NodeKind.RECIPE`, `EdgeType.CONSUMES`/`PRODUCES` (Task 1); `kg_ingest.ids.item_id`/`_stable_hash`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kg_ingest/test_recipes_builder.py`:
```python
from kg_ingest.builders.recipes import build_recipes
from osrs_planner.engine.kg.model import EdgeType, NodeKind

REC = [{
    "slug": "charge-scythe-of-vitur", "name": "Charge Scythe of vitur",
    "produces": {"item_id": 22325, "qty": 1},
    "subject":  {"item_id": 22486, "qty": 1},
    "materials": [{"item_id": 11697, "qty": 200, "name": "Blood rune"},
                  {"item_id": 22446, "qty": 1, "name": "Vial of blood"}],
    "charge_yield": 100, "charge_capacity": 20000,
}]

def test_recipe_node_consumes_and_produces():
    nodes, edges, groups = build_recipes(REC)
    assert groups == {}
    n = {x.id: x for x in nodes}["recipe:charge-scythe-of-vitur"]
    assert n.kind is NodeKind.RECIPE and n.name == "Charge Scythe of vitur"
    assert n.data == {"charge_yield": 100, "charge_capacity": 20000}
    consumes = [(e.dst, e.data["qty"], e.data["role"]) for e in edges if e.type is EdgeType.CONSUMES]
    assert ("item:11697", 200, "material") in consumes
    assert ("item:22446", 1, "material") in consumes
    assert ("item:22486", 1, "subject") in consumes      # the uncharged variant, role=subject
    produces = [(e.dst, e.data["qty"]) for e in edges if e.type is EdgeType.PRODUCES]
    assert produces == [("item:22325", 1)]
    assert all(e.src == "recipe:charge-scythe-of-vitur" for e in edges)   # all edges recipe-src

def test_recipe_edges_are_deterministic():
    e1 = build_recipes(REC)[1]
    e2 = build_recipes(REC)[1]
    assert [(e.id, e.type, e.dst) for e in e1] == [(e.id, e.type, e.dst) for e in e2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_recipes_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: kg_ingest.builders.recipes`.

- [ ] **Step 3: Write the builder**

Create `kg_ingest/builders/recipes.py`:
```python
"""build_recipes — emit reified recipe nodes + consumes/produces edges.

First use: item-charging recipes (data/charge_recipes.json). Pure transform;
builder-local edge ids in a disjoint band, re-keyed by assemble.rekey (owner =
the recipe node, so no cross-builder collision).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, item_id

_EDGE_BAND = 0x60000000  # recipes-domain builder-local edge ids (rekeyed in assemble)


def _edge_id(recipe_id: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{recipe_id}#edge#{slot}")


def build_recipes(records):
    nodes: list[Node] = []
    edges: list[Edge] = []
    for rec in records:
        rid = f"recipe:{rec['slug']}"
        data = {"charge_yield": rec["charge_yield"], "charge_capacity": rec["charge_capacity"]}
        if rec.get("notes"):
            data["notes"] = rec["notes"]
        nodes.append(Node(id=rid, kind=NodeKind.RECIPE, name=rec["name"], slug=rec["slug"], data=data))
        slot = 0
        # materials (consumes, role=material) in a deterministic order (by item_id)
        for m in sorted(rec["materials"], key=lambda x: x["item_id"]):
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.CONSUMES, src=rid,
                              dst=item_id(m["item_id"]), cond_group=None,
                              data={"qty": m["qty"], "role": "material"}))
            slot += 1
        # subject (consumes, role=subject) = the uncharged variant (transformed, not destroyed)
        sub = rec["subject"]
        edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.CONSUMES, src=rid,
                          dst=item_id(sub["item_id"]), cond_group=None,
                          data={"qty": sub["qty"], "role": "subject"}))
        slot += 1
        # produces (the charged variant)
        prod = rec["produces"]
        edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.PRODUCES, src=rid,
                          dst=item_id(prod["item_id"]), cond_group=None, data={"qty": prod["qty"]}))
        slot += 1
    return nodes, edges, {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_recipes_builder.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/recipes.py tests/kg_ingest/test_recipes_builder.py
git commit -m "feat(kg): build_recipes — recipe node + consumes/produces edges"
```

---

### Task 3: Curated `charge_recipes.json` + `verify_charge_recipes.py`

**Files:**
- Create: `data/charge_recipes.json`
- Create: `data/verify_charge_recipes.py`
- Test: `tests/kg_ingest/test_verify_charge_recipes.py`

**Interfaces:**
- Produces: the committed charge data (consumed by Task 4) + a CLI verifier returning exit 0/1.

- [ ] **Step 1: Create `data/charge_recipes.json`** (wiki-sourced quantities; owner verifies)

```json
{
  "_provenance": {
    "note": "curated item-charging recipes (consume-materials); editorial — owner-reviewed",
    "license": "CC BY-NC-SA 3.0",
    "accessed": "2026-06-25"
  },
  "records": [
    { "slug": "charge-scythe-of-vitur", "name": "Charge Scythe of vitur",
      "produces": {"item_id": 22325, "qty": 1},
      "subject":  {"item_id": 22486, "qty": 1},
      "materials": [ {"item_id": 11697, "qty": 200, "name": "Blood rune"},
                     {"item_id": 22446, "qty": 1, "name": "Vial of blood"} ],
      "charge_yield": 100, "charge_capacity": 20000,
      "source_url": "https://oldschool.runescape.wiki/w/Scythe_of_vitur",
      "source_token": "Each vial and 200 blood runes adds 100 charges to the scythe, with it being able to hold up to 20,000 charges" },
    { "slug": "charge-ring-of-suffering", "name": "Charge Ring of suffering",
      "produces": {"item_id": 20655, "qty": 1},
      "subject":  {"item_id": 19550, "qty": 1},
      "materials": [ {"item_id": 2550, "qty": 1, "name": "Ring of recoil"} ],
      "charge_yield": 40, "charge_capacity": 100000,
      "source_url": "https://oldschool.runescape.wiki/w/Ring_of_suffering",
      "source_token": "The ring can also be charged with noted and unnoted rings of recoil to give it the recoil effect, renaming the item as the Ring of suffering (r)." }
  ]
}
```

- [ ] **Step 2: Write the failing verifier test**

Create `tests/kg_ingest/test_verify_charge_recipes.py`:
```python
import os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _run():
    return subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_charge_recipes.py")],
                          capture_output=True, text=True)

def test_verifier_passes_on_committed_charge_recipes():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CHARGE-RECIPES VERIFICATION PASSED" in r.stdout
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_charge_recipes.py -v`
Expected: FAIL — `verify_charge_recipes.py` does not exist.

- [ ] **Step 4: Write the verifier**

Create `data/verify_charge_recipes.py`:
```python
#!/usr/bin/env python3
"""Source-grounding gate for data/charge_recipes.json (editorial charge layer).

Checks: every produces/subject/material item_id resolves in item_dictionary.json;
every record has source_url + a non-empty source_token; slugs are unique; every
qty / charge_yield / charge_capacity is a positive int; and produces & subject
share a page_name in item_dictionary (wrong-pairing guard). Exits non-zero on any
violation. Mirrors data/verify_item_families.py.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
CHARGES = os.path.join(ROOT, "data", "charge_recipes.json")


def _pos_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def main() -> int:
    errors: list[str] = []
    with open(DICT, encoding="utf-8") as f:
        id_to_page = {r["item_id"]: r["page_name"] for r in json.load(f)["records"]}
    with open(CHARGES, encoding="utf-8") as f:
        doc = json.load(f)
    seen: set[str] = set()
    for rec in doc["records"]:
        slug = rec.get("slug", "")
        if not slug:
            errors.append("[slug] record missing slug")
        if slug in seen:
            errors.append(f"[slug] duplicate recipe slug {slug!r}")
        seen.add(slug)
        if not rec.get("source_url") or not rec.get("source_token"):
            errors.append(f"[source] {slug!r} missing source_url/source_token")
        prod, subj = rec.get("produces", {}), rec.get("subject", {})
        refs = [prod, subj] + list(rec.get("materials", []))
        for ref in refs:
            iid = ref.get("item_id")
            if iid not in id_to_page:
                errors.append(f"[item] {slug!r} item_id {iid!r} not in item_dictionary")
            if not _pos_int(ref.get("qty")):
                errors.append(f"[qty] {slug!r} item_id {iid!r} qty not a positive int: {ref.get('qty')!r}")
        for key in ("charge_yield", "charge_capacity"):
            if not _pos_int(rec.get(key)):
                errors.append(f"[charge] {slug!r} {key} not a positive int: {rec.get(key)!r}")
        # wrong-pairing guard: produces & subject must be the same item-family (page_name)
        pp, sp = id_to_page.get(prod.get("item_id")), id_to_page.get(subj.get("item_id"))
        if pp is not None and sp is not None and pp != sp:
            errors.append(f"[pair] {slug!r} produces page {pp!r} != subject page {sp!r}")
    if errors:
        print(f"CHARGE-RECIPES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("CHARGE-RECIPES VERIFICATION PASSED — all charge recipes source-grounded.")
    print(f"  recipes: {len(doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test + verifier to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_charge_recipes.py -v && ./venv/bin/python data/verify_charge_recipes.py`
Expected: PASS; verifier prints `CHARGE-RECIPES VERIFICATION PASSED`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add data/charge_recipes.json data/verify_charge_recipes.py tests/kg_ingest/test_verify_charge_recipes.py
git commit -m "data(kg): curated charge recipes (scythe, ring of suffering) + source-grounding verifier"
```

---

### Task 4: Wire `build_recipes` into `assemble.py` + edge-id guard + regenerate

**Files:**
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_recipes_in_graph.py`

**Interfaces:**
- Consumes: `build_recipes` (Task 2), `data/charge_recipes.json` (Task 3), `rekey`/`_collect_referenced_ids`/`build_items`/`dedup_nodes` (existing).

- [ ] **Step 1: Write the failing integration test**

Create `tests/kg_ingest/test_recipes_in_graph.py`:
```python
import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType, NodeKind

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_committed_graph_has_charge_recipe_and_imported_materials():
    s = JsonKGStore.from_dir(KG)
    r = s.node("recipe:charge-scythe-of-vitur")
    assert r is not None and r.kind is NodeKind.RECIPE
    # materials auto-imported as item nodes via build_items (referenced mechanism)
    assert s.node("item:11697") is not None   # Blood rune
    assert s.node("item:22446") is not None    # Vial of blood
    # consumes/produces edges present, recipe-src
    cons = {(e.src, e.dst, e.data.get("role")) for e in s.edges if e.type is EdgeType.CONSUMES}
    assert ("recipe:charge-scythe-of-vitur", "item:11697", "material") in cons
    assert ("recipe:charge-scythe-of-vitur", "item:22486", "subject") in cons
    prod = {(e.src, e.dst) for e in s.edges if e.type is EdgeType.PRODUCES}
    assert ("recipe:charge-scythe-of-vitur", "item:22325") in prod
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_recipes_in_graph.py -v`
Expected: FAIL — the recipe node / material nodes don't exist yet.

- [ ] **Step 3: Add the loader + import in `assemble.py`**

Near the other `_load_*` helpers in `kg_ingest/assemble.py`, add:
```python
CHARGE_RECIPES_PATH = Path(__file__).resolve().parents[1] / "data" / "charge_recipes.json"


def _load_charge_recipe_records() -> list[dict]:
    if not CHARGE_RECIPES_PATH.exists():
        return []
    return json.loads(CHARGE_RECIPES_PATH.read_text())["records"]
```
And add the builder import with the others:
```python
from kg_ingest.builders.recipes import build_recipes
```

- [ ] **Step 4: Wire `build_recipes` BEFORE the reference collection, and add the edge-id assert**

In `assemble.assemble()`, find the block (added in slice 1) that begins by computing `referenced_all = _collect_referenced_ids(edges, groups)` and ends with `s_nodes = build_supporting(referenced)`. Replace from the `owned_ids = (...)` assignment down to `s_nodes = build_supporting(referenced)` with:
```python
    owned_ids = (
        {n.id for n in q_nodes}
        | {n.id for n in g_nodes}
        | {n.id for n in cg_nodes}
        | {n.id for n in d_nodes}
        | {n.id for n in dg_nodes}
        | {n.id for n in content_nodes}
    )
    # Recipe layer: emit recipe nodes + consumes/produces edges FIRST, so the consumed/produced
    # item ids land in referenced_item_ids and build_items auto-imports the material nodes.
    r_nodes, r_edges, _ = build_recipes(_load_charge_recipe_records())
    r_nodes, r_edges, _ = rekey(r_nodes, r_edges, {})
    edges = edges + r_edges
    owned_ids = owned_ids | {n.id for n in r_nodes}

    referenced_all = _collect_referenced_ids(edges, groups)
    referenced_item_ids = {r for r in referenced_all if r.startswith("item:")} - owned_ids
    i_nodes, i_edges, _ = build_items(
        _load_item_dict_records(), _load_item_exemplars(), _load_item_families(),
        referenced_item_ids, owned_ids=frozenset(owned_ids),
    )
    i_nodes, i_edges, _ = rekey(i_nodes, i_edges, {})
    edges = edges + i_edges
    # Global edge-id uniqueness (fail-fast): rekey only de-dups WITHIN one call; this catches a
    # cross-call collision (an item:* src re-keyed in two builders) before it ships. validate_kg's
    # amendment-C duplicate-edge-id check is the committed backstop.
    _eids = [e.id for e in edges]
    if len(_eids) != len(set(_eids)):
        _dupes = sorted({i for i in _eids if _eids.count(i) > 1})
        raise ValueError(f"duplicate global edge ids after rekey: {_dupes[:10]}")
    owned_ids = owned_ids | {n.id for n in i_nodes}
    referenced = {
        r for r in referenced_all
        if r.split(":")[0] in _LEAF_DOMAINS
    } - owned_ids
    s_nodes = build_supporting(referenced)
```
(The `_LEAF_DOMAINS = frozenset(...)` line stays where it is, just above this block.)

Then add `r_nodes` to the final `dedup_nodes(...)` call (before `i_nodes`):
```python
    nodes = dedup_nodes(
        q_nodes + g_nodes + cg_nodes + d_nodes + dg_nodes + content_nodes + r_nodes + i_nodes + s_nodes
    )
```

- [ ] **Step 5: Regenerate the committed graph**

Run: `./venv/bin/python -m kg_ingest.assemble`
Expected: writes `kg/*.json` without error (the edge-id assert passes).

- [ ] **Step 6: Verify byte-stability, validators, golden, integration**

Run:
```bash
./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/   # second run: NO further change
./venv/bin/python data/validate_kg.py            # exit 0 (recipe nodes + consumes/produces clean)
./venv/bin/python data/validate_cost.py          # exit 0
./venv/bin/python data/verify_charge_recipes.py  # exit 0
./venv/bin/python -m pytest tests/kg_ingest/test_golden_set.py tests/kg_ingest/test_items_in_graph.py tests/kg_ingest/test_recipes_in_graph.py -q
```
Expected: assemble idempotent; validators exit 0; golden + slice-1 + new integration tests PASS. If `validate_kg` reports a domain/range VIOLATION on `consumes`/`produces`, an endpoint kind is wrong (recipe-src, item-dst); if `[ref]`, a material id didn't import — check it resolves in `item_dictionary.json`.

- [ ] **Step 7: Commit (graph + wiring together)**

```bash
git add kg_ingest/assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_recipes_in_graph.py
git commit -m "feat(kg): wire build_recipes into assemble (+ edge-id guard); regenerate graph with charge recipes"
```

---

### Task 5: Charge-cost competency question

**Files:**
- Modify: `kg/competency_questions.json`
- Modify: `tests/kg_ingest/test_competency_questions.py`

**Interfaces:**
- Consumes: the committed KG (Task 4) + `consumes` edges with `data.role`.

- [ ] **Step 1: Add the CQ record to `kg/competency_questions.json` (red-first via unknown method)**

Append to the `records` array (after the scythe-family entry — note the leading comma):
```json
    ,{ "id": "cq-charge-cost-scythe-of-vitur",
      "question": "What materials does it cost to charge a Scythe of vitur?",
      "method": "recipe_materials", "target": "recipe:charge-scythe-of-vitur", "expect_min": 2 }
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL — the runner's method dispatch has no `recipe_materials` branch, so it raises `AssertionError: unknown method 'recipe_materials'`.

- [ ] **Step 3: Add the runner method + dispatch branch**

In `tests/kg_ingest/test_competency_questions.py`, add a helper next to `_members`/`_family`:
```python
def _recipe_materials(store, target):
    return {e.dst for e in store.edges
            if e.type is EdgeType.CONSUMES and e.src == target and (e.data or {}).get("role") == "material"}
```
And add a branch to the method dispatch in `test_all_competency_questions_pass` (before the final `else: raise`):
```python
        elif cq["method"] == "recipe_materials":
            answer = _recipe_materials(store, cq["target"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS — the recipe's two `role:material` consumes (Blood rune, Vial of blood) satisfy `expect_min` 2.

- [ ] **Step 5: Final full-suite gate**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 6: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): competency question — charge-cost materials for Scythe of vitur"
```

---

## Self-Review

**Spec coverage:** §2 model additions → Task 1; §3 recipe model → Task 2; §4 data + verifier → Task 3; §5 builder + assemble material-import handoff → Tasks 2/4; §6 edge-id assert → Task 4; §7 success criteria → Task 4 step 6 + Task 5; §7 CQ → Task 5. Deferred items (§8/§9) correctly absent.

**Placeholder scan:** none — all code/commands concrete; charge quantities are the wiki-sourced real values (owner verifies), not placeholders.

**Type consistency:** `build_recipes(records)` signature consistent (Tasks 2/4); `recipe:<slug>` ids, `consumes`/`produces` edge types, `data.role` (`material`/`subject`), and `data.qty` consistent across Tasks 2/3/4/5; the assemble block names (`r_nodes`/`r_edges`/`referenced_all`/`referenced_item_ids`/`i_nodes`) match the slice-1 wiring it edits.
