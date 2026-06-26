# Equipment Bonuses (`equipment_bonuses` + `has_bonuses`) — Slice 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the combat-stat facet to equippable items — a reified `equipment_bonuses` node per equippable item-variant + a `has_bonuses` edge (`item → equipment_bonuses`) — for the ~86 equippable item-variant nodes already in the graph.

**Architecture:** Flip the reserved `equipment_bonuses` node + `has_bonuses` edge live; a new builder `kg_ingest/builders/equipment_bonuses.py` reads the existing committed `data/items_equipment.json`, applies a **selection rule** (canonical page → drops beta; prefer `stat_variant_index 0`) to pick one record per item, and emits the facet nodes + edges; `assemble.py` runs it after `build_items` (bounded to existing nodes, no auto-import) and folds the item-`src` `has_bonuses` edges into the shared rekey. Design spec: `docs/superpowers/specs/2026-06-25-equipment-bonuses-design.md`.

**Tech Stack:** Python 3.14 (`./venv/bin/python`), committed JSON, `pytest`. No new dependencies.

## Global Constraints

- Run everything via `./venv/bin/python` (Python 3.14). (If a focused `pytest` run hangs unusually long, retry once — transient machine load.)
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run produces identical bytes.
- **Gates stay green:** `./venv/bin/python data/validate_kg.py` exit 0; `./venv/bin/python data/validate_cost.py` exit 0; golden (`tests/kg_ingest/test_golden_set.py`) + slice-1..4 tests (`test_items_in_graph.py`, `test_recipes_in_graph.py`, `test_degrade_paths_in_graph.py`, `test_repairs_in_graph.py`, `test_competency_questions.py`) pass; full `pytest` green except the 4 pre-existing `tests/drop_rates/` collection errors.
- **Flip reserved → live (not additive-new):** `equipment_bonuses` node + `has_bonuses` edge are already in `kg/schema.json` as `status: "reserved"`. This slice flips both to `"live"`. The `model-enum ⊆ schema` invariant must stay green; update any locked-set guard test (EdgeType/NodeKind members-match-schema) to include the two new members.
- **Pure transition edge:** `has_bonuses` carries NO `data` (`data={}`); the bonuses live on the node.
- **Selection rule (the crux):** the dataset has MULTIPLE records per `item_id` (stat-variants + `(beta)`-page duplicates). For each item pick ONE: prefer the record whose `page_name == item_dictionary` page (drops beta); among those prefer `stat_variant_index == 0`, then `None`, then lowest. Verified to resolve all 86 in-scope items with 0 beta leaks / 0 all-zero combat gear (audit 2026-06-25; e.g. Scythe slash 125 not the beta's 110; Dharok's def 45 not the empty variant_idx 1).
- **Bound scope:** emit only for item-variant nodes already in the graph (no auto-import). `has_bonuses` is item-`src` → joins the shared rekey (`i_edges + dg_edges + rp_edges + hb_edges`).
- **`Node`** fields = `(id, kind, name, slug, data)`; **`Edge`** = `(id, type, src, dst, cond_group, data)`. `item_id(n)` → `f"item:{int(n)}"`; `_stable_hash(text)` → md5 & `0x0FFFFFFF`.

---

