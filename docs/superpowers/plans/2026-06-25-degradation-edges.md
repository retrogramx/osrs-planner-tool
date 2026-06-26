# Degradation Edges (`degrades_to`) — Slice 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model OSRS item degradation as a new `degrades_to` downgrade ladder (per-step edges through charge-count variants; terminal = destroyed / reverts_to / broken) for Ring of dueling, Amulet of glory, Scythe of vitur, and Dharok's helm.

**Architecture:** Add `EdgeType.DEGRADES_TO` (additive) + a new `degrades_to` schema entry; a new pure builder `kg_ingest/builders/degrade_paths.py` reads a curated `data/degrade_paths.json` and emits the `degrades_to` chains; `assemble.py` runs it before `build_items` (so Dharok's variants auto-import) and — because `degrades_to` is item-`src` like `same_entity` — re-keys its edges TOGETHER with `build_items`' edges in one shared `rekey` call (avoiding a cross-call edge-id collision). Design spec: `docs/superpowers/specs/2026-06-25-degradation-edges-design.md`.

**Tech Stack:** Python 3.14 (`./venv/bin/python`), committed JSON, `pytest`. No new dependencies.

## Global Constraints

- Run everything via `./venv/bin/python` (Python 3.14).
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run produces identical bytes.
- **Gates stay green:** `./venv/bin/python data/validate_kg.py` exit 0; `./venv/bin/python data/validate_cost.py` exit 0; golden (`tests/kg_ingest/test_golden_set.py`) + slice-1/2 tests (`test_items_in_graph.py`, `test_recipes_in_graph.py`, `test_competency_questions.py`) pass; full `pytest` green except the 4 pre-existing `tests/drop_rates/` collection errors (`No module named 'data._toa_drop_rates'`).
- **Additive ontology extension:** `degrades_to` is NEW (not in v2 §3 — that's `supersedes`). Add the enum member AND a new `kg/schema.json` `edge_kinds.degrades_to` entry. The `model-enum ⊆ schema` invariant must stay green.
- **Never fabricate.** `data/degrade_paths.json` is editorial: every record carries `source_url` + a verbatim `source_token`; orderings are wiki-sourced + owner-reviewed.
- **Edge ids:** `degrades_to` is item-`src`. Builder-local edge ids in a disjoint band (`0xA0000000`). `degrades_to` edges are re-keyed TOGETHER with `build_items`' `same_entity` edges in one `rekey` call (shared per-owner index → no cross-call collision).
- **Degrade data (wiki-sourced, owner-verifies):** Ring of dueling = ids 2552(8)/2554(7)/2556(6)/2558(5)/2560(4)/2562(3)/2564(2)/2566(1), terminal **destroyed**. Amulet of glory = 11978(6)/11976(5)/1712(4)/1710(3)/1708(2)/1706(1) → **reverts_to** 1704 (uncharged). Scythe of vitur = 22325(charged) → **reverts_to** 22486 (uncharged). Dharok's helm = 4716(Undamaged)/4880(100)/4881(75)/4882(50)/4883(25) → **broken** 4884 (0).

---

### Task 1: Add `EdgeType.DEGRADES_TO` + new schema edge entry

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py` (`EdgeType`)
- Modify: `kg/schema.json` (new `edge_kinds.degrades_to` + `vocab`)
- Test: `tests/engine/test_kg_model.py`

**Interfaces:**
- Produces: `EdgeType.DEGRADES_TO` (`"degrades_to"`) — consumed by Task 2's builder and Task 4's assemble.

- [ ] **Step 1: Write the failing test**

Add to `tests/engine/test_kg_model.py`:
```python
def test_degrades_to_edge_exists_and_declared_live():
    from osrs_planner.engine.kg.model import EdgeType
    assert EdgeType.DEGRADES_TO.value == "degrades_to"
    import json, pathlib
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    d = schema["edge_kinds"]["degrades_to"]
    assert d["status"] == "live" and d["domain"] == ["item"] and d["range"] == ["item"] and d["dst"] == "optional"
    assert schema["vocab"]["degrade_terminal"] == ["destroyed", "reverts_to", "broken"]
    assert schema["vocab"]["degrade_trigger"] == ["per_use", "per_hit"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py::test_degrades_to_edge_exists_and_declared_live -v`
Expected: FAIL — `AttributeError: DEGRADES_TO` / `KeyError: 'degrades_to'`.

- [ ] **Step 3: Add the enum member**

In `src/osrs_planner/engine/kg/model.py`, in `class EdgeType`, after `PRODUCES = "produces"` add:
```python
    DEGRADES_TO = "degrades_to"        # downgrade ladder through use (inverse of supersedes); dst=None = destroyed
```

- [ ] **Step 4: Add the schema edge entry + vocab**

In `kg/schema.json`, in the `"edge_kinds"` object, add a new entry right after the `"supersedes"` entry:
```json
    "degrades_to": {"status": "live", "domain": ["item"], "range": ["item"], "dst": "optional", "cond_group": "forbidden", "reified": true, "notes": "Downgrade ladder through use (additive extension; inverse of supersedes' upgrade). Per-step item->item; terminal edge dst=None = destroyed, dst=uncharged = reverts_to, dst=broken = broken. data.trigger + data.terminal."},
```
In the top-level `"vocab"` object, add two keys:
```json
    "degrade_terminal": ["destroyed", "reverts_to", "broken"],
    "degrade_trigger": ["per_use", "per_hit"],
```

- [ ] **Step 5: Run tests to verify they pass (incl. the model-enum⊆schema invariant)**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py tests/kg_ingest/test_validate_kg_schema.py::test_model_enums_are_all_declared_in_schema -v`
Expected: PASS (degrades_to now declared in both the enum and the schema).

- [ ] **Step 6: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py kg/schema.json tests/engine/test_kg_model.py
git commit -m "feat(kg): add EdgeType.DEGRADES_TO + schema entry (additive extension)"
```

---

### Task 2: `build_degrade_paths` builder

**Files:**
- Create: `kg_ingest/builders/degrade_paths.py`
- Test: `tests/kg_ingest/test_degrade_paths_builder.py`

**Interfaces:**
- Produces: `build_degrade_paths(records: list[dict]) -> tuple[list[Node], list[Edge], dict]` — each record `{slug, page, trigger, sequence:[item_id...], terminal:"destroyed"|"reverts_to"|"broken", terminal_item?:item_id}` → a `degrades_to` edge between each consecutive `sequence` pair (`data={trigger}`) + a terminal edge from the last sequence id (`dst=None` for destroyed, else `dst=item:<terminal_item>`, `data={trigger, terminal}`). Returns `(nodes=[], edges, {})` — emits NO nodes.
- Consumes: `EdgeType.DEGRADES_TO` (Task 1); `kg_ingest.ids.item_id`/`_stable_hash`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kg_ingest/test_degrade_paths_builder.py`:
```python
from kg_ingest.builders.degrade_paths import build_degrade_paths
from osrs_planner.engine.kg.model import EdgeType

DESTROYED = [{"slug": "ring-of-dueling-degrade", "page": "Ring of dueling", "trigger": "per_use",
              "sequence": [2552, 2554, 2566], "terminal": "destroyed"}]
REVERTS = [{"slug": "scythe-of-vitur-degrade", "page": "Scythe of vitur", "trigger": "per_hit",
            "sequence": [22325], "terminal": "reverts_to", "terminal_item": 22486}]
BROKEN = [{"slug": "dharoks-helm-degrade", "page": "Dharok's helm", "trigger": "per_hit",
           "sequence": [4716, 4883], "terminal": "broken", "terminal_item": 4884}]

def test_destroyed_chain_ends_in_dst_none():
    nodes, edges, groups = build_degrade_paths(DESTROYED)
    assert nodes == [] and groups == {}
    chain = [(e.src, e.dst) for e in edges if e.type is EdgeType.DEGRADES_TO]
    assert ("item:2552", "item:2554") in chain          # step edge
    assert ("item:2554", "item:2566") in chain          # step edge
    term = [e for e in edges if e.src == "item:2566"]
    assert len(term) == 1 and term[0].dst is None and term[0].data == {"trigger": "per_use", "terminal": "destroyed"}
    assert all(e.data["trigger"] == "per_use" for e in edges)

def test_reverts_to_terminal_points_to_uncharged_node():
    _, edges, _ = build_degrade_paths(REVERTS)
    assert len(edges) == 1
    e = edges[0]
    assert e.src == "item:22325" and e.dst == "item:22486" and e.data["terminal"] == "reverts_to"

def test_broken_terminal_points_to_broken_node():
    _, edges, _ = build_degrade_paths(BROKEN)
    term = [e for e in edges if e.src == "item:4883"]
    assert len(term) == 1 and term[0].dst == "item:4884" and term[0].data["terminal"] == "broken"
    assert ("item:4716", "item:4883") in {(e.src, e.dst) for e in edges}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_degrade_paths_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: kg_ingest.builders.degrade_paths`.

- [ ] **Step 3: Write the builder**

Create `kg_ingest/builders/degrade_paths.py`:
```python
"""build_degrade_paths — emit degrades_to downgrade-ladder edges (slice 3).

Per family: a degrades_to edge between each consecutive `sequence` item, then a
terminal edge from the last sequence item (dst=None=destroyed, else dst=the
uncharged/broken terminal_item). Emits NO nodes — every endpoint is a slice-1
node or auto-imported by build_items. degrades_to is ITEM-src; assemble re-keys
these TOGETHER with build_items' same_entity edges (shared per-owner index).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType, Node
from kg_ingest.ids import _stable_hash, item_id

_EDGE_BAND = 0xA0000000  # degrade-paths builder-local edge ids (rekeyed in assemble)


def _edge_id(src_id: str) -> int:
    # one outgoing degrades_to per variant, so a single per-src slot suffices
    return _EDGE_BAND | _stable_hash(f"{src_id}#degrades_to")


def build_degrade_paths(records):
    nodes: list[Node] = []
    edges: list[Edge] = []
    for rec in records:
        seq = rec["sequence"]
        trigger = rec["trigger"]
        for i in range(len(seq) - 1):
            src = item_id(seq[i])
            edges.append(Edge(id=_edge_id(src), type=EdgeType.DEGRADES_TO, src=src,
                              dst=item_id(seq[i + 1]), cond_group=None, data={"trigger": trigger}))
        last = item_id(seq[-1])
        terminal = rec["terminal"]
        dst = None if terminal == "destroyed" else item_id(rec["terminal_item"])
        edges.append(Edge(id=_edge_id(last), type=EdgeType.DEGRADES_TO, src=last, dst=dst,
                          cond_group=None, data={"trigger": trigger, "terminal": terminal}))
    return nodes, edges, {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_degrade_paths_builder.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/degrade_paths.py tests/kg_ingest/test_degrade_paths_builder.py
git commit -m "feat(kg): build_degrade_paths — degrades_to ladder (3 terminals)"
```

---

### Task 3: Curated `degrade_paths.json` + `verify_degrade_paths.py`

**Files:**
- Create: `data/degrade_paths.json`
- Create: `data/verify_degrade_paths.py`
- Test: `tests/kg_ingest/test_verify_degrade_paths.py`

**Interfaces:**
- Produces: the committed degrade data (consumed by Task 4) + a CLI verifier returning exit 0/1.

- [ ] **Step 1: Create `data/degrade_paths.json`** (wiki-sourced; owner verifies orderings)

```json
{
  "_provenance": {
    "note": "curated item degradation paths (downgrade ladders); editorial — owner-reviewed",
    "license": "CC BY-NC-SA 3.0",
    "accessed": "2026-06-25"
  },
  "records": [
    { "slug": "ring-of-dueling-degrade", "page": "Ring of dueling", "trigger": "per_use",
      "sequence": [2552, 2554, 2556, 2558, 2560, 2562, 2564, 2566], "terminal": "destroyed",
      "source_url": "https://oldschool.runescape.wiki/w/Ring_of_dueling",
      "source_token": "Your ring of dueling crumbles to dust." },
    { "slug": "amulet-of-glory-degrade", "page": "Amulet of glory", "trigger": "per_use",
      "sequence": [11978, 11976, 1712, 1710, 1708, 1706], "terminal": "reverts_to", "terminal_item": 1704,
      "source_url": "https://oldschool.runescape.wiki/w/Amulet_of_glory",
      "source_token": "After at least one charge has been used, an amulet of glory can be recharged by using it on either the Fountain of Uhld or the Fountain of Heroes." },
    { "slug": "scythe-of-vitur-degrade", "page": "Scythe of vitur", "trigger": "per_hit",
      "sequence": [22325], "terminal": "reverts_to", "terminal_item": 22486,
      "source_url": "https://oldschool.runescape.wiki/w/Scythe_of_vitur",
      "source_token": "The fully charged scythe will last for 16.66 hours of continuous combat before reverting to its uncharged form." },
    { "slug": "dharoks-helm-degrade", "page": "Dharok's helm", "trigger": "per_hit",
      "sequence": [4716, 4880, 4881, 4882, 4883], "terminal": "broken", "terminal_item": 4884,
      "source_url": "https://oldschool.runescape.wiki/w/Dharok's_helm",
      "source_token": "Eventually it will degrade to Dharok's helm 75, then 50, then 25 and finally 0 at which point the equipment will be unusable until repaired." }
  ]
}
```

- [ ] **Step 2: Write the failing verifier test**

Create `tests/kg_ingest/test_verify_degrade_paths.py`:
```python
import os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _run():
    return subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_degrade_paths.py")],
                          capture_output=True, text=True)

def test_verifier_passes_on_committed_degrade_paths():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DEGRADE-PATHS VERIFICATION PASSED" in r.stdout
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_degrade_paths.py -v`
Expected: FAIL — `verify_degrade_paths.py` does not exist.

- [ ] **Step 4: Write the verifier**

Create `data/verify_degrade_paths.py`:
```python
#!/usr/bin/env python3
"""Source-grounding gate for data/degrade_paths.json (editorial degradation layer).

Checks: every sequence[] + terminal_item id resolves in item_dictionary.json;
sequence non-empty and all its ids share page_name (== record's page); terminal in
{destroyed, reverts_to, broken}; reverts_to/broken carry a terminal_item sharing the
page_name; destroyed carries NO terminal_item; trigger in {per_use, per_hit}; slug
unique; source_url + non-empty source_token. Exits non-zero on any violation.
Mirrors data/verify_charge_recipes.py.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
PATHS = os.path.join(ROOT, "data", "degrade_paths.json")
_TERMINALS = {"destroyed", "reverts_to", "broken"}
_TRIGGERS = {"per_use", "per_hit"}


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
        if rec.get("trigger") not in _TRIGGERS:
            errors.append(f"[trigger] {slug!r} bad trigger {rec.get('trigger')!r}")
        page = rec.get("page")
        seq = rec.get("sequence") or []
        if not seq:
            errors.append(f"[sequence] {slug!r} empty sequence")
        for iid in seq:
            if iid not in id_to_page:
                errors.append(f"[item] {slug!r} sequence id {iid!r} not in item_dictionary")
            elif id_to_page[iid] != page:
                errors.append(f"[page] {slug!r} sequence id {iid!r} page {id_to_page[iid]!r} != {page!r}")
        terminal = rec.get("terminal")
        if terminal not in _TERMINALS:
            errors.append(f"[terminal] {slug!r} bad terminal {terminal!r}")
        if terminal == "destroyed":
            if "terminal_item" in rec:
                errors.append(f"[terminal] {slug!r} destroyed must NOT carry a terminal_item")
        elif terminal in ("reverts_to", "broken"):
            ti = rec.get("terminal_item")
            if ti not in id_to_page:
                errors.append(f"[item] {slug!r} terminal_item {ti!r} not in item_dictionary")
            elif id_to_page[ti] != page:
                errors.append(f"[page] {slug!r} terminal_item page {id_to_page[ti]!r} != {page!r}")
    if errors:
        print(f"DEGRADE-PATHS VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("DEGRADE-PATHS VERIFICATION PASSED — all degrade paths source-grounded.")
    print(f"  paths: {len(doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test + verifier to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_degrade_paths.py -v && ./venv/bin/python data/verify_degrade_paths.py`
Expected: PASS; verifier prints `DEGRADE-PATHS VERIFICATION PASSED`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add data/degrade_paths.json data/verify_degrade_paths.py tests/kg_ingest/test_verify_degrade_paths.py
git commit -m "data(kg): curated degrade paths (dueling/glory/scythe/dharoks) + verifier"
```

---

### Task 4: Wire into `assemble.py` (shared item-`src` rekey) + regenerate

**Files:**
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_degrade_paths_in_graph.py`

**Interfaces:**
- Consumes: `build_degrade_paths` (Task 2), `data/degrade_paths.json` (Task 3), `build_items`/`rekey`/`_collect_referenced_ids` (existing).

- [ ] **Step 1: Write the failing integration test**

Create `tests/kg_ingest/test_degrade_paths_in_graph.py`:
```python
import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_degrade_terminals_and_dharoks_autoimport():
    s = JsonKGStore.from_dir(KG)
    # destroyed: Ring of dueling (1) -> None
    t = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:2566"]
    assert len(t) == 1 and t[0].dst is None and t[0].data["terminal"] == "destroyed"
    # reverts_to: Scythe charged -> uncharged
    sc = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:22325"]
    assert len(sc) == 1 and sc[0].dst == "item:22486" and sc[0].data["terminal"] == "reverts_to"
    # broken: Dharok's variants auto-imported + terminal to the broken (0) node
    assert s.node("item:4880") is not None and s.node("item:4884") is not None
    dh = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:4883"]
    assert len(dh) == 1 and dh[0].dst == "item:4884" and dh[0].data["terminal"] == "broken"

def test_shared_rekey_gives_distinct_ids_for_same_entity_and_degrades_to():
    # Ring of dueling (8) item:2552 is the SRC of both a same_entity edge (slice 1)
    # and a degrades_to edge (this slice). The shared rekey must give them distinct ids.
    s = JsonKGStore.from_dir(KG)
    se = [e for e in s.edges if e.type is EdgeType.SAME_ENTITY and e.src == "item:2552"]
    dg = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:2552"]
    assert len(se) == 1 and len(dg) == 1
    assert se[0].id != dg[0].id, "shared rekey collision: same_entity and degrades_to got the same edge id"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_degrade_paths_in_graph.py -v`
Expected: FAIL — degrades_to edges / Dharok's nodes don't exist yet.

- [ ] **Step 3: Add the loader + import in `assemble.py`**

Near the other `_load_*` helpers in `kg_ingest/assemble.py`, add:
```python
DEGRADE_PATHS_PATH = Path(__file__).resolve().parents[1] / "data" / "degrade_paths.json"


def _load_degrade_path_records() -> list[dict]:
    if not DEGRADE_PATHS_PATH.exists():
        return []
    return json.loads(DEGRADE_PATHS_PATH.read_text())["records"]
```
And add the builder import with the others:
```python
from kg_ingest.builders.degrade_paths import build_degrade_paths
```

- [ ] **Step 4: Wire `build_degrade_paths` in with a SHARED rekey**

In `assemble.assemble()`, find the slice-2 region that runs `build_recipes`, then computes `referenced_all`, runs `build_items`, re-keys `i_edges` alone, appends them, and asserts edge-id uniqueness. Replace from the `build_recipes(...)` line down to the global edge-id assert with:
```python
    r_nodes, r_edges, _ = build_recipes(_load_charge_recipe_records())
    r_nodes, r_edges, _ = rekey(r_nodes, r_edges, {})
    edges = edges + r_edges
    owned_ids = owned_ids | {n.id for n in r_nodes}

    # Degradation layer: degrades_to edges are ITEM-src (like build_items' same_entity edges).
    # Build them now (builder-local ids) so their item dsts (incl. Dharok's degrade variants)
    # are collected for import, but do NOT rekey them separately — rekey TOGETHER with
    # build_items below so a shared owner gets distinct per-owner indices (no cross-call collision).
    _dg_nodes, dg_edges, _ = build_degrade_paths(_load_degrade_path_records())  # _dg_nodes == []

    referenced_all = _collect_referenced_ids(edges + dg_edges, groups)
    referenced_item_ids = {r for r in referenced_all if r.startswith("item:")} - owned_ids
    i_nodes, i_edges, _ = build_items(
        _load_item_dict_records(), _load_item_exemplars(), _load_item_families(),
        referenced_item_ids, owned_ids=frozenset(owned_ids),
    )
    # SHARED REKEY: same_entity (i_edges) + degrades_to (dg_edges), both item-src, in one call,
    # so an item that is the src of BOTH gets distinct per-owner indices (0 and 1).
    i_nodes, item_edges, _ = rekey(i_nodes, i_edges + dg_edges, {})
    edges = edges + item_edges
    # Global edge-id uniqueness (fail-fast backstop for the shared rekey + any future item-src slice).
    _eids = [e.id for e in edges]
    if len(_eids) != len(set(_eids)):
        _dupes = sorted({i for i in _eids if _eids.count(i) > 1})
        raise ValueError(f"duplicate global edge ids after rekey: {_dupes[:10]}")
    owned_ids = owned_ids | {n.id for n in i_nodes}
```
(The `referenced = {...} - owned_ids` and `s_nodes = build_supporting(referenced)` lines that follow stay as-is; the `dedup_nodes(...)` call is unchanged — `build_degrade_paths` emits no nodes.)

- [ ] **Step 5: Regenerate the committed graph**

Run: `./venv/bin/python -m kg_ingest.assemble`
Expected: writes `kg/*.json` without error (the edge-id assert passes — the shared rekey prevents the same_entity/degrades_to collision).

- [ ] **Step 6: Verify byte-stability, validators, golden, integration**

Run:
```bash
./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/   # second run: NO further change
./venv/bin/python data/validate_kg.py            # exit 0 (degrades_to item->item, dst optional clean)
./venv/bin/python data/validate_cost.py          # exit 0
./venv/bin/python data/verify_degrade_paths.py   # exit 0
./venv/bin/python -m pytest tests/kg_ingest/test_golden_set.py tests/kg_ingest/test_items_in_graph.py tests/kg_ingest/test_recipes_in_graph.py tests/kg_ingest/test_degrade_paths_in_graph.py -q
```
Expected: assemble idempotent; validators exit 0; golden + slice-1/2 + new integration tests PASS. If the edge-id assert RAISES, the shared rekey wiring is wrong (degrades_to was re-keyed separately from same_entity). If `validate_kg` reports `[ref]`, a Dharok's id didn't import — check it resolves in `item_dictionary.json`.

- [ ] **Step 7: Commit (graph + wiring together)**

```bash
git add kg_ingest/assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_degrade_paths_in_graph.py
git commit -m "feat(kg): wire build_degrade_paths (shared item-src rekey); regenerate graph with degrades_to"
```

---

### Task 5: Degradation competency question

**Files:**
- Modify: `kg/competency_questions.json`
- Modify: `tests/kg_ingest/test_competency_questions.py`

**Interfaces:**
- Consumes: the committed KG (Task 4) + `degrades_to`/`same_entity` edges.

- [ ] **Step 1: Add the CQ record to `kg/competency_questions.json` (red-first via unknown method)**

Append to the `records` array (after the last record — note the leading comma):
```json
    ,{ "id": "cq-ring-of-dueling-destroyed",
      "question": "Is a Ring of dueling destroyed when its last charge is used?",
      "method": "is_destroyed", "target": "item:ring-of-dueling", "expect_min": 1 }
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL — the runner has no `is_destroyed` branch, so it raises `AssertionError: unknown method 'is_destroyed'`.

- [ ] **Step 3: Add the runner method + dispatch branch**

In `tests/kg_ingest/test_competency_questions.py`, add a helper next to `_members`/`_family`/`_recipe_materials`:
```python
def _is_destroyed(store, target):
    # variants of the page (same_entity in-edges) that have an outgoing degrades_to with dst=None
    variants = {e.src for e in store.edges if e.type is EdgeType.SAME_ENTITY and e.dst == target}
    return {e.src for e in store.edges
            if e.type is EdgeType.DEGRADES_TO and e.dst is None and e.src in variants}
```
And add a branch to the method dispatch in `test_all_competency_questions_pass` (before the final `else: raise`):
```python
        elif cq["method"] == "is_destroyed":
            answer = _is_destroyed(store, cq["target"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS — Ring of dueling's `(1)` variant (item:2566) bridges to `item:ring-of-dueling` and has a `degrades_to` with `dst=None`, so the answer set is `{item:2566}` (size 1 ≥ expect_min 1).

- [ ] **Step 5: Final full-suite gate**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 6: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): competency question — Ring of dueling destroyed-on-depletion"
```

---

## Self-Review

**Spec coverage:** §2 model + schema → Task 1; §3 degrades_to model (3 terminals, per-step) → Task 2; §4 data + verifier → Task 3; §5 builder + shared item-src rekey + Dharok's auto-import → Tasks 2/4; §6 success + the shared-rekey no-collision test → Task 4; §6 CQ → Task 5. Deferred items (§7/§8) correctly absent.

**Placeholder scan:** none — all code/commands concrete; degrade ids + orderings + source tokens are the wiki-sourced real values (owner verifies), not placeholders.

**Type consistency:** `build_degrade_paths(records)` signature consistent (Tasks 2/4); `EdgeType.DEGRADES_TO`, `data.trigger`/`data.terminal`, `sequence`/`terminal`/`terminal_item` record keys, and the `item:<id>` ids consistent across Tasks 2/3/4/5; the assemble block names (`dg_edges`/`i_edges`/`item_edges`/`referenced_all`) match the slice-2 wiring it edits.
