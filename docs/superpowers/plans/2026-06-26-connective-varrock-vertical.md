# Connective Varrock Vertical (acquisition spine) — Slice 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the containment/economic spine (`place`▸`npc`▸`shop`▸item) for Varrock so the planner can answer "where/how do I acquire item X" — from the owner-authored `data/map/varrock.json`.

**Architecture:** Flip `npc`/`shop` (+ `located_in`/`operates`/`sells`) live; a new builder `kg_ingest/builders/map_varrock.py` reads `varrock.json`, emits place/npc/shop nodes + `located_in`/`operates`/`sells`/`same_entity` edges, resolves `item_name`→`item_id` against `item_dictionary`, and maps the 7 conditional sells to `cond_group`s reusing the existing `QUEST`/`ACHIEVEMENT_DIARY` atoms. These edges are place/npc/shop-`src` (NOT item-`src`), so they re-key in their own call (no shared-rekey entanglement). Design spec: `docs/superpowers/specs/2026-06-26-connective-varrock-vertical-design.md`.

**Tech Stack:** Python 3.14 (`./venv/bin/python`), committed JSON, `pytest`. No new dependencies.

## Global Constraints

- Run everything via `./venv/bin/python` (Python 3.14). (If a focused `pytest` run hangs unusually long, retry once — transient machine load.)
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run produces identical bytes.
- **Gates stay green:** `./venv/bin/python data/validate_kg.py` exit 0; `./venv/bin/python data/validate_cost.py` exit 0 (NO price/currency tokens in the graph — pricing deferred); golden + slice-1..5 tests pass; full `pytest` green except the 4 pre-existing `tests/drop_rates/` collection errors.
- **Flip reserved → live (not additive-new):** `npc`/`shop` nodes + `located_in`/`operates`/`sells` edges are already in `kg/schema.json` as `reserved`. Flip to `live`; `place` + `located_in` + `same_entity` are already declared. The `model enums ⊆ schema` invariant must stay green; update any locked-set guard test.
- **Pricing deferred:** the `sells` edge carries `{noted?, source_token}` only — NO `price_each`/`qty`/`currency` (those trip `validate_cost`; pricing is the cost layer's job).
- **Never fabricate item ids:** the builder resolves `item_name`→`item_id` against `item_dictionary` (exact name/page match, prefer `is_canonical`); on no/ambiguous match it returns `None` and the sells edge is **skipped** — `verify_map.py` lists every unresolved name (never silently wrong). Owner editorial review is the human gate.
- **`Node(id, kind, name, slug, data)`**; **`Edge(id, type, src, dst, cond_group, data)`**; **`ConditionAtom(atom_type, ref_node=None, threshold=None, qty=None, data)`**; **`ConditionGroup(id, op, parent, children)`**. Helpers: `item_id(n)`→`f"item:{int(n)}"`, `slugify(s)`, `_stable_hash`. Edge band `0xE0000000`, group band `0xD0000000`.
- **Concrete ids (verified present):** `quest:what-lies-below`, `diary:varrock:{easy,medium,hard,elite}`, `region:varrock`, `region:grand-exchange`; Battlestaff = item `1391`.

---

### Task 1: Flip `npc`/`shop` + `located_in`/`operates`/`sells` live

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py` (`NodeKind`, `EdgeType`)
- Modify: `kg/schema.json`
- Test: `tests/engine/test_kg_model.py`

**Interfaces:**
- Produces: `NodeKind.PLACE`/`NPC`/`SHOP`, `EdgeType.OPERATES`/`SELLS` (`LOCATED_IN` exists) — consumed by Task 2/4.

- [ ] **Step 1: Write the failing test**

Add to `tests/engine/test_kg_model.py`:
```python
def test_connective_kinds_live():
    from osrs_planner.engine.kg.model import NodeKind, EdgeType
    assert NodeKind.PLACE.value == "place" and NodeKind.NPC.value == "npc" and NodeKind.SHOP.value == "shop"
    assert EdgeType.OPERATES.value == "operates" and EdgeType.SELLS.value == "sells"
    assert EdgeType.LOCATED_IN.value == "located_in"
    import json, pathlib
    s = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    for nk in ("npc", "shop", "place"):
        assert s["node_kinds"][nk]["status"] == "live", nk
    for ek in ("located_in", "operates", "sells"):
        assert s["edge_kinds"][ek]["status"] == "live", ek
    assert s["edge_kinds"]["operates"]["domain"] == ["npc"] and s["edge_kinds"]["operates"]["range"] == ["shop"]
    assert s["edge_kinds"]["sells"]["domain"] == ["shop"] and s["edge_kinds"]["sells"]["range"] == ["item"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py::test_connective_kinds_live -v`
Expected: FAIL — `AttributeError: PLACE` / status `reserved`.

- [ ] **Step 3: Add the enum members**

In `src/osrs_planner/engine/kg/model.py`, add to `class NodeKind`:
```python
    PLACE = "place"                    # recursive containment node (geometry = chunk-set; supersedes legacy region)
    NPC = "npc"                        # non-combat character (shopkeeper, ruler, quest-giver)
    SHOP = "shop"                      # store with stock
```
and to `class EdgeType` (after `LOCATED_IN` / near it):
```python
    OPERATES = "operates"              # npc -> shop
    SELLS = "sells"                    # shop -> item (cond_group = a diary/quest gate)
```

- [ ] **Step 4: Flip the schema entries live + fix data_keys**

In `kg/schema.json`: set `status` to `"live"` on `node_kinds.npc`, `node_kinds.shop`, `edge_kinds.located_in`, `edge_kinds.operates`, `edge_kinds.sells`. Set the `data_keys` to match what the builder emits:
- `node_kinds.place.data_keys` → `["place_type", "ruled_by", "faction", "aliases", "chunks", "facility_flags", "coordinate_fields"]` (add `ruled_by`, `faction`).
- `node_kinds.npc.data_keys` → `["role", "aliases"]`.
- `node_kinds.shop.data_keys` → `["operator", "shop_type", "aliases"]`.
Do not change any domain/range.

- [ ] **Step 5: Update locked-set guards + run**

Run `./venv/bin/python -m pytest tests/engine/test_kg_model.py tests/kg_ingest/test_validate_kg_schema.py -q`. If a locked-set guard fails (NodeKind/EdgeType members == an explicit set), add `"place"`/`"npc"`/`"shop"` and `"operates"`/`"sells"` to the respective sets (strengthening). Re-run until green, INCLUDING `test_model_enums_are_all_declared_in_schema`.
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py kg/schema.json tests/engine/test_kg_model.py
git commit -m "feat(kg): flip place/npc/shop + located_in/operates/sells live"
```

---

### Task 2: `build_map` builder (resolver + conditional gates + emission)

**Files:**
- Create: `kg_ingest/builders/map_varrock.py`
- Test: `tests/kg_ingest/test_map_varrock_builder.py`

**Interfaces:**
- Produces:
  - `make_item_resolver(dict_records) -> Callable[[str], int | None]` — exact name/page match, prefer `is_canonical`; `None` on no/ambiguous match.
  - `build_map(map_data, resolve, region_ids) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]` — emits place/npc(operators)/shop nodes + `located_in`/`operates`/`sells`/`same_entity` edges + the conditional `cond_group`s; skips sells whose name doesn't resolve.
- Consumes: `NodeKind`/`EdgeType`/`AtomType`/`ConditionAtom`/`ConditionGroup`/`Op` (Task 1); `kg_ingest.ids.item_id`/`slugify`/`_stable_hash`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kg_ingest/test_map_varrock_builder.py`:
```python
from kg_ingest.builders.map_varrock import make_item_resolver, build_map
from osrs_planner.engine.kg.model import NodeKind, EdgeType, AtomType, Op

DICT = [
    {"item_id": 1391, "name": "Battlestaff", "page_name": "Battlestaff", "is_canonical": True, "is_variant": False, "members": True},
    {"item_id": 1381, "name": "Staff of air", "page_name": "Staff of air", "is_canonical": True, "is_variant": False, "members": False},
]
MAP = {
    "places": [
        {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": None},
        {"id": "place:misthalin", "place_type": "kingdom", "name": "Misthalin", "located_in": "place:gielinor", "ruled_by": "King Roald III"},
        {"id": "place:varrock", "place_type": "city", "name": "Varrock", "located_in": "place:misthalin"},
    ],
    "npcs": [
        {"id": "npc:zaff", "name": "Zaff", "role": "shopkeeper", "located_in": "place:varrock", "operates": ["shop:zaffs-superior-staffs"]},
        {"id": "npc:bystander", "name": "Bystander", "role": "citizen", "located_in": "place:varrock"},
    ],
    "shops": [
        {"id": "shop:zaffs-superior-staffs", "name": "Zaff's Superior Staffs", "shop_type": "magic",
         "located_in": "place:varrock", "operator": "npc:zaff", "currency": "coins",
         "sells": [
             {"item_name": "Staff of air", "item_id": None, "source_token": "elemental staves"},
             {"item_name": "Battlestaff", "item_id": None, "source_token": "after What Lies Below",
              "condition": {"type": "quest", "ref": "What Lies Below", "state": "in_progress"}},
             {"item_name": "Battlestaff (noted)", "item_id": None, "noted": True, "source_token": "discount",
              "condition": {"type": "achievement_diary", "ref": "Varrock Diary - Hard", "state": "completed"}},
             {"item_name": "Nonexistent Doohickey", "item_id": None, "source_token": "x"},
         ]},
    ],
}

def test_resolver_canonical_match_and_miss():
    r = make_item_resolver(DICT)
    assert r("Battlestaff") == 1391
    assert r("Nonexistent Doohickey") is None

def test_places_npcs_shops_and_located_in():
    nodes, edges, _ = build_map(MAP, make_item_resolver(DICT), {"region:varrock"})
    kinds = {n.id: n.kind for n in nodes}
    assert kinds["place:varrock"] is NodeKind.PLACE and kinds["shop:zaffs-superior-staffs"] is NodeKind.SHOP
    assert kinds["npc:zaff"] is NodeKind.NPC
    assert "npc:bystander" not in kinds          # only shop OPERATORS are emitted
    loc = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:varrock", "place:misthalin") in loc and ("shop:zaffs-superior-staffs", "place:varrock") in loc
    assert ("npc:zaff", "shop:zaffs-superior-staffs") in {(e.src, e.dst) for e in edges if e.type is EdgeType.OPERATES}
    # same_entity bridge for the place that has a legacy region node
    assert ("place:varrock", "region:varrock") in {(e.src, e.dst) for e in edges if e.type is EdgeType.SAME_ENTITY}

def test_sells_resolution_skip_and_conditional_gate():
    nodes, edges, groups = build_map(MAP, make_item_resolver(DICT), set())
    sells = {e.dst: e for e in edges if e.type is EdgeType.SELLS}
    assert "item:1391" in sells and "item:1381" in sells     # resolved
    assert all(e.src == "shop:zaffs-superior-staffs" for e in edges if e.type is EdgeType.SELLS)
    assert len([e for e in edges if e.type is EdgeType.SELLS]) == 3   # the unresolvable one is SKIPPED
    # the gated Battlestaff sell carries a cond_group -> a group with a QUEST atom
    gated = sells["item:1391"]
    assert gated.cond_group is not None
    g = groups[gated.cond_group]
    assert g.op is Op.AND and g.children[0].atom_type is AtomType.QUEST
    assert g.children[0].ref_node == "quest:what-lies-below" and g.children[0].data["state"] == "in_progress"
    # the diary-gated noted sell -> ACHIEVEMENT_DIARY atom, ref diary:varrock:hard
    diary = groups[[e for e in edges if e.type is EdgeType.SELLS and e.data.get("noted")][0].cond_group]
    assert diary.children[0].atom_type is AtomType.ACHIEVEMENT_DIARY and diary.children[0].ref_node == "diary:varrock:hard"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_map_varrock_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: kg_ingest.builders.map_varrock`.

- [ ] **Step 3: Write the builder**

Create `kg_ingest/builders/map_varrock.py`:
```python
"""build_map — the connective Varrock vertical (slice 6).

Reads data/map/varrock.json (owner-authored) and emits the containment/economic
spine: place/npc(operators)/shop nodes + located_in/operates/sells/same_entity
edges. Resolves item_name->item_id against item_dictionary (canonical match;
skips + the verifier reports unresolved). The 7 gated sells become a cond_group
on the sells edge, reusing the existing QUEST/ACHIEVEMENT_DIARY atoms. These edges
are place/npc/shop-src (NOT item-src) -> assemble re-keys them in their own call.
"""
from __future__ import annotations

from collections import defaultdict

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, item_id, slugify

_EDGE_BAND = 0xE0000000
_GROUP_BAND = 0xD0000000


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _gid(owner_id: str, slot: str) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner_id}#group#{slot}")


def make_item_resolver(dict_records):
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in dict_records:
        for key in (r.get("name"), r.get("page_name")):
            if key:
                by_name[key].append(r)

    def resolve(name: str):
        cands = by_name.get(name) or []
        if not cands:
            return None
        canon = [r for r in cands if r.get("is_canonical")] or cands
        ids = {r["item_id"] for r in canon}
        return next(iter(ids)) if len(ids) == 1 else None  # ambiguous -> None (flagged)

    return resolve


def _diary_ref_to_id(ref: str) -> str:
    region_part, tier = ref.rsplit(" - ", 1) if " - " in ref else (ref, "Easy")
    region = slugify(region_part.replace(" Diary", "").strip())
    return f"diary:{region}:{tier.strip().lower()}"


def _condition_atom(cond: dict):
    t, ref, state = cond.get("type"), cond.get("ref"), cond.get("state")
    if t == "quest":
        return ConditionAtom(atom_type=AtomType.QUEST, ref_node=f"quest:{slugify(ref)}", data={"state": state})
    if t == "achievement_diary":
        return ConditionAtom(atom_type=AtomType.ACHIEVEMENT_DIARY, ref_node=_diary_ref_to_id(ref), data={"state": state})
    return None  # unknown type -> caller skips + verifier flags


def _slug(node_id: str) -> str:
    return node_id.split(":", 1)[1]


def build_map(map_data, resolve, region_ids):
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    # places (the containment hierarchy) + same_entity bridge to a legacy region node
    for p in map_data["places"]:
        data = {k: p[k] for k in ("place_type", "ruled_by", "faction") if p.get(k) is not None}
        nodes.append(Node(id=p["id"], kind=NodeKind.PLACE, name=p["name"], slug=_slug(p["id"]), data=data))
        if p.get("located_in"):
            edges.append(Edge(id=_edge_id(p["id"], "located_in"), type=EdgeType.LOCATED_IN,
                              src=p["id"], dst=p["located_in"], cond_group=None, data={}))
        region = f"region:{_slug(p['id'])}"
        if region in region_ids:
            edges.append(Edge(id=_edge_id(p["id"], "same_entity"), type=EdgeType.SAME_ENTITY,
                              src=p["id"], dst=region, cond_group=None, data={}))

    # npcs: only the shop operators
    npc_by_id = {n["id"]: n for n in map_data["npcs"]}
    for nid in sorted({sh["operator"] for sh in map_data["shops"] if sh.get("operator")}):
        n = npc_by_id[nid]
        nodes.append(Node(id=nid, kind=NodeKind.NPC, name=n["name"], slug=_slug(nid),
                          data={"role": n.get("role")}))
        if n.get("located_in"):
            edges.append(Edge(id=_edge_id(nid, "located_in"), type=EdgeType.LOCATED_IN,
                              src=nid, dst=n["located_in"], cond_group=None, data={}))
        for shid in n.get("operates", []):
            edges.append(Edge(id=_edge_id(nid, f"operates#{shid}"), type=EdgeType.OPERATES,
                              src=nid, dst=shid, cond_group=None, data={}))

    # shops + sells (item resolution + conditional gates)
    for sh in map_data["shops"]:
        nodes.append(Node(id=sh["id"], kind=NodeKind.SHOP, name=sh["name"], slug=_slug(sh["id"]),
                          data={"operator": sh.get("operator"), "shop_type": sh.get("shop_type")}))
        if sh.get("located_in"):
            edges.append(Edge(id=_edge_id(sh["id"], "located_in"), type=EdgeType.LOCATED_IN,
                              src=sh["id"], dst=sh["located_in"], cond_group=None, data={}))
        for i, offer in enumerate(sh.get("sells", [])):
            iid = resolve(offer["item_name"])
            if iid is None:
                continue  # unresolved -> skipped; verify_map.py reports it
            cg = None
            if offer.get("condition"):
                atom = _condition_atom(offer["condition"])
                if atom is None:
                    continue  # unknown condition type -> skipped; verifier flags
                gid = _gid(sh["id"], f"sell{i}")
                groups[gid] = ConditionGroup(id=gid, op=Op.AND, parent=None, children=[atom])
                cg = gid
            data = {"source_token": offer.get("source_token")}
            if offer.get("noted"):
                data["noted"] = True
            edges.append(Edge(id=_edge_id(sh["id"], f"sell#{i}"), type=EdgeType.SELLS,
                              src=sh["id"], dst=item_id(iid), cond_group=cg, data=data))

    return nodes, edges, groups
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_map_varrock_builder.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/map_varrock.py tests/kg_ingest/test_map_varrock_builder.py
git commit -m "feat(kg): build_map — Varrock containment spine + item resolution + conditional sells"
```

---

### Task 3: `verify_map.py` (structural + resolution report)

**Files:**
- Create: `data/verify_map.py`
- Test: `tests/kg_ingest/test_verify_map.py`

**Interfaces:**
- Produces: a CLI verifier (exit 0/1) gating `data/map/varrock.json` + reporting item resolution.

- [ ] **Step 1: Write the failing verifier test**

Create `tests/kg_ingest/test_verify_map.py`:
```python
import os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_verifier_passes_on_committed_map():
    r = subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_map.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MAP VERIFICATION PASSED" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_map.py -v`
Expected: FAIL — `verify_map.py` does not exist.

- [ ] **Step 3: Write the verifier**

Create `data/verify_map.py`:
```python
#!/usr/bin/env python3
"""Source-grounding gate for data/map/varrock.json (the connective vertical).

Reuses the builder's item resolver (no drift). Checks: every located_in target is a
place present in the file; every shop.operator is a present npc AND reciprocally in
that npc's operates[]; every sells.item_name resolves in item_dictionary (the
RESOLUTION REPORT lists any that don't); every condition has type in
{quest, achievement_diary} + a ref resolving to an existing quest/diary node in the
committed graph + a source_token; slug uniqueness. Exits non-zero on any violation.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                        # for kg_ingest.*
sys.path.insert(0, os.path.join(ROOT, "src"))   # for osrs_planner.* (imported by the builder)
from kg_ingest.builders.map_varrock import make_item_resolver, _condition_atom  # noqa: E402

MAP = os.path.join(ROOT, "data", "map", "varrock.json")
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
NODES = os.path.join(ROOT, "kg", "nodes.json")


def main() -> int:
    errors: list[str] = []
    unresolved: list[str] = []
    with open(MAP, encoding="utf-8") as f:
        m = json.load(f)
    resolve = make_item_resolver(json.load(open(DICT, encoding="utf-8"))["records"])
    graph_ids = {n["id"] for n in json.load(open(NODES, encoding="utf-8"))}

    place_ids = {p["id"] for p in m["places"]}
    npc_by_id = {n["id"]: n for n in m["npcs"]}
    shop_ids = {s["id"] for s in m["shops"]}
    seen: set[str] = set()
    for coll in ("places", "npcs", "shops"):
        for x in m[coll]:
            if x["id"] in seen:
                errors.append(f"[slug] duplicate id {x['id']!r}")
            seen.add(x["id"])
            li = x.get("located_in")
            if li is not None and li not in place_ids:
                errors.append(f"[located_in] {x['id']!r} -> {li!r} not a place in the file")

    for sh in m["shops"]:
        op = sh.get("operator")
        if op:
            if op not in npc_by_id:
                errors.append(f"[operator] shop {sh['id']!r} operator {op!r} not an npc in the file")
            elif sh["id"] not in (npc_by_id[op].get("operates") or []):
                errors.append(f"[operates] {op!r} does not reciprocally operate {sh['id']!r}")
        for offer in sh.get("sells", []):
            name = offer.get("item_name")
            if resolve(name) is None:
                unresolved.append(f"{sh['id']}: {name!r}")
            cond = offer.get("condition")
            if cond:
                if not cond.get("source_token") and not offer.get("source_token"):
                    errors.append(f"[source] gated sell {name!r} in {sh['id']!r} missing source_token")
                atom = _condition_atom(cond)
                if atom is None:
                    errors.append(f"[condition] {name!r} in {sh['id']!r} bad condition type {cond.get('type')!r}")
                elif atom.ref_node not in graph_ids:
                    errors.append(f"[ref] condition ref {atom.ref_node!r} ({name!r}) not a node in the committed graph")

    if unresolved:
        errors.append(f"[resolve] {len(unresolved)} sells item name(s) did not resolve in item_dictionary")
    if errors:
        print(f"MAP VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        if unresolved:
            print("  unresolved item names:")
            for u in unresolved[:40]:
                print("    -", u)
        return 1
    print("MAP VERIFICATION PASSED — Varrock map source-grounded.")
    print(f"  places: {len(place_ids)}  npcs: {len(npc_by_id)}  shops: {len(shop_ids)}  sells resolved: all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test + verifier; resolve any unresolved names**

Run: `./venv/bin/python data/verify_map.py` then `./venv/bin/python -m pytest tests/kg_ingest/test_verify_map.py -v`
Expected: `MAP VERIFICATION PASSED`, exit 0. **If it reports unresolved item names or `[ref]`/`[operates]` violations:** do NOT fabricate ids. List the unresolved names and surface them for owner review — the fix is to correct the `item_name` in `varrock.json` (owner-authored, editorial) so it matches an `item_dictionary` page, OR confirm the item is legitimately absent. Re-run until the committed data passes. (Expected resolvable from the canonical names; a handful like "Staff" vs "Magic staff" may need the exact page name.)

- [ ] **Step 5: Commit**

```bash
git add data/verify_map.py tests/kg_ingest/test_verify_map.py
git commit -m "data(kg): verify_map gate (located_in/operates reciprocity, condition refs, item resolution report)"
```

---

### Task 4: Wire into `assemble.py` (own rekey, before reference collection) + regenerate

**Files:**
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_map_in_graph.py`

**Interfaces:**
- Consumes: `build_map`/`make_item_resolver` (Task 2), `data/map/varrock.json`, existing rekey/region nodes.

- [ ] **Step 1: Write the failing integration test**

Create `tests/kg_ingest/test_map_in_graph.py`:
```python
import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType, NodeKind

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_varrock_acquisition_spine():
    s = JsonKGStore.from_dir(KG)
    assert s.node("place:varrock").kind is NodeKind.PLACE
    assert s.node("shop:zaffs-superior-staffs").kind is NodeKind.SHOP
    # containment: Varrock -> Misthalin -> Gielinor
    loc = {(e.src, e.dst) for e in s.edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:varrock", "place:misthalin") in loc and ("place:misthalin", "place:gielinor") in loc
    # acquisition path: battlestaff <- sells <- Zaff's shop <- operates <- Zaff ; shop located_in Varrock
    assert ("npc:zaff", "shop:zaffs-superior-staffs") in {(e.src, e.dst) for e in s.edges if e.type is EdgeType.OPERATES}
    sells = [e for e in s.edges if e.type is EdgeType.SELLS and e.dst == "item:1391"]
    assert sells and sells[0].src == "shop:zaffs-superior-staffs"
    assert s.node("item:1391") is not None        # battlestaff auto-imported
    # the gated offer carries a cond_group resolvable in the graph's groups
    gated = [e for e in sells if e.cond_group is not None]
    assert gated, "expected a What-Lies-Below-gated battlestaff sell"

def test_place_region_bridge_and_unique_ids():
    s = JsonKGStore.from_dir(KG)
    assert ("place:varrock", "region:varrock") in {(e.src, e.dst) for e in s.edges if e.type is EdgeType.SAME_ENTITY}
    ids = [e.id for e in s.edges]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_map_in_graph.py -v`
Expected: FAIL — no place/shop nodes / sells edges yet.

- [ ] **Step 3: Add the loader + import in `assemble.py`**

Near the other `_load_*` helpers, add:
```python
VARROCK_MAP_PATH = Path(__file__).resolve().parents[1] / "data" / "map" / "varrock.json"


def _load_varrock_map() -> dict | None:
    if not VARROCK_MAP_PATH.exists():
        return None
    return json.loads(VARROCK_MAP_PATH.read_text())
```
And add the builder import with the others:
```python
from kg_ingest.builders.map_varrock import build_map, make_item_resolver
```

- [ ] **Step 4: Build the map BEFORE the reference collection, with its own rekey**

In `assemble.assemble()`, find the two lines that build `_degrade_nodes, dg_edges = build_degrade_paths(...)` and `_repair_nodes, rp_edges = build_repairs(...)`, immediately followed by `referenced_all = _collect_referenced_ids(edges + dg_edges + rp_edges, groups)`. Insert the map build + its own rekey BETWEEN the `build_repairs(...)` line and the `referenced_all = ...` line:
```python
    # Connective layer (Varrock): place/npc/shop + located_in/operates/sells/same_entity.
    # These edges are place/npc/shop-src (NOT item-src), so they re-key in their OWN call
    # (the same_entity it emits is place-src, so it cannot collide with build_items' item-src
    # same_entity). Build BEFORE the reference collection so resolved sells dsts auto-import.
    # region nodes are minted by build_content_nodes (content_nodes, already built above), so
    # the bridge only targets places that have a real legacy region node.
    map_nodes: list[Node] = []
    _map = _load_varrock_map()
    if _map is not None:
        map_region_ids = {n.id for n in content_nodes if n.id.startswith("region:")}
        map_nodes, map_edges, map_groups = build_map(
            _map, make_item_resolver(_load_item_dict_records()), map_region_ids)
        map_nodes, map_edges, map_groups = rekey(map_nodes, map_edges, map_groups)
        edges = edges + map_edges
        groups.update(map_groups)
        owned_ids = owned_ids | {n.id for n in map_nodes}
```
(`content_nodes` is in scope — it's assigned earlier in `assemble()` from `build_content_nodes`, the sole source of `region:` nodes. The `referenced_all = _collect_referenced_ids(edges + dg_edges + rp_edges, groups)` line that follows is unchanged — `edges` now already includes `map_edges`, so the resolved sells item dsts are collected and `build_items` auto-imports them.)

Then add `map_nodes` to the `dedup_nodes(...)` call (after `i_nodes`/`eqb_nodes`):
```python
    nodes = dedup_nodes(
        q_nodes + g_nodes + cg_nodes + d_nodes + dg_nodes + content_nodes + r_nodes + i_nodes + eqb_nodes + map_nodes + s_nodes
    )
```
(The `referenced_all = _collect_referenced_ids(edges + dg_edges + rp_edges, groups)` line is unchanged — `edges` now already includes `map_edges`, so the resolved sells item dsts are collected and `build_items` auto-imports them.)

- [ ] **Step 5: Regenerate the committed graph**

Run: `./venv/bin/python -m kg_ingest.assemble`
Expected: writes `kg/*.json` without error.

- [ ] **Step 6: Verify byte-stability, validators, golden, integration**

Run:
```bash
./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/   # second run: NO change
./venv/bin/python data/validate_kg.py            # exit 0 (located_in/operates/sells clean; cond_groups well-formed)
./venv/bin/python data/validate_cost.py          # exit 0 (no price/currency tokens)
./venv/bin/python data/verify_map.py             # exit 0
./venv/bin/python -m pytest tests/kg_ingest/test_golden_set.py tests/kg_ingest/test_items_in_graph.py tests/kg_ingest/test_equipment_bonuses_in_graph.py tests/kg_ingest/test_map_in_graph.py -q
```
Expected: assemble idempotent; validators exit 0; golden + slice-5 + new integration tests PASS. If `validate_kg` reports a `[ref]` on a `located_in`/`sells`/`same_entity` dst, that dst node is missing — check the map build ran before the reference collection (sells items) and that `map_region_ids` only includes existing region nodes (same_entity). If the edge-id assert raises, a map owner collided across rekey calls (shouldn't — map owners are place/npc/shop, distinct from item/recipe).

- [ ] **Step 7: Commit (graph + wiring together)**

```bash
git add kg_ingest/assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_map_in_graph.py
git commit -m "feat(kg): wire build_map (Varrock connective spine, own rekey); regenerate graph"
```

---

### Task 5: Acquisition competency question

**Files:**
- Modify: `kg/competency_questions.json`
- Modify: `tests/kg_ingest/test_competency_questions.py`

**Interfaces:**
- Consumes: the committed KG (Task 4) + `sells` edges.

- [ ] **Step 1: Add the CQ record (red-first via unknown method)**

Append to the `records` array (leading comma):
```json
    ,{ "id": "cq-battlestaff-sold-by",
      "question": "Where can I buy a battlestaff?",
      "method": "sold_by", "target": "item:1391", "expect_min": 1 }
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL — `unknown method 'sold_by'`.

- [ ] **Step 3: Add the runner method + dispatch branch**

In `tests/kg_ingest/test_competency_questions.py`, add a helper next to the others:
```python
def _sold_by(store, target):
    # the set of shops with a sells edge to the target item
    return {e.src for e in store.edges if e.type is EdgeType.SELLS and e.dst == target}
```
And a dispatch branch (before the final `else: raise`):
```python
        elif cq["method"] == "sold_by":
            answer = _sold_by(store, cq["target"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS — `item:1391` has a `sells` in-edge from `shop:zaffs-superior-staffs` (size ≥ 1).

- [ ] **Step 5: Final full-suite gate**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 6: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): competency question — where can I buy a battlestaff"
```

---

## Self-Review

**Spec coverage:** §2 model flip → Task 1; §3 nodes/edges → Task 2; §4 conditional gates → Task 2 (`_condition_atom`); §5 builder + own-rekey wiring + item resolution → Tasks 2/4; §6 verifier → Task 3; §7 success + CQ → Tasks 4/5. Deferred items (§8) correctly absent.

**Placeholder scan:** the only prose-flagged spots are Task 3 Step 4 ("surface unresolved names for owner review") and Task 4 Step 4's `map_region_ids` note — both are concrete instructions (don't fabricate ids; bridge only existing region nodes), not deferred work. Real ids (1391, quest:what-lies-below, diary:varrock:hard) are the verified values.

**Type consistency:** `make_item_resolver(dict_records) -> resolve`, `build_map(map_data, resolve, region_ids) -> (nodes, edges, groups)`, `_condition_atom(cond)` consistent (Tasks 2/3/4); `Node`/`Edge`/`ConditionAtom`/`ConditionGroup` signatures match the real dataclasses; the `place:`/`npc:`/`shop:` ids, `EdgeType.LOCATED_IN`/`OPERATES`/`SELLS`/`SAME_ENTITY`, and `item:1391` consistent across tasks; the assemble edit (`map_nodes`/`map_edges`/`map_groups`, own rekey, dedup) matches the existing wiring it extends.
