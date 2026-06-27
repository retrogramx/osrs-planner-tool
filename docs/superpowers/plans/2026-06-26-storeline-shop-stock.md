# Source-Grounded Shop Stock (Storeline) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the owner's 27 category/aggregate `sells` shorthand with the wiki's authoritative per-shop stock from `Bucket:Storeline`, for Varrock's 15 shops.

**Architecture:** A new `build_storeline` becomes the sole source of `sells` edges, reading a committed full-bucket snapshot; `build_map` keeps containment but stops emitting sells. Storeline is the stock spine for the 13 covered shops; the owner's canonicalized gates ride as a cond_group overlay; 2 dialogue-shops with no Storeline fall back to owner sells. Pricing deferred (validate_cost clean).

**Tech Stack:** Python 3.14 via `./venv/bin/python`; OSRS Wiki Bucket API; committed JSON graph; pytest.

**Spec:** `docs/superpowers/specs/2026-06-26-storeline-shop-stock-design.md` (read it; this plan implements it).

## Global Constraints

- Run everything via `./venv/bin/python`. Branch: continue on `feat/connective-varrock` (do NOT branch).
- **`assemble` must be byte-stable** — re-run produces identical `kg/{nodes,edges,condition_groups}.json` bytes.
- **`build_storeline`'s edges are shop-`src` (sells), the SAME owner class as `build_map`'s shop-`src` `located_in`.** `rekey` derives ids from `stable_edge_id(owner, index)` with NO type component, so `build_storeline`'s OWN rekey call **MUST** pass `edge_index_seed` = per-owner edge counts already in `edges` (post-`build_map`). Without it, a shop's first sells edge collides with its `located_in` edge. The global edge-id-uniqueness assert (`assemble.py:428`) is the backstop.
- **Builder-local edge band `0xF0000000`, group band `0xC0000000`** (disjoint from `build_map`'s `0xE0`/`0xD0`).
- **Verifiers report, never hard-fail, on resolution/coverage residuals** (the editorial-data discipline). Structural violations hard-fail.
- **No cost tokens in the graph** — `validate_cost` Invariant 6 (`data/validate_cost.py:189`) FAILS on any `"price"`/`"cost"`/`"currency"` JSON key in `kg/*.json`. So sells edge `data` carries `{source_token, members?}` ONLY — **currency AND price are deferred** to the cost layer (the committed snapshot retains both). `validate_cost` must stay exit 0. (`members` is a boolean and is not a cost token.)
- **Never fabricate** — an unresolved `sold_item` is SKIPPED + reported, never emitted with a null/guessed dst.
- **Verified facts (2026-06-26, live):** full bucket = **6,236 rows / 581 shops**; bucket hard-caps at **5,000 rows/call** (paginate by offset); **13/15 Varrock shops resolve** (7 exact + 5 trailing-punctuation + Ratpit via town-disambiguator); **2 dialogue-shops** (`shop:baraeks-fur-stall`, `shop:varrock-apothecary`) have **no Storeline** → owner-sells fallback.
- Pre-existing `tests/drop_rates/` 4 collection errors are unrelated — ignore them.

## File Structure

- `data/fetch_storeline.py` (new) — paginated Bucket API fetch → raw snapshot. Mirrors `data/fetch_items_equipment.py`.
- `data/raw/storeline_bucket.json` (new, committed) — the full ~6,236-row snapshot, deterministically sorted.
- `kg_ingest/builders/storeline.py` (new) — `_norm`/`_base`/`index_by_shop`/`match_shop` (town-aware matcher) + `build_storeline` (the sells builder). Imports `make_item_resolver`/`_condition_atom` from `map_varrock` (no drift).
- `kg_ingest/builders/map_varrock.py` (modify) — `build_map` stops emitting `sells` (containment only).
- `data/map/varrock.json` (modify, Task 5) — canonicalize Zaff's 7 battlestaff offers → 2 (OWNER-REVIEWED).
- `kg_ingest/assemble.py` (modify) — wire `build_storeline` before the reference collection with a seeded rekey; add `_load_storeline_records()`.
- `data/verify_storeline.py` (new) — source-grounding gate (report-not-fail residuals + structural hard-fails).
- `data/verify_map.py` (modify) — drop the sells-resolution section (sells no longer originate in `build_map`).
- `kg/competency_questions.json` + `tests/kg_ingest/test_competency_questions.py` (modify) — add the `shop_stock` CQ.
- Tests: `tests/kg_ingest/test_storeline_snapshot.py`, `tests/kg_ingest/test_storeline_builder.py`, `tests/kg_ingest/test_storeline_in_graph.py`; edits to `tests/kg_ingest/test_map_in_graph.py`, `tests/kg_ingest/test_map_varrock_builder.py`.

---

### Task 1: Fetch + commit the Storeline raw snapshot

**Files:**
- Create: `data/fetch_storeline.py`
- Create (generated, commit): `data/raw/storeline_bucket.json`
- Test: `tests/kg_ingest/test_storeline_snapshot.py`

**Interfaces:**
- Produces: `data/raw/storeline_bucket.json` = `{"bucket": [ {sold_by, sold_item, store_currency, store_buy_price, store_sell_price, store_stock, store_delta, restock_time}, ... ], "_provenance": {...}}`, rows sorted by `(sold_by, sold_item)`.

- [ ] **Step 1: Write the failing snapshot test**

```python
# tests/kg_ingest/test_storeline_snapshot.py
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_storeline_snapshot_shape():
    raw = json.load(open(ROOT / "data" / "raw" / "storeline_bucket.json", encoding="utf-8"))
    rows = raw["bucket"]
    assert len(rows) >= 6000, f"expected full bucket, got {len(rows)}"
    soldby = {r["sold_by"] for r in rows}
    # exact-name shops, a trailing-punctuation shop, and a town-disambiguated shop must all be present
    assert "Varrock General Store" in soldby
    assert "Lowe's Archery Emporium" in soldby
    assert "Zaff's Superior Staffs!" in soldby
    assert "Ratpit bar (Varrock)" in soldby
    # rows are deterministically sorted
    keys = [(r.get("sold_by", ""), r.get("sold_item", "")) for r in rows]
    assert keys == sorted(keys)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_storeline_snapshot.py -v`
Expected: FAIL (file `data/raw/storeline_bucket.json` does not exist → FileNotFoundError).

- [ ] **Step 3: Write `data/fetch_storeline.py`**

```python
#!/usr/bin/env python3
"""Fetch the OSRS Wiki Bucket:Storeline (every shop's inventory) in full.

Source: OSRS Wiki Bucket API (action=bucket). Content licensed CC BY-NC-SA 3.0.
Verbatim — no inference. The server caps run() at 5000 rows, so paginate by offset.
Rows are sorted by (sold_by, sold_item) so the committed snapshot is byte-deterministic.
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
BASE = "https://oldschool.runescape.wiki/api.php"
PAGE = 5000
FIELDS = ["sold_by", "sold_item", "store_currency", "store_buy_price",
          "store_sell_price", "store_stock", "store_delta", "restock_time"]


def run_query(query):
    url = BASE + "?action=bucket&format=json&query=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def fetch_all():
    sel = ",".join(f"'{f}'" for f in FIELDS)
    rows, offset = [], 0
    while True:
        q = f"bucket('storeline').select({sel}).offset({offset}).limit({PAGE}).run()"
        d = run_query(q)
        if d.get("error"):
            raise RuntimeError(f"storeline offset={offset}: {d['error']}")
        batch = d.get("bucket", [])
        rows.extend(batch)
        print(f"  storeline: offset={offset} got {len(batch)} (total {len(rows)})")
        if len(batch) < PAGE:
            break
        offset += PAGE
        time.sleep(0.5)
    rows.sort(key=lambda r: (r.get("sold_by", ""), r.get("sold_item", "")))
    return rows


def main():
    os.makedirs(RAW, exist_ok=True)
    rows = fetch_all()
    out = {"_provenance": {"domain": "storeline",
                           "source_url": "https://oldschool.runescape.wiki/w/Bucket:Storeline",
                           "license": "CC BY-NC-SA 3.0", "extraction_method": "Bucket API action=bucket",
                           "query": f"bucket('storeline').select({','.join(FIELDS)}).run() [paginated by 5000]",
                           "row_count": len(rows)},
           "bucket": rows}
    with open(os.path.join(RAW, "storeline_bucket.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"DONE: {len(rows)} storeline rows")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the fetch (network) to produce the snapshot**

Run: `./venv/bin/python data/fetch_storeline.py`
Expected: prints offset pages (`offset=0 got 5000`, `offset=5000 got ~1236`) then `DONE: ~6236 storeline rows`; writes `data/raw/storeline_bucket.json`. (Requires network. If the environment blocks it, run on a connected machine and commit the file.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_storeline_snapshot.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add data/fetch_storeline.py data/raw/storeline_bucket.json tests/kg_ingest/test_storeline_snapshot.py
git commit -m "feat(data): fetch + commit Bucket:Storeline snapshot (paginated full bucket)"
```

---

### Task 2: The town-aware shop matcher

**Files:**
- Create: `kg_ingest/builders/storeline.py` (the matcher + helpers; `build_storeline` added in Task 3)
- Test: `tests/kg_ingest/test_storeline_builder.py`

**Interfaces:**
- Produces: `_norm(s) -> str`, `_base(s) -> str`, `index_by_shop(records) -> dict[str, list[dict]]`, `match_shop(shop_name: str, soldby_keys: list[str]) -> str | None`.

- [ ] **Step 1: Write the failing matcher tests**

```python
# tests/kg_ingest/test_storeline_builder.py
from kg_ingest.builders.storeline import _norm, _base, index_by_shop, match_shop

KEYS = ["Varrock General Store", "Lowe's Archery Emporium", "Zaff's Superior Staffs!",
        "Ratpit bar (Varrock)", "Ratpit bar (Keldagrim)", "Aubury's Rune Shop."]

def test_exact_match():
    assert match_shop("Varrock General Store", KEYS) == "Varrock General Store"
    assert match_shop("Lowe's Archery Emporium", KEYS) == "Lowe's Archery Emporium"

def test_trailing_punctuation_match():
    assert match_shop("Zaff's Superior Staffs", KEYS) == "Zaff's Superior Staffs!"
    assert match_shop("Aubury's Rune Shop", KEYS) == "Aubury's Rune Shop."

def test_town_disambiguator_required():
    # bare base name collides across towns -> must pick the (Varrock) one, never Keldagrim
    assert match_shop("Ratpit Bar", KEYS) == "Ratpit bar (Varrock)"

def test_no_match_returns_none():
    assert match_shop("Baraek's Fur Stall", KEYS) is None
    assert match_shop("Varrock Apothecary", KEYS) is None

def test_index_by_shop_groups_rows():
    recs = [{"sold_by": "A", "sold_item": "x"}, {"sold_by": "A", "sold_item": "y"},
            {"sold_by": "B", "sold_item": "z"}]
    idx = index_by_shop(recs)
    assert sorted(r["sold_item"] for r in idx["A"]) == ["x", "y"]
    assert len(idx["B"]) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_storeline_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: kg_ingest.builders.storeline`.

- [ ] **Step 3: Write `kg_ingest/builders/storeline.py` (matcher + helpers only)**

```python
"""build_storeline — source-grounded shop stock (slice 7).

Reads the committed Bucket:Storeline snapshot + data/map/varrock.json and emits the
sells edges: Storeline is the stock spine for shops it covers; the owner's canonicalized
gates ride as a cond_group overlay; shops with no Storeline rows (dialogue-shops) fall
back to the owner's authored sells. Shop matching is normalize-but-town-aware. Edges are
shop-src -> assemble re-keys them in their OWN seeded call.
"""
from __future__ import annotations

import re
from collections import defaultdict

from osrs_planner.engine.kg.model import ConditionGroup, Edge, EdgeType, Node, Op
from kg_ingest.ids import _stable_hash, item_id
from kg_ingest.builders.map_varrock import make_item_resolver, _condition_atom

_EDGE_BAND = 0xF0000000
_GROUP_BAND = 0xC0000000


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _gid(owner_id: str, slot: str) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner_id}#group#{slot}")


def _norm(s: str) -> str:
    return s.strip().rstrip(".!").strip().casefold()


def _base(s: str) -> str:
    return _norm(re.sub(r"\s*\(.*?\)\s*$", "", s))


def index_by_shop(records):
    by: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        sb = r.get("sold_by")
        if sb:
            by[sb].append(r)
    return by


def match_shop(shop_name, soldby_keys):
    if shop_name in soldby_keys:
        return shop_name
    n = _norm(shop_name)
    norm_hits = [k for k in soldby_keys if _norm(k) == n]
    if len(norm_hits) == 1:
        return norm_hits[0]
    base = _base(shop_name)
    town_hits = [k for k in soldby_keys if _base(k) == base and "(varrock)" in k.casefold()]
    if len(town_hits) == 1:
        return town_hits[0]
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_storeline_builder.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/storeline.py tests/kg_ingest/test_storeline_builder.py
git commit -m "feat(kg): storeline town-aware shop matcher"
```

---

### Task 3: `build_storeline` — sells edges (Storeline spine + gate overlay + fallback)

**Files:**
- Modify: `kg_ingest/builders/storeline.py` (add `_emit_owner_offer` + `build_storeline`)
- Test: `tests/kg_ingest/test_storeline_builder.py` (add builder tests)

**Interfaces:**
- Consumes: `make_item_resolver`, `_condition_atom` (from `map_varrock`); `index_by_shop`/`match_shop` (Task 2).
- Produces: `build_storeline(storeline_records: list[dict], map_data: dict, dict_records: list[dict]) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]` (nodes always `[]`; edges are shop-`src` `sells`; groups are gate cond_groups).

- [ ] **Step 1: Write the failing builder tests**

```python
# add to tests/kg_ingest/test_storeline_builder.py
from kg_ingest.builders.storeline import build_storeline
from osrs_planner.engine.kg.model import EdgeType

DICT = [   # members is a BOOLEAN in item_dictionary.json (Battlestaff is members)
    {"item_id": 1391, "name": "Battlestaff", "page_name": "Battlestaff", "is_canonical": True, "members": True},
    {"item_id": 1381, "name": "Staff of air", "page_name": "Staff of air", "is_canonical": True, "members": False},
    {"item_id": 6814, "name": "Fur", "page_name": "Fur", "is_canonical": True, "members": False},
]
# Zaff is covered (has Storeline rows); Baraek is a dialogue-shop (no Storeline rows).
STORELINE = [
    {"sold_by": "Zaff's Superior Staffs!", "sold_item": "Staff of air", "store_currency": "Coins"},
    {"sold_by": "Zaff's Superior Staffs!", "sold_item": "Battlestaff", "store_currency": "Coins"},
]
MAP = {"shops": [
    {"id": "shop:zaffs-superior-staffs", "name": "Zaff's Superior Staffs",
     "sells": [{"item_name": "Battlestaff", "source_token": "Zaff sells battlestaves",
                "condition": {"type": "quest", "ref": "What Lies Below", "state": "in_progress"}}]},
    {"id": "shop:baraeks-fur-stall", "name": "Baraek's Fur Stall",
     "sells": [{"item_name": "Fur", "source_token": "Baraek sells fur"}]},
]}

def _sells(edges):
    return {(e.src, e.dst, e.cond_group is not None) for e in edges if e.type is EdgeType.SELLS}

def test_covered_shop_storeline_supplies_ungated_overlay_owns_gated():
    nodes, edges, groups = build_storeline(STORELINE, MAP, DICT)
    s = _sells(edges)
    # Storeline supplies the ungated staff; the gated battlestaff is overlay-owned (gated edge)
    assert ("shop:zaffs-superior-staffs", "item:1381", False) in s   # Storeline staff
    assert ("shop:zaffs-superior-staffs", "item:1391", True) in s    # gated battlestaff (overlay)
    # NO duplicate: Storeline must NOT also emit an ungated battlestaff (ownership rule)
    assert ("shop:zaffs-superior-staffs", "item:1391", False) not in s
    assert nodes == []
    assert len(groups) == 1                                          # one gate cond_group

def test_dialogue_shop_falls_back_to_owner_sells():
    nodes, edges, groups = build_storeline(STORELINE, MAP, DICT)
    s = _sells(edges)
    assert ("shop:baraeks-fur-stall", "item:6814", False) in s       # owner-sells fallback

def test_storeline_edge_carries_members_no_cost_tokens():
    nodes, edges, groups = build_storeline(STORELINE, MAP, DICT)
    staff = next(e for e in edges if e.dst == "item:1381")
    assert staff.data["members"] is False
    # validate_cost Inv 6 forbids price/cost/currency keys in the graph -> none on the edge
    assert "currency" not in staff.data
    assert "store_currency" not in staff.data
    assert "store_buy_price" not in staff.data

def test_unresolved_sold_item_is_skipped_not_fabricated():
    sl = STORELINE + [{"sold_by": "Zaff's Superior Staffs!", "sold_item": "Nonexistent thing", "store_currency": "Coins"}]
    nodes, edges, groups = build_storeline(sl, MAP, DICT)
    assert all(e.dst is not None for e in edges)
    assert not any(e.dst == "item:None" for e in edges)
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_storeline_builder.py -k "covered or dialogue or carries or unresolved" -v`
Expected: FAIL with `ImportError: cannot import name 'build_storeline'`.

- [ ] **Step 3: Add `_emit_owner_offer` + `build_storeline` to `kg_ingest/builders/storeline.py`**

```python
def _emit_owner_offer(edges, groups, sid, idx, offer, resolve, dict_by_id, prefix):
    """Emit one owner-authored sells offer (slice-6 logic). Returns the resolved item_id or None."""
    iid = resolve(offer["item_name"])
    if iid is None:
        return None  # unresolved -> reported by verify_storeline, never fabricated
    cg = None
    if offer.get("condition"):
        atom = _condition_atom(offer["condition"])
        if atom is None:
            return None  # unknown condition type -> reported/failed by verifier
        gid = _gid(sid, f"{prefix}{idx}")
        groups[gid] = ConditionGroup(id=gid, op=Op.AND, parent=None, children=[atom])
        cg = gid
    data = {"source_token": offer.get("source_token")}   # NO currency/price -> validate_cost Inv 6
    mem = dict_by_id.get(iid, {}).get("members")
    if mem is not None:
        data["members"] = mem
    if offer.get("noted"):
        data["noted"] = True
    edges.append(Edge(id=_edge_id(sid, f"{prefix}#{idx}"), type=EdgeType.SELLS,
                      src=sid, dst=item_id(iid), cond_group=cg, data=data))
    return iid


def build_storeline(storeline_records, map_data, dict_records):
    resolve = make_item_resolver(dict_records)
    dict_by_id = {r["item_id"]: r for r in dict_records}
    by_shop = index_by_shop(storeline_records)
    soldby_keys = list(by_shop)

    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    for sh in map_data["shops"]:
        sid = sh["id"]
        owner_sells = sh.get("sells", [])
        matched = match_shop(sh["name"], soldby_keys)

        if matched is None:
            # NO-STORELINE FALLBACK (dialogue-shops): emit the owner's authored sells
            for i, offer in enumerate(owner_sells):
                _emit_owner_offer(edges, groups, sid, i, offer, resolve, dict_by_id, "own")
            continue

        # COVERED SHOP: owner gates are overlay-owned; Storeline supplies the rest.
        gated = [o for o in owner_sells if o.get("condition")]
        gated_items = set()
        for i, offer in enumerate(gated):
            iid = _emit_owner_offer(edges, groups, sid, i, offer, resolve, dict_by_id, "gate")
            if iid is not None:
                gated_items.add(iid)
        for j, row in enumerate(by_shop[matched]):
            iid = resolve(row.get("sold_item", ""))
            if iid is None:
                continue                      # unresolved -> reported by verify_storeline
            if iid in gated_items:
                continue                      # ownership rule: overlay owns gated items
            data = {"source_token": "Bucket:Storeline"}   # currency stays in the snapshot, NOT the graph
            mem = dict_by_id.get(iid, {}).get("members")
            if mem is not None:
                data["members"] = mem
            edges.append(Edge(id=_edge_id(sid, f"sl#{j}"), type=EdgeType.SELLS,
                              src=sid, dst=item_id(iid), cond_group=None, data=data))

    return [], edges, groups
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_storeline_builder.py -v`
Expected: PASS (all matcher + builder tests).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/storeline.py tests/kg_ingest/test_storeline_builder.py
git commit -m "feat(kg): build_storeline — Storeline spine + gate overlay + dialogue-shop fallback"
```

---

### Task 4: `build_map` stops emitting sells (containment only)

**Files:**
- Modify: `kg_ingest/builders/map_varrock.py` (remove the sells loop in `build_map`)
- Test: `tests/kg_ingest/test_map_varrock_builder.py` (assert no sells from `build_map`)

**Interfaces:**
- `build_map(map_data, resolve, region_ids)` keeps its signature; now returns NO `SELLS` edges and an empty `groups` dict. (`resolve` is still accepted for signature stability; unused.) `make_item_resolver`/`_condition_atom`/`_diary_ref_to_id` STAY in this module — `build_storeline` and the verifiers import them.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/kg_ingest/test_map_varrock_builder.py
from osrs_planner.engine.kg.model import EdgeType as _ET

def test_build_map_emits_no_sells():
    import json, pathlib
    from kg_ingest.builders.map_varrock import build_map, make_item_resolver
    root = pathlib.Path(__file__).resolve().parents[2]
    m = json.loads((root / "data" / "map" / "varrock.json").read_text())
    resolve = make_item_resolver(json.loads((root / "data" / "item_dictionary.json").read_text())["records"])
    nodes, edges, groups = build_map(m, resolve, set())
    assert not any(e.type is _ET.SELLS for e in edges)   # sells now come from build_storeline
    assert groups == {}                                  # gate groups moved to build_storeline
    assert any(e.type is _ET.LOCATED_IN for e in edges)  # containment still emitted
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_map_varrock_builder.py::test_build_map_emits_no_sells -v`
Expected: FAIL (`build_map` still emits SELLS edges and a non-empty groups dict).

- [ ] **Step 3: Remove the sells loop from `build_map`**

In `kg_ingest/builders/map_varrock.py`, delete the entire `for i, offer in enumerate(sh.get("sells", [])):` block (the body that builds `iid`, `cg`, `groups[gid]`, and appends the `EdgeType.SELLS` edge) inside the shops loop. The shops loop becomes just the node + `located_in` edge:

```python
    # shops (containment only; sells now come from build_storeline — slice 7)
    for sh in map_data["shops"]:
        nodes.append(Node(id=sh["id"], kind=NodeKind.SHOP, name=sh["name"], slug=_slug(sh["id"]),
                          data={"operator": sh.get("operator"), "shop_type": sh.get("shop_type")}))
        if sh.get("located_in"):
            edges.append(Edge(id=_edge_id(sh["id"], "located_in"), type=EdgeType.LOCATED_IN,
                              src=sh["id"], dst=sh["located_in"], cond_group=None, data={}))

    return nodes, edges, groups
```

Leave `make_item_resolver`, `_condition_atom`, `_diary_ref_to_id`, `_gid` in place (imported elsewhere). Update the module docstring's "sells" mention to note sells moved to `build_storeline`.

- [ ] **Step 4: Run to verify it passes (and the existing builder tests still pass)**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_map_varrock_builder.py -v`
Expected: PASS. (Any existing test asserting a specific sells edge from `build_map` must be updated/removed here — the Zaff→battlestaff assertion moves to Task 6's integration test.)

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/map_varrock.py tests/kg_ingest/test_map_varrock_builder.py
git commit -m "refactor(kg): build_map stops emitting sells (moved to build_storeline)"
```

---

### Task 5: Canonicalize Zaff's gates in `varrock.json` — OWNER REVIEW CHECKPOINT

**Files:**
- Modify: `data/map/varrock.json` (`shop:zaffs-superior-staffs` `sells`)

**This task is an editorial edit gated by owner review — a validator cannot judge the collapse.** The controller presents the before→after to the owner and applies only on approval (do NOT silently rewrite owner conditions).

**Interfaces:**
- Produces: Zaff's `sells` reduced to the 2 canonical gated offers (the ungated staves are superseded by Storeline and removed; the redundant battlestaff variants collapse).

- [ ] **Step 1: Show the owner the before→after**

Current Zaff `sells` (14 entries: 6 ungated staves + "Staves" + 7 overlapping battlestaff offers). Proposed canonical set (2 entries):

```json
"sells": [
  { "item_name": "Battlestaff", "source_token": "Only after completing most of What Lies Below.",
    "condition": { "type": "quest", "ref": "What Lies Below", "state": "in_progress" } },
  { "item_name": "Battlestaff (noted)", "source_token": "Varrock Diary daily discounted battlestaves.",
    "noted": true,
    "condition": { "type": "achievement_diary", "ref": "Varrock Diary - Easy", "state": "completed" } }
]
```

Rationale to present: the two *What Lies Below* gates collapse (`in_progress` already unlocks it); the four diary tiers collapse to the minimum-unlock `Easy` (per-tier quantity is deferred with pricing); the ungated staves (Staff, Magic staff, Staff of air/water/earth/fire) + "Staves" are dropped because Storeline now supplies Zaff's exact staff stock. **Get explicit owner approval before editing.**

- [ ] **Step 2: Apply the approved edit** to `data/map/varrock.json` (`shop:zaffs-superior-staffs.sells`).

- [ ] **Step 3: Structural sanity check** (the refs still resolve)

Run: `./venv/bin/python -c "import json,sys; sys.path[:0]=['.','src']; from kg_ingest.builders.map_varrock import _condition_atom; m=json.load(open('data/map/varrock.json')); z=[s for s in m['shops'] if s['id']=='shop:zaffs-superior-staffs'][0]; print([(_condition_atom(o['condition']).atom_type.value, _condition_atom(o['condition']).ref_node) for o in z['sells']])"`
Expected: prints `[('quest', 'quest:what-lies-below'), ('achievement_diary', 'diary:varrock:easy')]` — both refs well-formed.

- [ ] **Step 4: Commit**

```bash
git add data/map/varrock.json
git commit -m "data(map): canonicalize Zaff battlestaff gates (owner-reviewed): 14 sells -> 2 gates"
```

---

### Task 6: Wire `build_storeline` into assemble + regenerate the graph

**Files:**
- Modify: `kg_ingest/assemble.py` (add `_load_storeline_records()`, the seeded `build_storeline` wiring)
- Modify (generated): `kg/{nodes,edges,condition_groups}.json`
- Test: `tests/kg_ingest/test_storeline_in_graph.py` (new); `tests/kg_ingest/test_map_in_graph.py` (drop the sells assertions)

**Interfaces:**
- Consumes: `build_storeline` (Task 3). Adds `_load_storeline_records() -> list[dict]` reading `data/raw/storeline_bucket.json`'s `"bucket"`.

- [ ] **Step 1: Write the failing integration test**

```python
# tests/kg_ingest/test_storeline_in_graph.py
import json, pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

ROOT = pathlib.Path(__file__).resolve().parents[2]

def _store():
    return JsonKGStore.from_dir(str(ROOT / "kg"))

def test_lowes_stocks_storeline_items():
    store = _store()
    stock = {e.dst for e in store.edges if e.type is EdgeType.SELLS and e.src == "shop:lowes-archery-emporium"}
    assert len(stock) >= 10                                 # the 27 categories -> exact Storeline stock

def test_zaff_battlestaff_keeps_gate():
    store = _store()
    gated = [e for e in store.edges if e.type is EdgeType.SELLS
             and e.src == "shop:zaffs-superior-staffs" and e.dst == "item:1391"]
    assert gated and any(e.cond_group is not None for e in gated)   # the What-Lies-Below overlay survives

def test_dialogue_shop_keeps_owner_sell():
    store = _store()
    fur = {e.dst for e in store.edges if e.type is EdgeType.SELLS and e.src == "shop:baraeks-fur-stall"}
    assert "item:6814" in fur                               # Baraek's Fur fallback (no Storeline)

def test_no_gated_and_ungated_duplicate():
    store = _store()
    pairs = {}
    for e in store.edges:
        if e.type is EdgeType.SELLS:
            pairs.setdefault((e.src, e.dst), set()).add(e.cond_group is not None)
    assert not [k for k, v in pairs.items() if v == {True, False}]   # ownership rule holds in the graph
```

(Item ids: `item:1391` Battlestaff, `item:6814` Fur — confirm against the committed `item_dictionary.json` during implementation; adjust if the Fur id differs.)

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_storeline_in_graph.py -v`
Expected: FAIL (the committed graph has no Storeline edges yet — Lowe's stock is empty).

- [ ] **Step 3: Add `_load_storeline_records()` to `assemble.py`** (near `_load_varrock_map`, ~line 290)

```python
STORELINE_RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "storeline_bucket.json"


def _load_storeline_records() -> list[dict]:
    if not STORELINE_RAW_PATH.exists():
        return []
    return json.loads(STORELINE_RAW_PATH.read_text())["bucket"]
```

- [ ] **Step 4: Add the import + the seeded wiring**

Add to the builder imports (after the `map_varrock` import, line ~36):
```python
from kg_ingest.builders.storeline import build_storeline
```

Insert the wiring immediately AFTER the `build_map` block (after `owned_ids = owned_ids | {n.id for n in map_nodes}`, line ~400) and BEFORE `referenced_all = _collect_referenced_ids(...)` (line ~402):

```python
    # Source-grounded shop stock (slice 7): Storeline is the stock spine. build_map no
    # longer emits sells; build_storeline emits ALL sells (Storeline + owner-gate overlay
    # + dialogue-shop fallback). Its edges are shop-src (sells), the SAME owner class as
    # build_map's located_in, so its OWN rekey MUST be seeded with the per-owner edge
    # counts already in `edges` (else a shop's first sells collides with its located_in).
    if _map is not None:
        st_nodes, st_edges, st_groups = build_storeline(
            _load_storeline_records(), _map, _load_item_dict_records())
        _prior_src_counts: dict[str, int] = {}
        for _e in edges:
            _prior_src_counts[_e.src] = _prior_src_counts.get(_e.src, 0) + 1
        st_nodes, st_edges, st_groups = rekey(st_nodes, st_edges, st_groups,
                                              edge_index_seed=_prior_src_counts)
        edges = edges + st_edges
        groups.update(st_groups)
```

(No `st_nodes` to dedup — `build_storeline` returns `[]` nodes; items auto-import via the reference collection that follows.)

- [ ] **Step 5: Regenerate + verify byte-stability**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/`
Expected: the SECOND run leaves `kg/` unchanged in `git diff --stat` (byte-stable). The global edge-id assert (`assemble.py:428`) does not raise.

- [ ] **Step 6: Update `tests/kg_ingest/test_map_in_graph.py`** — remove assertions that `build_map`/the graph carries a Zaff→battlestaff *sells* edge (those now live in `test_storeline_in_graph.py`). Keep the containment assertions (place/npc/shop, located_in, operates, same_entity). Run:

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_map_in_graph.py tests/kg_ingest/test_storeline_in_graph.py -v`
Expected: PASS (both).

- [ ] **Step 7: Commit**

```bash
git add kg_ingest/assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_storeline_in_graph.py tests/kg_ingest/test_map_in_graph.py
git commit -m "feat(kg): wire build_storeline (seeded shop-src rekey); regenerate graph"
```

---

### Task 7: `verify_storeline.py` + move the sells section out of `verify_map.py`

**Files:**
- Create: `data/verify_storeline.py`
- Modify: `data/verify_map.py` (drop the sells loop)
- Test: `tests/kg_ingest/test_verify_storeline.py`

**Interfaces:**
- Consumes: `make_item_resolver`/`_condition_atom` (map_varrock), `index_by_shop`/`match_shop` (storeline). Reuses the committed `kg/{nodes,edges}.json`.

- [ ] **Step 1: Write the failing verifier test**

```python
# tests/kg_ingest/test_verify_storeline.py
import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_verify_storeline_passes_on_committed_graph():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_storeline.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "STORELINE VERIFICATION PASSED" in r.stdout
    assert "shops covered by Storeline: 13/15" in r.stdout            # 2 dialogue-shops fall back
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_storeline.py -v`
Expected: FAIL (`data/verify_storeline.py` does not exist).

- [ ] **Step 3: Write `data/verify_storeline.py`**

```python
#!/usr/bin/env python3
"""Source-grounding gate for the Storeline shop-stock layer (slice 7).

REPORTS (never fails) resolution/coverage residuals: shops with no Storeline match
(dialogue-shops -> owner fallback) and sold_item names that don't resolve. HARD-FAILS
(exit 1) on structural violations: a malformed owner gate (bad type / ref not in the
committed graph / missing source_token) and the ownership rule (no shop->item with BOTH
a gated and an ungated sells edge in the committed graph). Reuses the builder helpers.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.map_varrock import make_item_resolver, _condition_atom  # noqa: E402
from kg_ingest.builders.storeline import index_by_shop, match_shop              # noqa: E402

MAP = os.path.join(ROOT, "data", "map", "varrock.json")
RAW = os.path.join(ROOT, "data", "raw", "storeline_bucket.json")
DICT = os.path.join(ROOT, "data", "item_dictionary.json")
NODES = os.path.join(ROOT, "kg", "nodes.json")
EDGES = os.path.join(ROOT, "kg", "edges.json")


def main() -> int:
    errors, unresolved = [], []
    m = json.load(open(MAP, encoding="utf-8"))
    records = json.load(open(RAW, encoding="utf-8"))["bucket"]
    resolve = make_item_resolver(json.load(open(DICT, encoding="utf-8"))["records"])
    graph_ids = {n["id"] for n in json.load(open(NODES, encoding="utf-8"))}
    edges = json.load(open(EDGES, encoding="utf-8"))

    by_shop = index_by_shop(records)
    soldby = list(by_shop)

    covered, uncovered = [], []
    total = resolved = 0
    for sh in m["shops"]:
        matched = match_shop(sh["name"], soldby)
        if matched is None:
            uncovered.append(sh["id"]); continue
        covered.append(sh["id"])
        for row in by_shop[matched]:
            total += 1
            if resolve(row.get("sold_item", "")) is None:
                unresolved.append(f"{sh['id']}: {row.get('sold_item')!r}")
            else:
                resolved += 1

    # HARD-FAIL: owner gate conditions well-formed + resolve + have a source_token
    for sh in m["shops"]:
        for offer in sh.get("sells", []):
            cond = offer.get("condition")
            if not cond:
                continue
            if not offer.get("source_token"):
                errors.append(f"[source] gated sell {offer.get('item_name')!r} in {sh['id']!r} missing source_token")
            atom = _condition_atom(cond)
            if atom is None:
                errors.append(f"[condition] {offer.get('item_name')!r} in {sh['id']!r} bad type {cond.get('type')!r}")
            elif atom.ref_node not in graph_ids:
                errors.append(f"[ref] {atom.ref_node!r} ({offer.get('item_name')!r}) not in the committed graph")

    # HARD-FAIL: ownership rule — no (shop -> item) with BOTH a gated and an ungated sells edge
    pairs: dict[tuple, set] = {}
    for e in edges:
        if e.get("type") == "sells":
            pairs.setdefault((e["src"], e["dst"]), set()).add(e.get("cond_group") is not None)
    for (src, dst), kinds in sorted(pairs.items()):
        if kinds == {True, False}:
            errors.append(f"[ownership] {src} -> {dst} has BOTH a gated and an ungated sells edge")

    if errors:
        print(f"STORELINE VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print("STORELINE VERIFICATION PASSED — Varrock shop stock source-grounded.")
    print(f"  shops covered by Storeline: {len(covered)}/{len(m['shops'])} ; "
          f"dialogue-shops (owner-sells fallback): {sorted(uncovered)}")
    print(f"  storeline rows resolved: {resolved}/{total}")
    if unresolved:
        print(f"  {len(unresolved)} unresolved sold_item name(s) (residual — alias pass):")
        for u in unresolved[:40]:
            print("    -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Drop the sells loop from `data/verify_map.py`**

Remove the entire `for offer in sh.get("sells", []):` block (lines ~54-67: the `total_sells`/`unresolved`/`condition` checks) from `verify_map.py`, plus the now-unused `unresolved`/`total_sells`/`resolved` variables and the trailing "unresolved sells" print. Keep the `located_in`, operator-reciprocity, and slug-uniqueness structural checks and the `_condition_atom` import (still used? no — drop the `_condition_atom` import if unused after removal). Update the PASSED line to drop the `sells resolved` clause. Result: `verify_map` covers containment only; `verify_storeline` owns sells/gates.

- [ ] **Step 5: Run both verifiers + their tests**

Run: `./venv/bin/python data/verify_map.py && ./venv/bin/python data/verify_storeline.py && ./venv/bin/python -m pytest tests/kg_ingest/test_verify_storeline.py tests/kg_ingest/test_verify_map.py -v`
Expected: both verifiers exit 0; `verify_storeline` prints `shops covered by Storeline: 13/15`; tests PASS. (Update `test_verify_map.py` if it asserted the old `sells resolved` line.)

- [ ] **Step 6: Commit**

```bash
git add data/verify_storeline.py data/verify_map.py tests/kg_ingest/test_verify_storeline.py tests/kg_ingest/test_verify_map.py
git commit -m "feat(data): verify_storeline (report-not-fail residuals); verify_map drops sells section"
```

---

### Task 8: `shop_stock` competency question

**Files:**
- Modify: `kg/competency_questions.json`
- Modify: `tests/kg_ingest/test_competency_questions.py`

**Interfaces:**
- Adds a `shop_stock` method to the CQ runner: shops' `sells` out-edges.

- [ ] **Step 1: Add the CQ record (method unknown to the runner) — RED**

Append to the `records` array in `kg/competency_questions.json` (after the `cq-battlestaff-sold-by` record):
```json
    ,{ "id": "cq-lowes-shop-stock",
      "question": "What does Lowe's Archery Emporium stock?",
      "method": "shop_stock", "target": "shop:lowes-archery-emporium", "expect_min": 10 }
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL with `unknown method 'shop_stock'`.

- [ ] **Step 3: Add the `_shop_stock` helper + dispatch branch**

In `tests/kg_ingest/test_competency_questions.py`, add the helper (next to `_sold_by`):
```python
def _shop_stock(store, target):
    # the set of items a shop sells (out-edges)
    return {e.dst for e in store.edges if e.type is EdgeType.SELLS and e.src == target}
```
Add the dispatch branch (before the final `else: raise`):
```python
        elif cq["method"] == "shop_stock":
            answer = _shop_stock(store, cq["target"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS (Lowe's stock ≥ 10).

- [ ] **Step 5: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): competency question — what does Lowe's Archery Emporium stock"
```

---

### Task 9: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Byte-stable assemble**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/`
Expected: no `kg/` change after the second run.

- [ ] **Step 2: All validators + verifiers exit 0**

Run:
```bash
for v in validate_kg validate_cost verify_item_families verify_charge_recipes verify_degrade_paths verify_repair_paths verify_equipment_bonuses verify_map verify_storeline; do ./venv/bin/python data/$v.py >/dev/null 2>&1 && echo "$v=0" || echo "$v=FAIL"; done
```
Expected: every line `=0`. (Crucially `validate_cost=0` — no price tokens leaked.)

- [ ] **Step 3: Full test suite**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 4: Spot-check the win**

Run: `./venv/bin/python data/verify_storeline.py`
Expected: `STORELINE VERIFICATION PASSED`; `shops covered by Storeline: 13/15`; the only residual lines are Varrock Apothecary's potion categories (dialogue-shop). Confirm Lowe's/Aubury/General Store now carry exact stock and the 27 categories are gone except the 2 Apothecary potions.

- [ ] **Step 5: Commit (if any verification touched tracked files — otherwise skip)**

```bash
git status --porcelain   # expect clean; the graph was already committed in Task 6
```

---

## Notes for the executor

- **The seeded rekey (Task 6) is the highest-risk step.** If the global edge-id assert raises, confirm `edge_index_seed=_prior_src_counts` is passed to `build_storeline`'s `rekey` and that the wiring sits AFTER the `build_map` block (so `edges` already contains the map's `located_in` edges when the seed is computed).
- **Item ids in tests** (`item:1391` Battlestaff, `item:6814` Fur, `item:1381` Staff of air): verify against the committed `item_dictionary.json` during implementation; correct if any differ.
- **Network** is needed only for Task 1's fetch; every test runs offline against the committed snapshot + graph.
- **Task 5 is owner-gated** — do not apply the `varrock.json` edit without the owner's explicit approval of the before→after.
