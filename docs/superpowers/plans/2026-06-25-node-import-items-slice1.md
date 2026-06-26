# Node Import — Slice 1 (item nodes, two-level variant model) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import OSRS item nodes from the committed Wiki-Bucket dictionary into the KG as a two-level variant model (auto intra-page variants + curated cross-page families), introducing the first new v2 edge `same_entity`.

**Architecture:** A new pure builder `kg_ingest/builders/items.py` reads `data/item_dictionary.json` + two curated files and emits item page/variant/family nodes plus `same_entity` edges; `assemble.py` wires it in ahead of `build_supporting` (link-don't-merge handoff). The committed graph is regenerated and stays VIOLATION-clean + byte-stable; golden tests stay green. Design spec: `docs/superpowers/specs/2026-06-25-node-import-items-slice1-design.md`.

**Tech Stack:** Python 3.14 (`./venv/bin/python`), committed JSON data, `pytest`. No new dependencies.

## Global Constraints

- Run everything via `./venv/bin/python` (e.g. `./venv/bin/python -m pytest -q`). Python 3.14.
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run produces identical bytes.
- **Gates stay green:** `./venv/bin/python data/validate_kg.py` exit 0; `./venv/bin/python data/validate_cost.py` exit 0; golden tests (`tests/kg_ingest/test_golden_set.py`) pass; full `pytest` green except the 4 pre-existing `tests/drop_rates/` collection errors (`No module named 'data._toa_drop_rates'`).
- **Schema changes are additive only** (new edge/atom/kind), never a re-ingest. `same_entity` is already declared in `kg/schema.json` (status `reserved`).
- **Never fabricate.** Curated `item_node_families.json` is editorial: every record carries `source_url` + a verbatim `source_token`, and is owner-reviewed before merge.
- **Node ids:** variants `item:<numeric item_id>` (slug = the numeric id string, matching existing convention); page nodes `item:<slugify(page_name)>`; family nodes `item:<curated-family-slug>` (suffixed `-family`).
- Builders are pure; builder-local edge ids live in a disjoint band and are re-keyed to global ids by `assemble.rekey` (it re-indexes by edge `src`, discarding the local id value).

---

### Task 1: Add `EdgeType.SAME_ENTITY` + flip schema status

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py` (the `EdgeType` enum)
- Modify: `kg/schema.json` (`same_entity` status + `item` kind `data_keys`)
- Test: `tests/engine/test_kg_model.py`

**Interfaces:**
- Produces: `EdgeType.SAME_ENTITY` (value `"same_entity"`), consumed by Task 2's builder and Task 5's assemble.

- [ ] **Step 1: Write the failing test**

Add to `tests/engine/test_kg_model.py`:
```python
import json, pathlib
from osrs_planner.engine.kg.model import EdgeType
from osrs_planner.engine.kg.json_store import edge_to_dict, edge_from_dict
from osrs_planner.engine.kg.model import Edge

def test_same_entity_edge_type_exists_and_roundtrips():
    assert EdgeType.SAME_ENTITY.value == "same_entity"
    e = Edge(id=1, type=EdgeType.SAME_ENTITY, src="item:1712", dst="item:amulet-of-glory",
             cond_group=None, data={"basis": "x"})
    assert edge_from_dict(edge_to_dict(e)) == e

def test_schema_declares_same_entity_live():
    schema = json.load(open(pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json"))
    assert schema["edge_kinds"]["same_entity"]["status"] == "live"
    assert "is_page" in schema["node_kinds"]["item"]["data_keys"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py::test_same_entity_edge_type_exists_and_roundtrips tests/engine/test_kg_model.py::test_schema_declares_same_entity_live -v`
Expected: FAIL — `AttributeError: SAME_ENTITY` (enum) and `assert 'reserved' == 'live'`.

- [ ] **Step 3: Add the enum member**

In `src/osrs_planner/engine/kg/model.py`, in `class EdgeType`, after `SUPERSEDES = "supersedes"` add:
```python
    SAME_ENTITY = "same_entity"        # identity bridge (variant->page, page->family); decision 5/6
```

- [ ] **Step 4: Flip the schema status + extend item data_keys**

In `kg/schema.json`:
- In `edge_kinds.same_entity`, change `"status": "reserved"` to `"status": "live"`.
- In `node_kinds.item`, change `"data_keys"` to include the variant/page/family fields:
  `"data_keys": ["is_page", "is_family", "members", "is_canonical", "version_anchor", "variant_of", "tradeable", "value", "alch", "weight", "buy_limit", "aliases"]`
- In `node_kinds.item.notes`, append: ` Page-identity nodes are slug-keyed (item:<page-slug>) and family nodes item:<family-slug>; variant nodes are cache-id-keyed.`

- [ ] **Step 5: Run tests to verify they pass (incl. the model-enum⊆schema invariant)**

Run: `./venv/bin/python -m pytest tests/engine/test_kg_model.py tests/kg_ingest/test_validate_kg_schema.py::test_model_enums_are_all_declared_in_schema -v`
Expected: PASS (same_entity already declared in schema, so the subset invariant stays green).

- [ ] **Step 6: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py kg/schema.json tests/engine/test_kg_model.py
git commit -m "feat(kg): add EdgeType.SAME_ENTITY + flip schema same_entity to live"
```

---

### Task 2: `build_items` — Level 1 (intra-page variants + referenced singles)

**Files:**
- Create: `kg_ingest/builders/items.py`
- Test: `tests/kg_ingest/test_items_builder.py`

**Interfaces:**
- Produces: `build_items(dict_records: list[dict], exemplar_page_names: set[str], family_records: list[dict], referenced_item_ids: set[str], owned_ids: frozenset[str] = frozenset()) -> tuple[list[Node], list[Edge], dict]` — returns `(nodes, same_entity_edges, {})`. Consumed by Task 3 (extended) and Task 5 (assemble).
- Consumes: `EdgeType.SAME_ENTITY` (Task 1); `kg_ingest.ids.slugify`/`item_id`/`_stable_hash`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kg_ingest/test_items_builder.py`:
```python
from kg_ingest.builders.items import build_items
from osrs_planner.engine.kg.model import EdgeType, NodeKind

# Minimal in-memory dictionary records (mirrors data/item_dictionary.json shape).
DICT = [
    {"item_id": 1704, "name": "Amulet of glory", "members": True, "page_name": "Amulet of glory",
     "is_variant": True, "is_canonical": False, "version_anchor": "Uncharged"},
    {"item_id": 1712, "name": "Amulet of glory(4)", "members": True, "page_name": "Amulet of glory",
     "is_variant": True, "is_canonical": True, "version_anchor": "4"},
    {"item_id": 4587, "name": "Dragon scimitar", "members": True, "page_name": "Dragon scimitar",
     "is_variant": False, "is_canonical": True},
    {"item_id": 99, "name": "Referenced thing", "members": False, "page_name": "Referenced thing",
     "is_variant": False, "is_canonical": True},
]

def _by_id(nodes):
    return {n.id: n for n in nodes}

def test_multivariant_page_emits_page_node_variants_and_bridges():
    nodes, edges, groups = build_items(DICT, {"Amulet of glory"}, [], set())
    assert groups == {}
    byid = _by_id(nodes)
    page = byid["item:amulet-of-glory"]
    assert page.kind is NodeKind.ITEM and page.data == {"is_page": True} and page.name == "Amulet of glory"
    v = byid["item:1712"]
    assert v.name == "Amulet of glory(4)" and v.slug == "1712"
    assert v.data == {"members": True, "is_canonical": True, "version_anchor": "4"}
    se = [e for e in edges if e.type is EdgeType.SAME_ENTITY]
    pairs = {(e.src, e.dst) for e in se}
    assert ("item:1704", "item:amulet-of-glory") in pairs
    assert ("item:1712", "item:amulet-of-glory") in pairs
    assert all(e.data["basis"] == "shares wiki page 'Amulet of glory'" for e in se)

def test_single_variant_referenced_item_has_no_page_or_bridge():
    nodes, edges, _ = build_items(DICT, set(), [], {"item:99"})
    byid = _by_id(nodes)
    assert byid["item:99"].data == {"members": False, "is_canonical": True}
    assert "item:referenced-thing" not in byid       # no page node for single-variant
    assert not edges                                 # no same_entity bridge

def test_owned_ids_are_skipped_to_avoid_dedup_conflict():
    nodes, _, _ = build_items(DICT, set(), [], {"item:4587"}, owned_ids=frozenset({"item:4587"}))
    assert "item:4587" not in _by_id(nodes)          # build_goals owns it; build_items must not re-emit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_items_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: kg_ingest.builders.items`.

- [ ] **Step 3: Write the builder (Level 1)**

Create `kg_ingest/builders/items.py`:
```python
"""build_items — import item nodes from the Wiki-Bucket dictionary (slice 1).

Two-level variant model (decision 5): L1 auto intra-page variants (page node +
variant children + same_entity), L2 curated cross-page families (Task 3). Pure
transform; builder-local edge ids in a disjoint band, re-keyed by assemble.rekey.
"""
from __future__ import annotations

from collections import defaultdict

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, item_id, slugify

_EDGE_BAND = 0x50000000  # items-domain builder-local same_entity edge ids (rekeyed in assemble)


def _se_edge_id(src: str, dst: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src}#same_entity#{dst}")


def _page_id(page_name: str) -> str:
    return f"item:{slugify(page_name)}"


def _variant_node(rec: dict) -> Node:
    data = {"members": bool(rec.get("members")), "is_canonical": bool(rec.get("is_canonical"))}
    if rec.get("version_anchor"):
        data["version_anchor"] = rec["version_anchor"]
    return Node(id=item_id(rec["item_id"]), kind=NodeKind.ITEM,
                name=rec["name"], slug=str(rec["item_id"]), data=data)


def build_items(dict_records, exemplar_page_names, family_records,
                referenced_item_ids, owned_ids=frozenset()):
    by_id = {r["item_id"]: r for r in dict_records}
    by_page = defaultdict(list)
    for r in dict_records:
        by_page[r["page_name"]].append(r)

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    def emit(node: Node) -> None:
        if node.id in owned_ids:          # another builder owns it: link-don't-merge, skip
            return
        nodes.setdefault(node.id, node)

    family_member_pages = {m["page"] for fam in family_records for m in fam["members"]}
    full_pages = set(exemplar_page_names) | family_member_pages

    # --- L1: full intra-page import for exemplar + family-member pages ---
    for page in sorted(full_pages):
        recs = sorted(by_page.get(page, []), key=lambda r: r["item_id"])
        if len(recs) > 1:
            pid = _page_id(page)
            emit(Node(id=pid, kind=NodeKind.ITEM, name=page, slug=slugify(page),
                      data={"is_page": True}))
            for r in recs:
                emit(_variant_node(r))
                vid = item_id(r["item_id"])
                edges.append(Edge(id=_se_edge_id(vid, pid), type=EdgeType.SAME_ENTITY,
                                  src=vid, dst=pid, cond_group=None,
                                  data={"basis": f"shares wiki page '{page}'"}))
        elif len(recs) == 1:
            emit(_variant_node(recs[0]))   # single-variant page: no page node / no bridge

    # --- L1: referenced single items not already covered/owned ---
    for ref in sorted(referenced_item_ids):
        num = int(ref.split(":")[1])
        if num in by_id:
            emit(_variant_node(by_id[num]))

    # --- L2: cross-page families (Task 3 inserts here) ---

    return list(nodes.values()), edges, {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_items_builder.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/items.py tests/kg_ingest/test_items_builder.py
git commit -m "feat(kg): build_items L1 — intra-page variants + same_entity bridges"
```

---

### Task 3: `build_items` — Level 2 (curated cross-page families)

**Files:**
- Modify: `kg_ingest/builders/items.py` (insert the L2 block)
- Test: `tests/kg_ingest/test_items_builder.py` (add cases)

**Interfaces:**
- Consumes: `family_records` = list of `{"family_name", "slug", "members": [{"page", "basis"}], ...}`.
- Produces: family nodes `item:<slug>` `data={"is_family": True}` + `same_entity` (member-anchor → family) edges.

- [ ] **Step 1: Write the failing tests**

Add to `tests/kg_ingest/test_items_builder.py`:
```python
FAMILY_DICT = DICT + [
    {"item_id": 4081, "name": "Salve amulet", "members": True, "page_name": "Salve amulet",
     "is_variant": False, "is_canonical": True},
    {"item_id": 12017, "name": "Salve amulet(i)", "members": True, "page_name": "Salve amulet(i)",
     "is_variant": True, "is_canonical": True, "version_anchor": "Nightmare Zone"},
    {"item_id": 25250, "name": "Salve amulet(i)", "members": True, "page_name": "Salve amulet(i)",
     "is_variant": True, "is_canonical": False, "version_anchor": "Soul Wars"},
]
SALVE_FAMILY = [{
    "family_name": "Salve amulet (all variants)", "slug": "salve-amulet-family",
    "members": [{"page": "Salve amulet", "basis": "base"},
                {"page": "Salve amulet(i)", "basis": "imbue"}],
}]

def test_family_node_and_member_bridges():
    nodes, edges, _ = build_items(FAMILY_DICT, set(), SALVE_FAMILY, set())
    byid = _by_id(nodes)
    fam = byid["item:salve-amulet-family"]
    assert fam.data == {"is_family": True} and fam.name == "Salve amulet (all variants)"
    se = {(e.src, e.dst, e.data["basis"]) for e in edges if e.type is EdgeType.SAME_ENTITY}
    # single-variant member bridges from the VARIANT node; multi-variant member from the PAGE node
    assert ("item:4081", "item:salve-amulet-family", "base") in se
    assert ("item:salve-amulet-i", "item:salve-amulet-family", "imbue") in se

def test_multicanonical_page_tolerated():
    # Salve amulet(i) here has two is_canonical rows in real data; builder must not crash/assume singular.
    multi = [
        {"item_id": 25246, "name": "Ring of suffering (i)", "members": True,
         "page_name": "Ring of suffering (i)", "is_variant": True, "is_canonical": True, "version_anchor": "Uncharged"},
        {"item_id": 20657, "name": "Ring of suffering (i)", "members": True,
         "page_name": "Ring of suffering (i)", "is_variant": True, "is_canonical": True, "version_anchor": "Recoil"},
    ]
    nodes, edges, _ = build_items(multi, {"Ring of suffering (i)"}, [], set())
    canon = [n for n in nodes if n.data.get("is_canonical")]
    assert len(canon) == 2   # both kept; page node still anchors
    assert _by_id(nodes)["item:ring-of-suffering-i"].data == {"is_page": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_items_builder.py::test_family_node_and_member_bridges tests/kg_ingest/test_items_builder.py::test_multicanonical_page_tolerated -v`
Expected: FAIL — `test_family_node_and_member_bridges`: `KeyError: 'item:salve-amulet-family'` (no family node). (`test_multicanonical_page_tolerated` may already pass — L1 tolerates it; that's fine, it pins the behavior.)

- [ ] **Step 3: Insert the L2 block**

In `kg_ingest/builders/items.py`, replace the comment line `    # --- L2: cross-page families (Task 3 inserts here) ---` with:
```python
    # --- L2: cross-page families (curated) ---
    for fam in sorted(family_records, key=lambda f: f["slug"]):
        fam_id = f"item:{fam['slug']}"
        emit(Node(id=fam_id, kind=NodeKind.ITEM, name=fam["family_name"],
                  slug=fam["slug"], data={"is_family": True}))
        for m in fam["members"]:
            recs = by_page.get(m["page"], [])
            if len(recs) > 1:
                anchor = _page_id(m["page"])
            elif len(recs) == 1:
                anchor = item_id(recs[0]["item_id"])
            else:
                continue   # member page absent from dict; verify_item_families.py (Task 4) gates this
            edges.append(Edge(id=_se_edge_id(anchor, fam_id), type=EdgeType.SAME_ENTITY,
                              src=anchor, dst=fam_id, cond_group=None,
                              data={"basis": m["basis"]}))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_items_builder.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/items.py tests/kg_ingest/test_items_builder.py
git commit -m "feat(kg): build_items L2 — curated cross-page family bridges"
```

---

### Task 4: Curated data files + `verify_item_families.py` gate

**Files:**
- Create: `data/item_node_exemplars.json`
- Create: `data/item_node_families.json`
- Create: `data/verify_item_families.py`
- Test: `tests/kg_ingest/test_verify_item_families.py`

**Interfaces:**
- Produces: the two committed data files (consumed by Task 5 assemble) + a CLI verifier returning exit 0/1.

- [ ] **Step 1: Create `data/item_node_exemplars.json`**

```json
{
  "_provenance": {
    "note": "intra-page multi-variant exemplars (L1) proving decision-5 variant model",
    "source": "data/item_dictionary.json (page_name grouping)",
    "accessed": "2026-06-25"
  },
  "records": ["Amulet of glory", "Ring of dueling", "Ring of wealth", "Slayer ring", "Dragon dagger"]
}
```

- [ ] **Step 2: Create `data/item_node_families.json`** (editorial — source_token is a verbatim wiki phrase)

```json
{
  "_provenance": {
    "note": "curated cross-page families (L2); editorial — owner-reviewed",
    "license": "CC BY-NC-SA 3.0",
    "accessed": "2026-06-25",
    "deferred": "Bow of faerdhinen per-Elf-house/LMS/deadman cosmetic recolors (9 pages) deferred; core (base + (c)) only"
  },
  "records": [
    { "family_name": "Salve amulet (all variants)", "slug": "salve-amulet-family",
      "members": [ {"page": "Salve amulet", "basis": "base"},
                   {"page": "Salve amulet (e)", "basis": "enchant"},
                   {"page": "Salve amulet(i)", "basis": "imbue"},
                   {"page": "Salve amulet(ei)", "basis": "enchant_imbue"} ],
      "source_url": "https://oldschool.runescape.wiki/w/Salve_amulet",
      "source_token": "Salve amulet (i)" },
    { "family_name": "Scythe of vitur (all variants)", "slug": "scythe-of-vitur-family",
      "members": [ {"page": "Scythe of vitur", "basis": "base"},
                   {"page": "Holy scythe of vitur", "basis": "ornament_kit"},
                   {"page": "Sanguine scythe of vitur", "basis": "ornament_kit"},
                   {"page": "Corrupted scythe of vitur", "basis": "ornament_kit"},
                   {"page": "Scythe of vitur (rotten)", "basis": "broken"} ],
      "source_url": "https://oldschool.runescape.wiki/w/Scythe_of_vitur",
      "source_token": "Holy scythe of vitur" },
    { "family_name": "Ring of suffering (all variants)", "slug": "ring-of-suffering-family",
      "members": [ {"page": "Ring of suffering", "basis": "base"},
                   {"page": "Ring of suffering (i)", "basis": "imbue"} ],
      "source_url": "https://oldschool.runescape.wiki/w/Ring_of_suffering",
      "source_token": "Ring of suffering (i)" },
    { "family_name": "Bow of faerdhinen (core)", "slug": "bow-of-faerdhinen-family",
      "members": [ {"page": "Bow of faerdhinen", "basis": "base"},
                   {"page": "Bow of faerdhinen (c)", "basis": "enchant"} ],
      "source_url": "https://oldschool.runescape.wiki/w/Bow_of_faerdhinen",
      "source_token": "Bow of faerdhinen (c)" },
    { "family_name": "Crystal pickaxe (all variants)", "slug": "crystal-pickaxe-family",
      "members": [ {"page": "Crystal pickaxe", "basis": "base"},
                   {"page": "Crystal pickaxe (The Gauntlet)", "basis": "recharge_state"} ],
      "source_url": "https://oldschool.runescape.wiki/w/Crystal_pickaxe",
      "source_token": "Crystal pickaxe" },
    { "family_name": "Infernal axe (all variants)", "slug": "infernal-axe-family",
      "members": [ {"page": "Infernal axe", "basis": "base"},
                   {"page": "Infernal axe (or)", "basis": "ornament_kit"},
                   {"page": "Infernal axe (or) (Trailblazer Reloaded)", "basis": "ornament_kit"} ],
      "source_url": "https://oldschool.runescape.wiki/w/Infernal_axe",
      "source_token": "Infernal axe (or)" }
  ]
}
```

- [ ] **Step 3: Write the failing verifier test**

Create `tests/kg_ingest/test_verify_item_families.py`:
```python
import importlib.util, os, subprocess, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _run():
    return subprocess.run([sys.executable, os.path.join(_ROOT, "data", "verify_item_families.py")],
                          capture_output=True, text=True)

def test_verifier_passes_on_committed_families():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ITEM-FAMILIES VERIFICATION PASSED" in r.stdout
```

- [ ] **Step 4: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_item_families.py -v`
Expected: FAIL — `verify_item_families.py` does not exist (non-zero / FileNotFound).

- [ ] **Step 5: Write the verifier**

Create `data/verify_item_families.py`:
```python
#!/usr/bin/env python3
"""Source-grounding gate for data/item_node_families.json (editorial L2 layer).

Checks: every member `page` resolves in item_dictionary.json; every record has a
source_url + a non-empty source_token; family slugs are unique, end in '-family',
and never collide with a member page's slug. Exits non-zero on any violation.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from kg_ingest.ids import slugify  # noqa: E402

DICT = os.path.join(ROOT, "data", "item_dictionary.json")
FAMILIES = os.path.join(ROOT, "data", "item_node_families.json")


def main() -> int:
    errors: list[str] = []
    pages = {r["page_name"] for r in json.load(open(DICT, encoding="utf-8"))["records"]}
    fam_doc = json.load(open(FAMILIES, encoding="utf-8"))
    seen_slugs: set[str] = set()
    for rec in fam_doc["records"]:
        slug = rec.get("slug", "")
        if not slug.endswith("-family"):
            errors.append(f"[slug] {slug!r} must end with '-family'")
        if slug in seen_slugs:
            errors.append(f"[slug] duplicate family slug {slug!r}")
        seen_slugs.add(slug)
        if not rec.get("source_url") or not rec.get("source_token"):
            errors.append(f"[source] {slug!r} missing source_url/source_token")
        for m in rec.get("members", []):
            if m["page"] not in pages:
                errors.append(f"[page] {slug!r} member page {m['page']!r} not in item_dictionary")
            if slugify(m["page"]) == slug:
                errors.append(f"[collide] family slug {slug!r} collides with member page slug")
    if errors:
        print(f"ITEM-FAMILIES VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors:
            print("  -", e)
        return 1
    print("ITEM-FAMILIES VERIFICATION PASSED — all family records source-grounded.")
    print(f"  families: {len(fam_doc['records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_item_families.py -v && ./venv/bin/python data/verify_item_families.py`
Expected: PASS; verifier prints `ITEM-FAMILIES VERIFICATION PASSED`, exit 0.

- [ ] **Step 7: Commit**

```bash
git add data/item_node_exemplars.json data/item_node_families.json data/verify_item_families.py tests/kg_ingest/test_verify_item_families.py
git commit -m "data(kg): curated item exemplars + cross-page families + source-grounding verifier"
```

---

### Task 5: Wire `build_items` into `assemble.py` + regenerate the graph

**Files:**
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_golden_set.py` (existing — must stay green) + a new assemble integration test

**Interfaces:**
- Consumes: `build_items` (Tasks 2-3), the two data files (Task 4), `rekey`/`_collect_referenced_ids`/`dedup_nodes` (existing).

- [ ] **Step 1: Write the failing integration test**

Create `tests/kg_ingest/test_items_in_graph.py`:
```python
import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_committed_graph_has_item_pages_families_and_bridges():
    s = JsonKGStore.from_dir(KG)
    assert s.node("item:amulet-of-glory") is not None         # L1 page node
    assert s.node("item:amulet-of-glory").data.get("is_page") is True
    assert s.node("item:scythe-of-vitur-family") is not None  # L2 family node
    assert s.node("item:scythe-of-vitur-family").data.get("is_family") is True
    se = [e for e in s.edges if e.type is EdgeType.SAME_ENTITY]
    pairs = {(e.src, e.dst) for e in se}
    assert ("item:1712", "item:amulet-of-glory") in pairs            # variant -> page (L1)
    assert ("item:scythe-of-vitur", "item:scythe-of-vitur-family") in pairs  # page -> family (L2)
    # Dragon scimitar still resolves with its goal-owned name (no handoff conflict)
    assert s.node("item:4587").name == "Dragon scimitar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_items_in_graph.py -v`
Expected: FAIL — those nodes don't exist yet (assemble hasn't run build_items).

- [ ] **Step 3: Add the data loaders + import in `assemble.py`**

Near the other `_load_*` helpers in `kg_ingest/assemble.py`, add:
```python
ITEM_DICTIONARY_PATH = Path(__file__).resolve().parents[1] / "data" / "item_dictionary.json"
ITEM_EXEMPLARS_PATH = Path(__file__).resolve().parents[1] / "data" / "item_node_exemplars.json"
ITEM_FAMILIES_PATH = Path(__file__).resolve().parents[1] / "data" / "item_node_families.json"


def _load_item_dict_records() -> list[dict]:
    return json.loads(ITEM_DICTIONARY_PATH.read_text())["records"]


def _load_item_exemplars() -> set[str]:
    if not ITEM_EXEMPLARS_PATH.exists():
        return set()
    return set(json.loads(ITEM_EXEMPLARS_PATH.read_text())["records"])


def _load_item_families() -> list[dict]:
    if not ITEM_FAMILIES_PATH.exists():
        return []
    return json.loads(ITEM_FAMILIES_PATH.read_text())["records"]
```
And add the builder import at the top with the others:
```python
from kg_ingest.builders.items import build_items
```

- [ ] **Step 4: Wire `build_items` between reference-collection and `build_supporting`**

In `assemble.assemble()`, the current step 3 computes `referenced` then calls `build_supporting`. Replace that region (the `_LEAF_DOMAINS`/`owned_ids`/`referenced`/`s_nodes` block) with:
```python
    _LEAF_DOMAINS = frozenset(
        {"skill", "item", "access", "minigame", "gear_loadout", "npc"}
    )
    owned_ids = (
        {n.id for n in q_nodes}
        | {n.id for n in g_nodes}
        | {n.id for n in cg_nodes}
        | {n.id for n in d_nodes}
        | {n.id for n in dg_nodes}
        | {n.id for n in content_nodes}
    )
    referenced_all = _collect_referenced_ids(edges, groups)
    # Item nodes: build_items owns referenced items (in the dictionary) NOT already owned,
    # plus the curated exemplar/family rosters. It is re-keyed in its own call.
    referenced_item_ids = {r for r in referenced_all if r.startswith("item:")} - owned_ids
    i_nodes, i_edges, _ = build_items(
        _load_item_dict_records(), _load_item_exemplars(), _load_item_families(),
        referenced_item_ids, owned_ids=frozenset(owned_ids),
    )
    i_nodes, i_edges, _ = rekey(i_nodes, i_edges, {})
    edges = edges + i_edges
    owned_ids = owned_ids | {n.id for n in i_nodes}
    referenced = {
        r for r in referenced_all
        if r.split(":")[0] in _LEAF_DOMAINS
    } - owned_ids
    s_nodes = build_supporting(referenced)
```
Then add `i_nodes` to the final `dedup_nodes(...)` call (place it right before `s_nodes`):
```python
    nodes = dedup_nodes(
        q_nodes + g_nodes + cg_nodes + d_nodes + dg_nodes + content_nodes + i_nodes + s_nodes
    )
```

- [ ] **Step 5: Regenerate the committed graph**

Run: `./venv/bin/python -m kg_ingest.assemble`
Expected: writes `kg/{nodes,edges,condition_groups}.json` without error.

- [ ] **Step 6: Verify byte-stability, validators, golden, and the new integration test**

Run:
```bash
./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/   # second run must show NO further change
./venv/bin/python data/validate_kg.py            # expect exit 0
./venv/bin/python data/validate_cost.py          # expect exit 0
./venv/bin/python -m pytest tests/kg_ingest/test_golden_set.py tests/kg_ingest/test_items_in_graph.py -q
```
Expected: assemble idempotent (re-run identical); both validators exit 0; golden + integration tests PASS. If `validate_kg` reports a `[ref]` or domain/range VIOLATION, a `same_entity` endpoint is missing — check the family member pages all exist in the dict (Task 4 verifier).

- [ ] **Step 7: Commit (graph + wiring together — they must move as one)**

```bash
git add kg_ingest/assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_items_in_graph.py
git commit -m "feat(kg): wire build_items into assemble; regenerate graph with item variant layer"
```

---

### Task 6: Seed the competency-questions gate

**Files:**
- Create: `kg/competency_questions.json`
- Test: `tests/kg_ingest/test_competency_questions.py`

**Interfaces:**
- Consumes: the committed KG (Task 5) + `same_entity` edges.

- [ ] **Step 1: Write the failing runner test**

Create `tests/kg_ingest/test_competency_questions.py`:
```python
import json, pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

ROOT = pathlib.Path(__file__).resolve().parents[2]
KG = str(ROOT / "kg")

def _members(store, target):
    return {e.src for e in store.edges if e.type is EdgeType.SAME_ENTITY and e.dst == target}

def _family(store, target):
    out = set()
    for anchor in _members(store, target):          # family -> member pages/variants
        out.add(anchor)
        out |= _members(store, anchor)              # member page -> its variants
    return out

def test_all_competency_questions_pass():
    store = JsonKGStore.from_dir(KG)
    cqs = json.load(open(ROOT / "kg" / "competency_questions.json"))["records"]
    assert cqs
    for cq in cqs:
        if cq["method"] == "same_entity_members":
            answer = _members(store, cq["target"])
        elif cq["method"] == "same_entity_family":
            answer = _family(store, cq["target"])
        else:
            raise AssertionError(f"unknown method {cq['method']!r}")
        assert len(answer) >= cq["expect_min"], f"{cq['id']}: got {len(answer)} < {cq['expect_min']}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL — `FileNotFoundError`/`json` error: `kg/competency_questions.json` does not exist yet.

- [ ] **Step 3: Create `kg/competency_questions.json`**

```json
{
  "_provenance": {"note": "competency-questions CI gate (decision 9, from day one)", "accessed": "2026-06-25"},
  "records": [
    { "id": "cq-item-variants-amulet-of-glory",
      "question": "What are all variants of the Amulet of glory?",
      "method": "same_entity_members", "target": "item:amulet-of-glory", "expect_min": 5 },
    { "id": "cq-item-family-scythe-of-vitur",
      "question": "What are all Scythes of vitur (every kit)?",
      "method": "same_entity_family", "target": "item:scythe-of-vitur-family", "expect_min": 5 }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS — Amulet of glory family ≥ 5 variants; Scythe family ≥ 5 members+variants.

- [ ] **Step 5: Final full-suite gate**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 6: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): seed competency-questions gate (variant + family resolution)"
```

---

## Self-Review

**Spec coverage:** §2 L1 → Task 2; §2 L2 → Task 3; §3 builder + §4 handoff → Tasks 2/3/5; §5 additive (`SAME_ENTITY` + schema flip) → Task 1; §6 data files → Task 4; §7 CQ gate → Task 6; §8 success criteria → Task 5 step 6 + Task 6 step 5; §8 editorial verifier → Task 4. Anomalies (multi-canonical) → Task 3 test; (source-duplicate) → Task 3 FAMILY_DICT/byte of Task 5. Faerdhinen core-only → Task 4 data + `_provenance.deferred`.

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `build_items(dict_records, exemplar_page_names, family_records, referenced_item_ids, owned_ids)` signature identical across Tasks 2/3/5; `_se_edge_id`/`_page_id`/`_variant_node`/`emit` names consistent within `items.py`; `EdgeType.SAME_ENTITY` used uniformly; family record keys (`family_name`/`slug`/`members`/`page`/`basis`/`source_url`/`source_token`) consistent across Tasks 3/4/the verifier.