### Task 1: Flip `equipment_bonuses` node + `has_bonuses` edge live

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py` (`NodeKind`, `EdgeType`)
- Modify: `kg/schema.json` (`node_kinds.equipment_bonuses`, `edge_kinds.has_bonuses`)
- Test: `tests/engine/test_kg_model.py`

**Interfaces:**
- Produces: `NodeKind.EQUIPMENT_BONUSES` (`"equipment_bonuses"`), `EdgeType.HAS_BONUSES` (`"has_bonuses"`) — consumed by Task 2's builder and Task 4's assemble.

- [ ] **Step 1: Write the failing test**

Add to `tests/engine/test_kg_model.py`:
```python
def test_equipment_bonuses_and_has_bonuses_are_live():
    from osrs_planner.engine.kg.model import NodeKind, EdgeType
    assert NodeKind.EQUIPMENT_BONUSES.value == "equipment_bonuses"
    assert EdgeType.HAS_BONUSES.value == "has_bonuses"
    import json, pathlib
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    assert schema["node_kinds"]["equipment_bonuses"]["status"] == "live"
    hb = schema["edge_kinds"]["has_bonuses"]
    assert hb["status"] == "live" and hb["domain"] == ["item"] and hb["range"] == ["equipment_bonuses"]
    assert hb["dst"] == "required" and hb["reified"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py::test_equipment_bonuses_and_has_bonuses_are_live -v`
Expected: FAIL — `AttributeError: EQUIPMENT_BONUSES` / status is `"reserved"`.

- [ ] **Step 3: Add the enum members**

In `src/osrs_planner/engine/kg/model.py`: add to `class NodeKind` (after the last live node kind):
```python
    EQUIPMENT_BONUSES = "equipment_bonuses"   # reified combat-stat facet of an equippable item-variant
```
and to `class EdgeType` (after `REPAIRS`):
```python
    HAS_BONUSES = "has_bonuses"               # item-variant -> its equipment_bonuses facet (item-src)
```

- [ ] **Step 4: Flip the schema entries live**

In `kg/schema.json`: in `node_kinds.equipment_bonuses`, change `"status": "reserved"` to `"status": "live"`. In `edge_kinds.has_bonuses`, change `"status": "reserved"` to `"status": "live"` and ensure the entry reads `"dst": "required"` and `"reified": false` (add/set these keys if absent; keep `"domain": ["item"]`, `"range": ["equipment_bonuses"]`).

- [ ] **Step 5: Update locked-set guard tests + run**

Run `./venv/bin/python -m pytest tests/engine/test_kg_model.py tests/kg_ingest/test_validate_kg_schema.py -q`. If a locked-set guard fails (a test asserting EdgeType/NodeKind members == an explicit set), add `"equipment_bonuses"` / `"has_bonuses"` to that set (strengthening, not weakening). Re-run until green, INCLUDING `test_model_enums_are_all_declared_in_schema`.
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py kg/schema.json tests/engine/test_kg_model.py
git commit -m "feat(kg): flip equipment_bonuses node + has_bonuses edge live"
```

---

### Task 2: `equipment_bonuses` builder + selection rule

**Files:**
- Create: `kg_ingest/builders/equipment_bonuses.py`
- Test: `tests/kg_ingest/test_equipment_bonuses_builder.py`

**Interfaces:**
- Produces:
  - `select_bonus_record(records: list[dict], canonical_page: str | None) -> dict` — pick one record per item (canonical page → drops beta; prefer `stat_variant_index 0`, then `None`, then lowest).
  - `build_equipment_bonuses(eq_records: list[dict], owned_item_ids: set[str], canonical_pages: dict[int, str]) -> tuple[list[Node], list[Edge], dict]` — for each `item_id` whose `item:<id>` is in `owned_item_ids`, emit one `equipment_bonuses:<id>` node (data = `{item_id, slot, stats, weapon?}`) + one `has_bonuses` edge (`item:<id> → equipment_bonuses:<id>`, item-`src`, `data={}`).
- Consumes: `NodeKind.EQUIPMENT_BONUSES`, `EdgeType.HAS_BONUSES` (Task 1); `kg_ingest.ids.item_id`/`_stable_hash`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kg_ingest/test_equipment_bonuses_builder.py`:
```python
from kg_ingest.builders.equipment_bonuses import select_bonus_record, build_equipment_bonuses
from osrs_planner.engine.kg.model import EdgeType, NodeKind

def _stats(**kw):
    base = {k: 0 for k in (
        "stab_attack_bonus","slash_attack_bonus","crush_attack_bonus","magic_attack_bonus","range_attack_bonus",
        "stab_defence_bonus","slash_defence_bonus","crush_defence_bonus","magic_defence_bonus","range_defence_bonus",
        "strength_bonus","ranged_strength_bonus","prayer_bonus","magic_damage_bonus")}
    base.update(kw); return base

SCYTHE = [
    {"item_id":22325,"item":"Scythe of vitur","page_name":"Scythe of vitur","slot":"2h","stat_variant_index":0,
     "stats":_stats(slash_attack_bonus=125,strength_bonus=75),"weapon":{"weapon_attack_speed":5,"weapon_attack_range":"1","combat_style":"Slash"}},
    {"item_id":22325,"item":"Scythe of vitur","page_name":"Scythe of vitur","slot":"2h","stat_variant_index":1,
     "stats":_stats(slash_attack_bonus=75),"weapon":{"weapon_attack_speed":5,"weapon_attack_range":"1","combat_style":"Slash"}},
    {"item_id":22325,"item":"Scythe of vitur","page_name":"Scythe of vitur (beta)","slot":"2h","stat_variant_index":None,
     "stats":_stats(slash_attack_bonus=110),"weapon":{"weapon_attack_speed":5,"weapon_attack_range":"1","combat_style":"Slash"}},
]
DHAROK = [
    {"item_id":4716,"item":"Dharok's helm","page_name":"Dharok's helm","slot":"head","stat_variant_index":0,"stats":_stats(stab_defence_bonus=45)},
    {"item_id":4716,"item":"Dharok's helm","page_name":"Dharok's helm","slot":"head","stat_variant_index":1,"stats":_stats()},
]

def test_select_drops_beta_and_prefers_variant_zero():
    assert select_bonus_record(SCYTHE, "Scythe of vitur")["stats"]["slash_attack_bonus"] == 125
    assert select_bonus_record(DHAROK, "Dharok's helm")["stats"]["stab_defence_bonus"] == 45

def test_build_emits_node_and_edge_per_owned_item():
    eq = SCYTHE + DHAROK
    owned = {"item:22325"}    # Dharok's NOT owned -> skipped
    canon = {22325:"Scythe of vitur", 4716:"Dharok's helm"}
    nodes, edges, groups = build_equipment_bonuses(eq, owned, canon)
    assert groups == {}
    assert [n.id for n in nodes] == ["equipment_bonuses:22325"]
    n = nodes[0]
    assert n.kind is NodeKind.EQUIPMENT_BONUSES
    assert n.data["stats"]["slash_attack_bonus"] == 125 and n.data["slot"] == "2h"
    assert n.data["weapon"]["combat_style"] == "Slash"
    assert len(edges) == 1
    e = edges[0]
    assert e.type is EdgeType.HAS_BONUSES and e.src == "item:22325" and e.dst == "equipment_bonuses:22325"
    assert e.data == {} and e.cond_group is None

def test_build_omits_weapon_block_for_armour():
    nodes, _, _ = build_equipment_bonuses(DHAROK, {"item:4716"}, {4716:"Dharok's helm"})
    assert "weapon" not in nodes[0].data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_equipment_bonuses_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: kg_ingest.builders.equipment_bonuses`.

- [ ] **Step 3: Write the builder**

Create `kg_ingest/builders/equipment_bonuses.py`:
```python
"""build_equipment_bonuses — reified combat-stat facet nodes + has_bonuses edges (slice 5).

Reads data/items_equipment.json. The dataset carries MULTIPLE records per item_id
(stat-variants + (beta)-page duplicates), so select_bonus_record picks the canonical
one (page == item_dictionary page, dropping beta; preferring stat_variant_index 0).
Bounded to items already in the graph (owned_item_ids) — no auto-import. has_bonuses
is ITEM-src; assemble re-keys it TOGETHER with same_entity/degrades_to/repairs.
"""
from __future__ import annotations

from collections import defaultdict

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, item_id

_EDGE_BAND = 0xD0000000  # equipment-bonuses builder-local edge ids (rekeyed in assemble)
_WEAPON_SLOTS = {"weapon", "2h"}


def _is_beta(page: str | None) -> bool:
    return "(beta)" in (page or "").lower()


def select_bonus_record(records: list[dict], canonical_page: str | None) -> dict:
    canon = [r for r in records if r.get("page_name") == canonical_page]
    pool = canon or [r for r in records if not _is_beta(r.get("page_name"))] or records

    def rank(r):
        vi = r.get("stat_variant_index")
        if vi == 0:
            return (0, 0)
        if vi is None:
            return (1, 0)
        return (2, vi)

    return sorted(pool, key=rank)[0]


def _edge_id(src_id: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#has_bonuses")


def build_equipment_bonuses(eq_records, owned_item_ids, canonical_pages):
    by_id: dict[int, list[dict]] = defaultdict(list)
    for r in eq_records:
        if r.get("item_id") is not None:
            by_id[r["item_id"]].append(r)

    nodes: list[Node] = []
    edges: list[Edge] = []
    for iid in sorted(by_id):
        src = item_id(iid)
        if src not in owned_item_ids:
            continue
        rec = select_bonus_record(by_id[iid], canonical_pages.get(iid))
        data = {"item_id": iid, "slot": rec.get("slot"), "stats": rec["stats"]}
        if rec.get("slot") in _WEAPON_SLOTS and rec.get("weapon"):
            data["weapon"] = rec["weapon"]
        bonus_id = f"equipment_bonuses:{iid}"
        nodes.append(Node(id=bonus_id, kind=NodeKind.EQUIPMENT_BONUSES,
                          name=f"{rec['item']} (equipment bonuses)",
                          slug=f"equipment-bonuses-{iid}", data=data))
        edges.append(Edge(id=_edge_id(src), type=EdgeType.HAS_BONUSES, src=src,
                          dst=bonus_id, cond_group=None, data={}))
    return nodes, edges, {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_equipment_bonuses_builder.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/equipment_bonuses.py tests/kg_ingest/test_equipment_bonuses_builder.py
git commit -m "feat(kg): build_equipment_bonuses + canonical-page selection rule"
```

---

### Task 3: `verify_equipment_bonuses.py` (the verifier with teeth)

**Files:**
- Create: `data/verify_equipment_bonuses.py`
- Test: `tests/kg_ingest/test_verify_equipment_bonuses.py`

**Interfaces:**
- Produces: a CLI verifier returning exit 0/1 that re-runs the selection for the in-scope items and gates the corruption classes + structure.

- [ ] **Step 1: Write the failing verifier test**

Create `tests/kg_ingest/test_verify_equipment_bonuses.py`:
```python
import os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_verifier_passes_on_committed_data():
    r = subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_equipment_bonuses.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "EQUIPMENT-BONUSES VERIFICATION PASSED" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_equipment_bonuses.py -v`
Expected: FAIL — `verify_equipment_bonuses.py` does not exist.

- [ ] **Step 3: Write the verifier**

Create `data/verify_equipment_bonuses.py`:
```python
#!/usr/bin/env python3
"""Source-grounding gate for the equipment-bonuses layer (data/items_equipment.json).

The dataset has multiple records per item_id (stat-variants + (beta) duplicates). For
each IN-SCOPE item (an equippable item-variant node already in kg/nodes.json), re-run
the selection rule and gate the corruption classes the 2026-06-25 audit found:
  - selected page is canonical (== item_dictionary page) and NOT a (beta) page;
  - exactly one record selected per item;
  - no all-zero stat block on a COMBAT slot (the empty-variant failure mode);
  - structural: 14 stat fields present + numeric; known slot; weapon block iff weapon slot.
Exits non-zero on any violation.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                        # for kg_ingest.* (run standalone: script dir is on path, ROOT is not)
sys.path.insert(0, os.path.join(ROOT, "src"))   # for osrs_planner.* (imported by the builder module)
from kg_ingest.builders.equipment_bonuses import select_bonus_record  # noqa: E402

DICT = os.path.join(ROOT, "data", "item_dictionary.json")
EQUIP = os.path.join(ROOT, "data", "items_equipment.json")
NODES = os.path.join(ROOT, "kg", "nodes.json")
STAT_FIELDS = {"stab_attack_bonus","slash_attack_bonus","crush_attack_bonus","magic_attack_bonus","range_attack_bonus",
               "stab_defence_bonus","slash_defence_bonus","crush_defence_bonus","magic_defence_bonus","range_defence_bonus",
               "strength_bonus","ranged_strength_bonus","prayer_bonus","magic_damage_bonus"}
COMBAT_SLOTS = {"weapon","2h","body","head","legs","shield","hands","feet","cape"}
WEAPON_SLOTS = {"weapon","2h"}
KNOWN_SLOTS = COMBAT_SLOTS | {"ring","neck","ammo"}


def main() -> int:
    errors: list[str] = []
    with open(DICT, encoding="utf-8") as f:
        id2page = {r["item_id"]: r["page_name"] for r in json.load(f)["records"]}
    with open(EQUIP, encoding="utf-8") as f:
        eq = json.load(f)["records"]
    with open(NODES, encoding="utf-8") as f:
        nodes = json.load(f)
    by_id: dict[int, list[dict]] = defaultdict(list)
    for r in eq:
        if r.get("item_id") is not None:
            by_id[r["item_id"]].append(r)
    eq_ids = set(by_id)
    in_scope = sorted({int(n["id"].split(":", 1)[1]) for n in nodes
                       if n["id"].startswith("item:") and n["id"].split(":", 1)[1].isdigit()
                       and int(n["id"].split(":", 1)[1]) in eq_ids})

    for iid in in_scope:
        rec = select_bonus_record(by_id[iid], id2page.get(iid))
        tag = f"item:{iid}"
        if iid not in id2page:
            errors.append(f"[item] {tag} not in item_dictionary")
        if "(beta)" in (rec.get("page_name") or "").lower():
            errors.append(f"[beta] {tag} selected a (beta) page {rec.get('page_name')!r}")
        elif iid in id2page and rec.get("page_name") != id2page[iid]:
            errors.append(f"[page] {tag} selected page {rec.get('page_name')!r} != canonical {id2page[iid]!r}")
        stats = rec.get("stats") or {}
        missing = STAT_FIELDS - set(stats)
        if missing:
            errors.append(f"[stats] {tag} missing stat fields {sorted(missing)}")
        elif any(not isinstance(stats[k], (int, float)) for k in STAT_FIELDS):
            errors.append(f"[stats] {tag} has non-numeric stat value")
        elif rec.get("slot") in COMBAT_SLOTS and all(stats[k] == 0 for k in STAT_FIELDS):
            errors.append(f"[zero] {tag} all-zero stat block on combat slot {rec.get('slot')!r}")
        slot = rec.get("slot")
        if slot not in KNOWN_SLOTS:
            errors.append(f"[slot] {tag} unknown slot {slot!r}")
        if (slot in WEAPON_SLOTS) != bool(rec.get("weapon")):
            errors.append(f"[weapon] {tag} slot={slot!r} but weapon-block-present={bool(rec.get('weapon'))}")

    if errors:
        print(f"EQUIPMENT-BONUSES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        return 1
    print("EQUIPMENT-BONUSES VERIFICATION PASSED — all in-scope bonuses source-grounded.")
    print(f"  in-scope equippable items: {len(in_scope)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test + verifier**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_equipment_bonuses.py -v && ./venv/bin/python data/verify_equipment_bonuses.py`
Expected: PASS; verifier prints `EQUIPMENT-BONUSES VERIFICATION PASSED`, exit 0. If `[weapon]` fires, the iff-rule is too strict for some in-scope item — inspect that item's record; if a weapon-slot item legitimately lacks a weapon block (or vice versa), relax that single check to one-directional (`weapon block present implies weapon slot`) and note it. If `[zero]`/`[page]`/`[beta]` fires, the selection rule didn't resolve an item — STOP and report (do not loosen the gate).

- [ ] **Step 5: Commit**

```bash
git add data/verify_equipment_bonuses.py tests/kg_ingest/test_verify_equipment_bonuses.py
git commit -m "data(kg): verify_equipment_bonuses gate (canonical page + no all-zero combat gear)"
```

---

### Task 4: Wire into `assemble.py` (4th item-`src` edge) + regenerate

**Files:**
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_equipment_bonuses_in_graph.py`

**Interfaces:**
- Consumes: `build_equipment_bonuses` (Task 2), `data/items_equipment.json`, `data/item_dictionary.json`, the slice-4 shared-rekey wiring (existing).

- [ ] **Step 1: Write the failing integration test**

Create `tests/kg_ingest/test_equipment_bonuses_in_graph.py`:
```python
import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType, NodeKind

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def _bonus_node_for(s, item_node):
    es = [e for e in s.edges if e.type is EdgeType.HAS_BONUSES and e.src == item_node]
    assert len(es) == 1
    return s.node(es[0].dst)

def test_scythe_and_dharoks_bonuses_resolve_correctly():
    # the 2026-06-25 audit regression guards: selection must pick the CANONICAL values.
    s = JsonKGStore.from_dir(KG)
    scythe = _bonus_node_for(s, "item:22325")
    assert scythe.kind is NodeKind.EQUIPMENT_BONUSES
    assert scythe.data["stats"]["slash_attack_bonus"] == 125    # canonical, not the beta's 110
    assert scythe.data["weapon"]["combat_style"] == "Slash"
    dharoks = _bonus_node_for(s, "item:4716")
    assert dharoks.data["stats"]["stab_defence_bonus"] == 45    # variant_idx 0, not the empty variant_idx 1

def test_bonuses_attach_to_variants_not_pages_and_ids_unique():
    s = JsonKGStore.from_dir(KG)
    # page node must NOT carry has_bonuses (only numeric variant ids do)
    assert not any(e.type is EdgeType.HAS_BONUSES and e.src == "item:scythe-of-vitur" for e in s.edges)
    ids = [e.id for e in s.edges]
    assert len(ids) == len(set(ids)), "duplicate edge id with four item-src edge types present"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_equipment_bonuses_in_graph.py -v`
Expected: FAIL — no `has_bonuses` edges / `equipment_bonuses` nodes yet.

- [ ] **Step 3: Add the loaders + import in `assemble.py`**

Near the other `_load_*` helpers (after `_load_repair_path_records`, ~line 274), add:
```python
ITEMS_EQUIPMENT_PATH = Path(__file__).resolve().parents[1] / "data" / "items_equipment.json"


def _load_equipment_records() -> list[dict]:
    if not ITEMS_EQUIPMENT_PATH.exists():
        return []
    return json.loads(ITEMS_EQUIPMENT_PATH.read_text())["records"]


def _load_canonical_item_pages() -> dict[int, str]:
    return {r["item_id"]: r["page_name"] for r in _load_item_dict_records()}
```
And add the builder import with the others (alphabetical, after `build_diary_goals` / before `build_goals`):
```python
from kg_ingest.builders.equipment_bonuses import build_equipment_bonuses
```

- [ ] **Step 4: Build the bonuses + extend the shared rekey**

In `kg_ingest/assemble.py`, the slice-4 block builds `i_nodes, i_edges = build_items(...)` then immediately runs the shared rekey `rekey(i_nodes, i_edges + dg_edges + rp_edges, {})`. Insert the bonuses build BETWEEN them, and add `hb_edges` to the rekey. Replace:
```python
    i_nodes, i_edges, _ = build_items(
        _load_item_dict_records(), _load_item_exemplars(), _load_item_families(),
        referenced_item_ids, owned_ids=frozenset(owned_ids),
    )
    # SHARED REKEY: same_entity (i_edges) + degrades_to (dg_edges) + repairs (rp_edges), all item-src,
    # in one call, so an item that is the src of multiple types gets distinct per-owner indices.
    i_nodes, item_edges, _ = rekey(i_nodes, i_edges + dg_edges + rp_edges, {})
```
with:
```python
    i_nodes, i_edges, _ = build_items(
        _load_item_dict_records(), _load_item_exemplars(), _load_item_families(),
        referenced_item_ids, owned_ids=frozenset(owned_ids),
    )
    # Equipment-bonuses facet: has_bonuses edges are the 4th ITEM-src family. Build AFTER
    # build_items (needs the owned item-variant ids; bounded to existing nodes, NO auto-import)
    # but BEFORE the shared rekey so hb_edges join it. eqb_nodes are new facet nodes (no rekey).
    _owned_item_ids = {x for x in (owned_ids | {n.id for n in i_nodes})
                       if x.startswith("item:") and x.split(":", 1)[1].isdigit()}
    eqb_nodes, hb_edges, _ = build_equipment_bonuses(
        _load_equipment_records(), _owned_item_ids, _load_canonical_item_pages())
    # SHARED REKEY: same_entity + degrades_to + repairs + has_bonuses, all item-src, in one call,
    # so an item that is the src of multiple types gets distinct per-owner indices.
    i_nodes, item_edges, _ = rekey(i_nodes, i_edges + dg_edges + rp_edges + hb_edges, {})
```
Then add `eqb_nodes` to the `dedup_nodes(...)` call (the `q_nodes + g_nodes + ... + i_nodes + s_nodes` list) — insert `+ eqb_nodes` right after `i_nodes`:
```python
    nodes = dedup_nodes(
        q_nodes + g_nodes + cg_nodes + d_nodes + dg_nodes + content_nodes + r_nodes + i_nodes + eqb_nodes + s_nodes
    )
```
(The global edge-id assert is unchanged — `item_edges` now includes `hb_edges`, so the backstop covers them.)

- [ ] **Step 5: Regenerate the committed graph**

Run: `./venv/bin/python -m kg_ingest.assemble`
Expected: writes `kg/*.json` without error (the edge-id assert passes — the shared rekey now covers four item-`src` edge types).

- [ ] **Step 6: Verify byte-stability, validators, golden, integration**

Run:
```bash
./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/   # second run: NO further change
./venv/bin/python data/validate_kg.py            # exit 0 (has_bonuses item->equipment_bonuses, dst required clean)
./venv/bin/python data/validate_cost.py          # exit 0
./venv/bin/python data/verify_equipment_bonuses.py   # exit 0
./venv/bin/python -m pytest tests/kg_ingest/test_golden_set.py tests/kg_ingest/test_items_in_graph.py tests/kg_ingest/test_degrade_paths_in_graph.py tests/kg_ingest/test_repairs_in_graph.py tests/kg_ingest/test_equipment_bonuses_in_graph.py -q
```
Expected: assemble idempotent; validators exit 0; golden + slice-1..4 + new integration tests PASS (Scythe slash 125, Dharok's def 45). Node count ≈ 658, edge count ≈ 953. If `validate_kg` reports a `has_bonuses` range error, an `equipment_bonuses` node didn't get added to `dedup_nodes` (check Step 4's node-list edit). If the edge-id assert RAISES, `hb_edges` were re-keyed separately instead of in the shared call.

- [ ] **Step 7: Commit (graph + wiring together)**

```bash
git add kg_ingest/assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_equipment_bonuses_in_graph.py
git commit -m "feat(kg): wire build_equipment_bonuses (4th item-src edge); regenerate graph with has_bonuses"
```

---

### Task 5: Equipment-bonus competency question

**Files:**
- Modify: `kg/competency_questions.json`
- Modify: `tests/kg_ingest/test_competency_questions.py`

**Interfaces:**
- Consumes: the committed KG (Task 4) + `has_bonuses` edges + `equipment_bonuses` nodes.

- [ ] **Step 1: Add the CQ record to `kg/competency_questions.json` (red-first via unknown method)**

Append to the `records` array (after the last record — note the leading comma):
```json
    ,{ "id": "cq-scythe-of-vitur-slash-bonus",
      "question": "What is the Scythe of vitur's slash attack bonus?",
      "method": "equipment_bonus", "target": "item:22325", "stat": "slash_attack_bonus", "expect": 125 }
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL — the runner has no `equipment_bonus` branch → `AssertionError: unknown method 'equipment_bonus'`.

- [ ] **Step 3: Add the runner method + dispatch branch**

In `tests/kg_ingest/test_competency_questions.py`, add a helper next to the others (`_members`/`_family`/`_recipe_materials`/`_is_destroyed`/`_is_repairable`):
```python
def _equipment_bonus(store, target, stat):
    for e in store.edges:
        if e.type is EdgeType.HAS_BONUSES and e.src == target:
            return store.node(e.dst).data["stats"].get(stat)
    return None
```
And add a branch in the method dispatch of `test_all_competency_questions_pass`. Because this CQ asserts an exact value (not a set size), give it its own assertion and `continue` so it skips the shared `expect_min` check (place it before the `else: raise`):
```python
        elif cq["method"] == "equipment_bonus":
            answer = _equipment_bonus(store, cq["target"], cq["stat"])
            assert answer == cq["expect"], f"{cq['id']}: {cq['stat']}={answer!r} != {cq['expect']!r}"
            continue
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS — `item:22325` has a `has_bonuses` edge to a node whose `stats.slash_attack_bonus == 125`.

- [ ] **Step 5: Final full-suite gate**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 6: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): competency question — Scythe of vitur slash attack bonus"
```

---

## Self-Review

**Spec coverage:** §2 model flip → Task 1; §3 node+edge model → Task 2; §4 data + selection rule → Task 2 (`select_bonus_record`); §5 verifier with teeth → Task 3; §6 builder + shared rekey (4th item-src) + bounded-no-auto-import → Tasks 2/4; §7 success + audit regression guards (Scythe 125 / Dharok's 45) + CQ → Tasks 4/5. Deferred items (§8) correctly absent.

**Placeholder scan:** none — all code/commands concrete; the selection rule, the stat-field set, and the audit values are the real verified values, not placeholders.

**Type consistency:** `select_bonus_record(records, canonical_page)` and `build_equipment_bonuses(eq_records, owned_item_ids, canonical_pages)` signatures consistent (Tasks 2/3/4); `NodeKind.EQUIPMENT_BONUSES`/`EdgeType.HAS_BONUSES`, the `equipment_bonuses:<id>` node id, the `item:<id>` src, and the `stats`/`slot`/`weapon` data keys consistent across Tasks 2/3/4/5; the assemble edit (`eqb_nodes`, `hb_edges`, `_owned_item_ids`, `i_edges + dg_edges + rp_edges + hb_edges`) matches the slice-4 wiring it extends; `Node(id, kind, name, slug, data)` / `Edge(id, type, src, dst, cond_group, data)` match the real dataclasses.
