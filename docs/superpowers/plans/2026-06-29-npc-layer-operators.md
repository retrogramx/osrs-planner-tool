# NPC Layer (shop operators) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the shop operators — each distinct `owner` NPC from the shop brick becomes an `npc:` node,
`located_in` a skeleton place via a new npc-infobox brick, with `operates` edges to its shops — closing the shop
layer's deferred operators and resolving its 14 multi-location shops.

**Architecture:** A new builder `kg_ingest/builders/npcs.py` (`build_npcs`) consumes the shop brick's `owner`
field (the operator roster + shop→npc mapping) and a NEW `wiki_npc_infoboxes.json` (each operator's
`{{Infobox NPC}}` location). It emits `npc` nodes + `located_in` + `operates`, wired into `assemble.py` after
`build_shops` with an npc-`src` seeded `rekey`. Mirrors the shop layer; reuses its parenting helpers verbatim.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON graph; pytest. Reuses
`kg_ingest.builders.shops` (`build_place_name_index`, `resolve_shop_places`, `shop_roster`), `storeline`
(`match_shop`), `world` (`parse_infobox_links`, `_norm`), `ids` (`slugify`, `_stable_hash`).

## Global Constraints

- **Never fabricate.** Operator names come from the shop brick `owner` field verbatim; the npc-infobox brick is
  the NPC filter (no `{{Infobox NPC}}` → not an npc node); unparented/unresolved → reported, never invented.
- **Zero schema changes.** `npc` / `operates` / `located_in (npc→place)` are all live; `role`/`members`/`aliases`
  left unset; npc ids are slugs (`npc:<slug>`).
- **`operates` edge is the single source of truth;** `shop.operator` is NOT backfilled (D3).
- **Byte-stable** assemble; the committed-kg golden test stays green; all validators/verifiers exit 0.
- **Multi-location resolution via operators, no role node** (D4). NPC `located_in` reuses the shop layer's
  `1/>1/0` rule (`>1 → multi_location: true`, no edge; `0 → FLAG`).

## File Structure

- `data/fetch_shop_infoboxes.py` (MODIFY, 1 line) — generalize `extract_infobox_block(wikitext, infobox_name=...)`
  so the npc brick can reuse it for `{{Infobox NPC}}` (backward-compatible default; shop snapshot unchanged).
- `kg_ingest/builders/npcs.py` (NEW) — `operator_map`/`operator_roster` (roster helpers) + `build_npcs`.
- `data/fetch_npc_infoboxes.py` (NEW) — fetch each operator's `{{Infobox NPC}}` location.
- `data/raw/wiki_npc_infoboxes.json` (NEW, committed) — `{title: {locations, is_npc, source_url}}`.
- `data/verify_npcs.py` (NEW) — source-grounding gate. `data/verify_npc_coverage.py` (NEW) — completeness gate.
- `kg_ingest/assemble.py` (MODIFY) — load the npc brick; call `build_npcs` after `build_shops`; seeded rekey.
- `kg/competency_questions.json` (MODIFY) — operator competency questions.

---

### Task 1: npc-infobox brick (roster helpers + fetch + committed snapshot)

**Files:**
- Modify: `data/fetch_shop_infoboxes.py` (the `extract_infobox_block` signature)
- Create: `kg_ingest/builders/npcs.py` (roster helpers only this task), `data/fetch_npc_infoboxes.py`
- Create (committed): `data/raw/wiki_npc_infoboxes.json`
- Test: `tests/kg_ingest/test_npc_roster.py`, `tests/kg_ingest/test_npc_snapshot.py`

**Interfaces:**
- Produces: `operator_map(storeline_records, shop_infoboxes, varrock_shop_names) -> dict[str, list[str]]`
  (`{shop_name: [operator NPC page-names]}`, distinct+ordered, derived roster only);
  `operator_roster(storeline_records, shop_infoboxes, varrock_shop_names) -> list[str]` (sorted distinct
  operator page-names). Snapshot `wiki_npc_infoboxes.json` = `{"_provenance": {...}, "infoboxes":
  {title: {"locations": [str], "is_npc": bool, "source_url": str}}}`.

- [ ] **Step 1: Write failing roster-helper tests**

`tests/kg_ingest/test_npc_roster.py`:
```python
from kg_ingest.builders.npcs import operator_map, operator_roster

# Storeline gives the derived roster; the shop brick owner field gives the operators.
RECS = [{"sold_by": "Al Kharid General Store", "sold_item": "Pot"},
        {"sold_by": "Slayer Rewards", "sold_item": "Broad bolts"},
        {"sold_by": "Varrock General Store", "sold_item": "Pot"}]  # Varrock -> excluded
SHOP_IB = {
    "Al Kharid General Store": {"owner": ["[[Shop keeper (Al Kharid)|Shop keeper]]"]},
    "Slayer Rewards": {"owner": ["[[Turael]]", "[[Spria]]"]},          # multi-owner
    "Varrock General Store": {"owner": ["[[Shop keeper]]"]},
}
VARROCK = {"Varrock General Store"}

def test_operator_map_parses_owner_links_derived_only():
    m = operator_map(RECS, SHOP_IB, VARROCK)
    assert m["Al Kharid General Store"] == ["Shop keeper (Al Kharid)"]   # link target, not display
    assert m["Slayer Rewards"] == ["Turael", "Spria"]                   # multi-owner, ordered
    assert "Varrock General Store" not in m                             # Varrock excluded

def test_operator_roster_is_sorted_distinct():
    assert operator_roster(RECS, SHOP_IB, VARROCK) == ["Shop keeper (Al Kharid)", "Spria", "Turael"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npc_roster.py -q` → FAIL (module not defined).

- [ ] **Step 3: Create `kg_ingest/builders/npcs.py` with the roster helpers**

```python
"""build_npcs — the operator layer (shop operators).

Roster = the distinct `owner` NPCs the shop brick captured over the derived shop
roster (Storeline minus Varrock). Each operator -> an npc: node (NO role: the
operates edge + the shop's shop_type encode it relationally), located_in a skeleton
place via its {{Infobox NPC}} location, with operates edges to the shops it runs.
The npc-infobox brick is the NPC filter (no infobox -> not an npc). Operators close
the shop layer's deferred operates AND its multi-location shops (the slayer masters
operate Slayer Rewards). Edges are npc-src -> assemble re-keys them in their OWN
seeded call. Never fabricates.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, slugify
from kg_ingest.builders.storeline import match_shop
from kg_ingest.builders.world import parse_infobox_links
from kg_ingest.builders.shops import shop_roster, build_place_name_index, resolve_shop_places, _shop_slug

_EDGE_BAND = 0xF0000000        # npc-src; cosmetic — rekey replaces it


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _npc_slug(name: str) -> str:
    return "npc:" + slugify(name)


def operator_map(storeline_records, shop_infoboxes, varrock_shop_names):
    """{shop_name: [operator NPC page-names]} over the derived roster (Storeline minus Varrock),
    parsed from each shop's brick `owner` field (link TARGETS, distinct + ordered). Shops with no
    owner are omitted."""
    titles = list(shop_infoboxes)
    out: dict[str, list[str]] = {}
    for name in shop_roster(storeline_records, varrock_shop_names):
        t = match_shop(name, titles)
        owner = (shop_infoboxes.get(t) or {}).get("owner") if t else None
        if not owner:
            continue
        npcs: list[str] = []
        for raw in owner:
            for tgt in parse_infobox_links(raw):
                if tgt not in npcs:
                    npcs.append(tgt)
        if npcs:
            out[name] = npcs
    return out


def operator_roster(storeline_records, shop_infoboxes, varrock_shop_names):
    """Sorted distinct operator NPC page-names across the derived roster (the npc-fetch page list)."""
    m = operator_map(storeline_records, shop_infoboxes, varrock_shop_names)
    return sorted({npc for npcs in m.values() for npc in npcs})
```

- [ ] **Step 4: Run roster tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npc_roster.py -q` → PASS (2 passed).

- [ ] **Step 5: Generalize the shop brick's block extractor (1-line, backward-compatible)**

In `data/fetch_shop_infoboxes.py`, change `extract_infobox_block` to accept the infobox name (default keeps the
shop behavior verbatim):
```python
def extract_infobox_block(wikitext, infobox_name="Infobox Shop"):
    """Return the {{<infobox_name> ...}} block (brace-depth counted so nested {{...}} are kept), or ''."""
    m = re.search(r"\{\{" + re.escape(infobox_name) + r"\b", wikitext or "", re.IGNORECASE)
    if not m:
        return ""
    i, depth = m.start(), 0
    while i < len(wikitext):
        if wikitext[i:i + 2] == "{{":
            depth += 1; i += 2; continue
        if wikitext[i:i + 2] == "}}":
            depth -= 1; i += 2
            if depth == 0:
                return wikitext[m.start():i]
            continue
        i += 1
    return wikitext[m.start():]
```
Verify the shop brick is unaffected: `./venv/bin/python -m pytest tests/data/test_fetch_shop_infoboxes.py -q` → still PASS (the default reproduces the old behavior).

- [ ] **Step 6: Create `data/fetch_npc_infoboxes.py`**

```python
#!/usr/bin/env python3
"""Fetch each shop-operator NPC's {{Infobox NPC}} location (verbatim) for the operator layer.
Roster = the distinct owner NPCs the shop brick captured. Deterministic + sorted. Verbatim — no
inference. Source: OSRS Wiki (CC BY-NC-SA). Run: ./venv/bin/python data/fetch_npc_infoboxes.py
"""
import importlib.util, json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
WIKI = "https://oldschool.runescape.wiki/w/"

# Reuse the shop brick's pure parsers (split + location list); load it by path (no package import).
_spec = importlib.util.spec_from_file_location("fetch_shop_infoboxes", os.path.join(HERE, "fetch_shop_infoboxes.py"))
_fsi = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_fsi)
extract_infobox_block = _fsi.extract_infobox_block
split_top_level_params = _fsi.split_top_level_params
shop_locations = _fsi.shop_locations            # generic: |location= + |location1..N=

import sys
sys.path.insert(0, ROOT)                          # for kg_ingest + the committed snapshots
from kg_ingest.builders.npcs import operator_roster   # noqa: E402


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def main():
    os.makedirs(RAW, exist_ok=True)
    storeline = json.load(open(os.path.join(RAW, "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    shop_ib = json.load(open(os.path.join(RAW, "wiki_shop_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    varrock = {s["name"] for s in json.load(open(os.path.join(HERE, "map", "varrock.json"), encoding="utf-8"))["shops"]}
    titles = operator_roster(storeline, shop_ib, varrock)

    infoboxes = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        d = _api({"action": "query", "titles": "|".join(batch), "prop": "revisions",
                  "rvprop": "content", "rvslots": "main", "redirects": 1})
        pages = d.get("query", {}).get("pages", {})
        for pg in pages.values():
            title = pg["title"]
            revs = pg.get("revisions", [])
            wt = revs[0]["slots"]["main"]["*"] if revs else ""
            block = extract_infobox_block(wt, "Infobox NPC")
            params = split_top_level_params(block) if block else {}
            infoboxes[title] = {"locations": shop_locations(params), "is_npc": bool(block),
                                "source_url": WIKI + title.replace(" ", "_")}
        time.sleep(0.1)
    with open(os.path.join(RAW, "wiki_npc_infoboxes.json"), "w", encoding="utf-8") as f:
        json.dump({"_provenance": {"domain": "wiki_npc_infoboxes", "source": "OSRS Wiki revisions API",
                                   "license": "CC BY-NC-SA 3.0", "param": "Infobox NPC|location"},
                   "infoboxes": dict(sorted(infoboxes.items()))}, f, ensure_ascii=False, indent=1)
    print(f"DONE: {len(titles)} operators, {sum(1 for v in infoboxes.values() if v['is_npc'])} with an NPC infobox, "
          f"{sum(1 for v in infoboxes.values() if v['locations'])} with a location")


if __name__ == "__main__":
    main()
```

> **Network note:** the fetch needs network. If unavailable, STOP with `NEEDS_CONTEXT` and the controller runs it.

- [ ] **Step 7: Materialize the committed snapshot**

Run: `./venv/bin/python data/fetch_npc_infoboxes.py` → prints `DONE: <N> operators, <M> with an NPC infobox, <K> with a location`.

- [ ] **Step 8: Write + run the snapshot shape test**

`tests/kg_ingest/test_npc_snapshot.py`:
```python
import json, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

def test_npc_infobox_snapshot_shape():
    d = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_npc_infoboxes.json"), encoding="utf-8"))
    assert "_provenance" in d and "infoboxes" in d
    assert d["infoboxes"] == dict(sorted(d["infoboxes"].items()))
    sample = next(iter(d["infoboxes"].values()))
    assert set(sample) >= {"locations", "is_npc", "source_url"}
    assert any(v["is_npc"] for v in d["infoboxes"].values())   # some operators are real NPCs
```
Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npc_snapshot.py -q` → PASS.

- [ ] **Step 9: Commit**

```bash
git add data/fetch_shop_infoboxes.py kg_ingest/builders/npcs.py data/fetch_npc_infoboxes.py \
        data/raw/wiki_npc_infoboxes.json tests/kg_ingest/test_npc_roster.py tests/kg_ingest/test_npc_snapshot.py
git commit -m "feat(npc-layer): operator roster helpers + npc-infobox brick"
```

---

### Task 2: `build_npcs` roster + node emission (no edges yet)

**Files:**
- Modify: `kg_ingest/builders/npcs.py`
- Test: `tests/kg_ingest/test_npcs_builder.py`

**Interfaces:**
- Produces: `build_npcs(storeline_records, shop_infoboxes, npc_infoboxes, place_nodes, varrock_npc_names) ->
  (nodes: list[Node], edges: list[Edge], groups: dict)`. This task emits **nodes only** (`located_in` Task 3,
  `operates` Task 4 → `edges` stays `[]`). An operator becomes an npc node iff it has an `{{Infobox NPC}}`
  (`npc_infoboxes[name]["is_npc"]`); minus `varrock_npc_names` (`extra_seen`). No `role`.

- [ ] **Step 1: Write failing tests**

`tests/kg_ingest/test_npcs_builder.py`:
```python
from kg_ingest.builders.npcs import _npc_slug, build_npcs
from osrs_planner.engine.kg.model import NodeKind

RECS = [{"sold_by": "Al Kharid General Store"}, {"sold_by": "Mystic Shop"}]
SHOP_IB = {"Al Kharid General Store": {"owner": ["[[Shop keeper (Al Kharid)|Shop keeper]]"]},
           "Mystic Shop": {"owner": ["[[Sins of the Father]]"]}}   # a QUEST mis-linked as owner
NPC_IB = {"Shop keeper (Al Kharid)": {"locations": ["[[Al Kharid]]"], "is_npc": True},
          "Sins of the Father": {"locations": [], "is_npc": False}}  # no NPC infobox -> not an npc

def test_npc_slug():
    assert _npc_slug("Shop keeper (Al Kharid)") == "npc:shop-keeper-al-kharid"

def test_build_npcs_emits_node_for_real_npc_only():
    nodes, edges, groups = build_npcs(RECS, SHOP_IB, NPC_IB, [], set(), set())
    ids = {n.id for n in nodes}
    assert "npc:shop-keeper-al-kharid" in ids
    assert "npc:sins-of-the-father" not in ids        # quest, no NPC infobox -> filtered, never fabricated
    n = next(n for n in nodes if n.id == "npc:shop-keeper-al-kharid")
    assert n.kind is NodeKind.NPC
    assert "role" not in n.data                        # role left unset (D2)
    assert edges == [] and groups == {}

def test_varrock_npcs_excluded():
    npc_ib = {"Aubury": {"locations": ["[[Varrock]]"], "is_npc": True}}
    recs = [{"sold_by": "Aubury's Rune Shop"}]
    shop_ib = {"Aubury's Rune Shop": {"owner": ["[[Aubury]]"]}}
    nodes, _, _ = build_npcs(recs, shop_ib, npc_ib, [], set(), {"Aubury"})
    assert nodes == []                                 # Aubury is a Varrock npc (build_map owns it)
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npcs_builder.py -q` → FAIL (`build_npcs`/`_npc_slug` not defined — `_npc_slug` exists from Task 1; `build_npcs` does not).

- [ ] **Step 3: Implement `build_npcs` (nodes only) in `kg_ingest/builders/npcs.py`**

```python
def build_npcs(storeline_records, shop_infoboxes, npc_infoboxes, place_nodes,
               varrock_shop_names, varrock_npc_names):
    """Operator npcs. varrock_shop_names excludes Varrock shops from the roster (via operator_map);
    varrock_npc_names excludes the 15 hand-authored Varrock npcs (build_map owns them)."""
    nodes: list[Node] = []
    edges: list[Edge] = []                     # located_in (Task 3) + operates (Task 4) land here
    roster = operator_roster(storeline_records, shop_infoboxes, varrock_shop_names)

    claimed: dict[str, str] = {}               # slug -> first name (collision guard)
    for name in roster:
        ib = npc_infoboxes.get(name)
        if not ib or not ib.get("is_npc"):
            continue                           # owner link with no {{Infobox NPC}} (quest/item) -> not an npc
        if name in varrock_npc_names:
            continue                           # build_map owns the Varrock npcs
        nid = _npc_slug(name)
        if nid in claimed:                     # distinct names, same slug -> NEVER silently merge
            k = 2
            while f"{nid}-{k}" in claimed:
                k += 1
            print(f"[npcs] slug collision: {name!r} and {claimed[nid]!r} -> {nid}; using {nid}-{k}")
            nid = f"{nid}-{k}"
        claimed[nid] = name
        nodes.append(Node(id=nid, kind=NodeKind.NPC, name=name, slug=nid.split(":", 1)[1], data={}))

    return nodes, edges, {}
```
The final signature is `build_npcs(storeline_records, shop_infoboxes, npc_infoboxes, place_nodes,
varrock_shop_names, varrock_npc_names)` — used verbatim in Tasks 3, 4, and 6.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npcs_builder.py tests/kg_ingest/test_npc_roster.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/npcs.py tests/kg_ingest/test_npcs_builder.py
git commit -m "feat(npc-layer): build_npcs roster + node emission (is_npc filter, collision guard, no role)"
```

---

### Task 3: Parenting + multi-location (reuse the shop machinery)

**Files:**
- Modify: `kg_ingest/builders/npcs.py`
- Test: `tests/kg_ingest/test_npcs_parenting.py`

**Interfaces:**
- Consumes: `shops.build_place_name_index`, `shops.resolve_shop_places` (already imported). `build_npcs` now
  emits a `located_in` edge for a single-location npc; `>1` → `data["multi_location"] = True` (no edge); `0` → FLAG.

- [ ] **Step 1: Write failing tests**

`tests/kg_ingest/test_npcs_parenting.py`:
```python
from kg_ingest.builders.npcs import build_npcs
from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType

PLACES = [Node(id="place:al-kharid", kind=NodeKind.PLACE, name="Al Kharid", slug="al-kharid", data={}),
          Node(id="place:burthorpe", kind=NodeKind.PLACE, name="Burthorpe", slug="burthorpe", data={})]

def _loc(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}

def _build(name, locations):
    recs = [{"sold_by": "S"}]
    shop_ib = {"S": {"owner": [f"[[{name}]]"]}}
    npc_ib = {name: {"locations": locations, "is_npc": True}}
    return build_npcs(recs, shop_ib, npc_ib, PLACES, set(), set())

def test_single_location_emits_located_in():
    nodes, edges, _ = _build("Ali the Kebab seller", ["[[Al Kharid]]"])
    assert ("npc:ali-the-kebab-seller", "place:al-kharid") in _loc(edges)

def test_multi_location_defers_no_edge_flag():
    nodes, edges, _ = _build("Wanderer", ["[[Al Kharid]]", "[[Burthorpe]]"])
    assert _loc(edges) == set()
    assert next(n for n in nodes if n.id == "npc:wanderer").data["multi_location"] is True

def test_zero_resolution_flag_no_edge():
    nodes, edges, _ = _build("Ghost", ["[[Nowhere]]"])
    assert _loc(edges) == set()
    assert "multi_location" not in next(n for n in nodes if n.id == "npc:ghost").data
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npcs_parenting.py -q` → FAIL (no located_in emitted yet).

- [ ] **Step 3: Add parenting to `build_npcs`**

Build the name-index once before the loop (`name_index = build_place_name_index(place_nodes)`), and inside the
loop (after computing `nid`, before/at `nodes.append`) resolve + emit:
```python
        places = resolve_shop_places((ib or {}).get("locations", []), name_index)
        data = {"multi_location": True} if len(places) > 1 else {}
        nodes.append(Node(id=nid, kind=NodeKind.NPC, name=name, slug=nid.split(":", 1)[1], data=data))
        if len(places) == 1:
            edges.append(Edge(id=_edge_id(nid, "located_in"), type=EdgeType.LOCATED_IN,
                              src=nid, dst=places[0], cond_group=None, data={}))
        # len(places) == 0 -> unparented FLAG (no edge), reported by verify_npc_coverage
```
(Replace the Task-2 `nodes.append(... data={})` line with this resolve-then-append block.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npcs_parenting.py tests/kg_ingest/test_npcs_builder.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/npcs.py tests/kg_ingest/test_npcs_parenting.py
git commit -m "feat(npc-layer): npc parenting via infobox location + multi-location defer rule"
```

---

### Task 4: `operates` edges (npc → shop)

**Files:**
- Modify: `kg_ingest/builders/npcs.py`
- Test: `tests/kg_ingest/test_npcs_operates.py`

**Interfaces:**
- `build_npcs` now also emits `operates` edges (npc → `shop:<slug>`) for each shop an npc owns (from
  `operator_map`). Multi-owner shops yield one edge per operator; a single npc owning multiple shops yields one
  edge per shop. dst = `_shop_slug(shop_name)` (the committed shop node id).

- [ ] **Step 1: Write failing tests**

`tests/kg_ingest/test_npcs_operates.py`:
```python
from kg_ingest.builders.npcs import build_npcs
from osrs_planner.engine.kg.model import EdgeType

RECS = [{"sold_by": "Slayer Rewards"}, {"sold_by": "Al Kharid General Store"}]
SHOP_IB = {"Slayer Rewards": {"owner": ["[[Turael]]", "[[Spria]]"]},
           "Al Kharid General Store": {"owner": ["[[Shop keeper (Al Kharid)|Shop keeper]]"]}}
NPC_IB = {"Turael": {"locations": ["[[Burthorpe]]"], "is_npc": True},
          "Spria": {"locations": ["[[Draynor Village]]"], "is_npc": True},
          "Shop keeper (Al Kharid)": {"locations": ["[[Al Kharid]]"], "is_npc": True}}

def _ops(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.OPERATES}

def test_operates_edges_npc_to_shop():
    nodes, edges, _ = build_npcs(RECS, SHOP_IB, NPC_IB, [], set(), set())
    o = _ops(edges)
    assert ("npc:turael", "shop:slayer-rewards") in o
    assert ("npc:spria", "shop:slayer-rewards") in o           # multi-owner -> one edge per master
    assert ("npc:shop-keeper-al-kharid", "shop:al-kharid-general-store") in o

def test_operates_dst_is_shop_id():
    nodes, edges, _ = build_npcs(RECS, SHOP_IB, NPC_IB, [], set(), set())
    assert all(e.dst.startswith("shop:") for e in edges if e.type is EdgeType.OPERATES)
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npcs_operates.py -q` → FAIL (no operates edges yet).

- [ ] **Step 3: Add `operates` emission to `build_npcs`**

Before the loop, invert `operator_map` to `{npc_name: [shop_names]}`:
```python
    op_map = operator_map(storeline_records, shop_infoboxes, varrock_shop_names)
    npc_to_shops: dict[str, list[str]] = {}
    for shop_name, npcs in op_map.items():
        for npc in npcs:
            npc_to_shops.setdefault(npc, []).append(shop_name)
```
Inside the loop, after the `located_in` block, emit operates for the shops this npc runs:
```python
        for j, shop_name in enumerate(npc_to_shops.get(name, [])):
            edges.append(Edge(id=_edge_id(nid, f"op#{j}"), type=EdgeType.OPERATES,
                              src=nid, dst=_shop_slug(shop_name), cond_group=None, data={}))
```
(`op_map` here uses the builder's `varrock_shop_names` param — the same value the Task-2 `roster` call uses.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_npcs_operates.py tests/kg_ingest/test_npcs_parenting.py tests/kg_ingest/test_npcs_builder.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/npcs.py tests/kg_ingest/test_npcs_operates.py
git commit -m "feat(npc-layer): operates edges (npc -> shop), closing the deferred operators"
```

---

### Task 5: Verifiers (source-grounding + coverage)

**Files:**
- Create: `data/verify_npcs.py`, `data/verify_npc_coverage.py`
- Test: `tests/kg_ingest/test_verify_npcs.py`

**Interfaces:**
- Read the committed `kg/nodes.json`/`kg/edges.json` + the bricks; reuse `npcs.operator_map`, `npcs._npc_slug`.
  `verify_npcs` exits 1 on structural breach (an `operates` with no backing owner; a npc `located_in` whose dst
  isn't a place node), else 0. `verify_npc_coverage` is report-not-fail (exit 0).

- [ ] **Step 1: Write a failing smoke test**

`tests/kg_ingest/test_verify_npcs.py`:
```python
import subprocess, sys, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
def _run(s): return subprocess.run([sys.executable, os.path.join(ROOT, "data", s)], capture_output=True, text=True)

def test_verify_npc_coverage_runs():
    r = _run("verify_npc_coverage.py"); assert r.returncode == 0; assert "NPC COVERAGE" in r.stdout

def test_verify_npcs_passes_on_committed_graph():
    r = _run("verify_npcs.py"); assert r.returncode == 0, r.stdout; assert "NPC VERIFICATION" in r.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_npcs.py -q` → FAIL (scripts don't exist; both go green after Task 6 wires the graph — but the scripts must exist and run now).

- [ ] **Step 3: Implement `data/verify_npcs.py`**

```python
#!/usr/bin/env python3
"""Source-grounding gate for the operator layer. HARD-FAILS (exit 1) on structural breaches: an `operates` edge
whose (npc, shop) has no backing shop-brick `owner` entry, or a derived npc `located_in` whose dst is not a
committed place node. REPORTS (exit 0 otherwise) resolution residuals (owner links with no {{Infobox NPC}}).
"""
from __future__ import annotations
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.npcs import operator_map, _npc_slug, _shop_slug   # noqa: E402

def main() -> int:
    errors = []
    storeline = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    shop_ib = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    place_ids = {n["id"] for n in nodes if n["id"].startswith("place:")}

    op_map = operator_map(storeline, shop_ib, varrock)
    # backing set of (npc_id, shop_id) the brick supports
    backing = {(_npc_slug(npc), _shop_slug(shop)) for shop, npcs in op_map.items() for npc in npcs}
    derived_npc_ids = {_npc_slug(npc) for npcs in op_map.values() for npc in npcs}

    for e in edges:
        if e.get("type") == "operates" and e["src"] in derived_npc_ids:
            if (e["src"], e["dst"]) not in backing:
                errors.append(f"[operates] {e['src']} -> {e['dst']} has no backing shop-brick owner")
        if e.get("type") == "located_in" and e["src"] in derived_npc_ids and e["dst"] not in place_ids:
            errors.append(f"[located_in] {e['src']} -> {e['dst']} dst is not a committed place node")

    if errors:
        print(f"NPC VERIFICATION FAILED — {len(errors)} violation(s):")
        for x in errors[:60]: print("  -", x)
        return 1
    print("NPC VERIFICATION PASSED — operators source-grounded.")
    print(f"  derived operator npcs: {len(derived_npc_ids)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implement `data/verify_npc_coverage.py`**

```python
#!/usr/bin/env python3
"""Operator COMPLETENESS gate (offline, report-not-fail). Of the derived shops with an owner, how many got >=1
operator npc; residual categorized {owner-not-an-npc (no {{Infobox NPC}}), npc-no-location, npc-location-unresolved}.
"""
from __future__ import annotations
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.npcs import operator_map, operator_roster, _npc_slug   # noqa: E402
from kg_ingest.builders.shops import resolve_shop_places, build_place_name_index   # noqa: E402
from osrs_planner.engine.kg.model import Node, NodeKind   # noqa: E402

def main() -> int:
    storeline = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    shop_ib = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    npc_ib = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_npc_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    place_nodes = [Node(id=n["id"], kind=NodeKind.PLACE, name=n["name"], slug=n["id"].split(":",1)[1], data={})
                   for n in nodes if n["id"].startswith("place:")]
    name_index = build_place_name_index(place_nodes)

    op_map = operator_map(storeline, shop_ib, varrock)
    roster = operator_roster(storeline, shop_ib, varrock)
    not_npc = [n for n in roster if not (npc_ib.get(n) or {}).get("is_npc")]
    npcs = [n for n in roster if (npc_ib.get(n) or {}).get("is_npc")]
    no_loc, unresolved, parented = [], [], []
    for n in npcs:
        locs = npc_ib[n]["locations"]
        if not locs: no_loc.append(n)
        elif resolve_shop_places(locs, name_index): parented.append(n)
        else: unresolved.append((n, locs))
    print("NPC COVERAGE (operators of the derived shops):")
    print(f"  shops with an owner: {len(op_map)} ; distinct operator names: {len(roster)}")
    print(f"  -> real npcs (have {{Infobox NPC}}): {len(npcs)}  | owner-not-an-npc (quest/item links): {len(not_npc)}")
    print(f"  npcs parented: {len(parented)} | no-location: {len(no_loc)} | location-unresolved: {len(unresolved)}")
    for n, locs in sorted(unresolved)[:20]:
        print(f"        location-unresolved: {n} -> {locs}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Commit (tests go green after Task 6)**

```bash
git add data/verify_npcs.py data/verify_npc_coverage.py tests/kg_ingest/test_verify_npcs.py
git commit -m "feat(npc-layer): source-grounding + coverage verifiers"
```

---

### Task 6: Assemble wiring + competency + byte-stable

**Files:**
- Modify: `kg_ingest/assemble.py`, `kg/competency_questions.json`
- Regenerate: `kg/nodes.json`, `kg/edges.json`
- Test: `tests/kg_ingest/test_assemble.py`, `tests/kg_ingest/test_competency_questions.py`, `tests/kg_ingest/test_verify_npcs.py`

- [ ] **Step 1: Add the loader + the build_npcs block to `assemble.py`**

Near the other `*_PATH` constants:
```python
NPC_INFOBOX_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "wiki_npc_infoboxes.json"
```
Loader near `_load_shop_infoboxes`:
```python
def _load_npc_infoboxes() -> dict | None:
    if not NPC_INFOBOX_PATH.exists():
        return None
    return json.loads(NPC_INFOBOX_PATH.read_text())["infoboxes"]
```
Import near `from kg_ingest.builders.shops import build_shops`:
```python
from kg_ingest.builders.npcs import build_npcs
```
Immediately AFTER the `build_shops` block (after `owned_ids = owned_ids | {n.id for n in sh_nodes}`), add the
npc block (mirrors the shop block; npc-`src` seeded rekey). `world_nodes`/`map_nodes` are in scope for place
nodes; the Varrock npc names come from `_map["npcs"]`:
```python
    # NPC operator layer: each shop owner (from the shop brick) -> an npc node, located_in via its {{Infobox NPC}},
    # operates -> its shops. Closes the deferred operators + the multi-location shops. npc-src seeded rekey.
    _npc_ib = _load_npc_infoboxes()
    if _map is not None and _shop_ib is not None and _npc_ib is not None:
        _place_nodes = [n for n in (world_nodes + map_nodes) if n.kind == NodeKind.PLACE]
        _varrock_shop_names = {s["name"] for s in _map["shops"]}
        _varrock_npc_names = {n["name"] for n in _map["npcs"]}
        npc_nodes, npc_edges, _ = build_npcs(
            _load_storeline_records(), _shop_ib, _npc_ib, _place_nodes,
            _varrock_shop_names, _varrock_npc_names)
        _seed_npc: dict[str, int] = {}
        for _e in edges:
            _seed_npc[_e.src] = _seed_npc.get(_e.src, 0) + 1
        npc_nodes, npc_edges, _ = rekey(npc_nodes, npc_edges, {}, edge_index_seed=_seed_npc)
        edges = edges + npc_edges
        owned_ids = owned_ids | {n.id for n in npc_nodes}
```
Ensure `npc_nodes` join the written node set the same way `sh_nodes`/`map_nodes` do (add to the `dedup_nodes`
accumulation — follow the exact pattern used for `sh_nodes`).

- [ ] **Step 2: Re-assemble + structural validators**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python -m kg_ingest.assemble       # twice — byte-stable
H1=$(cat kg/nodes.json kg/edges.json | md5); ./venv/bin/python -m kg_ingest.assemble >/dev/null; H2=$(cat kg/nodes.json kg/edges.json | md5)
[ "$H1" = "$H2" ] && echo BYTE-STABLE
./venv/bin/python data/validate_kg.py        # exit 0
./venv/bin/python data/validate_cost.py      # exit 0
```
Expected: byte-stable; both validators PASS (npc nodes + operates/located_in are schema-valid).

- [ ] **Step 3: Run the verifiers against the wired graph**

```bash
./venv/bin/python data/verify_npcs.py            # exit 0; "NPC VERIFICATION PASSED" + 0 structural
./venv/bin/python data/verify_npc_coverage.py    # exit 0; the categorized coverage breakdown
./venv/bin/python data/verify_shops.py           # still exit 0 (shops unchanged)
./venv/bin/python -m pytest tests/kg_ingest/test_verify_npcs.py -q   # PASS
```
If `verify_npcs` reports structural errors, fix the builder (a real bug) — never weaken the verifier.

- [ ] **Step 4: Add operator competency questions**

Pick a real operator + shop that exist post-assembly; verify each target exists and set `expect_min` the graph
satisfies. Add to `kg/competency_questions.json` `records` (add an `operated_by` method handler to
`tests/kg_ingest/test_competency_questions.py` if absent — it traverses `operates` edges into a shop, returning
its operators). Example (adjust ids/expect_min to the assembled graph — they MUST pass):
```json
{ "id": "cq-slayer-rewards-operators", "question": "Who runs the Slayer Rewards shop?",
  "method": "operated_by", "target": "shop:slayer-rewards", "expect_min": 1 },
{ "id": "cq-operator-region-chain", "question": "Where is a shop operator located?",
  "method": "region_chain", "target": "npc:<a-parented-operator>", "expect_min": 2 }
```

- [ ] **Step 5: Full suite + commit**

```bash
./venv/bin/python -m pytest tests/kg_ingest/test_assemble.py tests/kg_ingest/test_competency_questions.py -q
./venv/bin/python -m pytest -q --continue-on-collection-errors    # full suite (4 drop_rates errors pre-existing)
git add kg_ingest/assemble.py kg/competency_questions.json kg/nodes.json kg/edges.json kg_ingest/builders/npcs.py tests/kg_ingest/test_competency_questions.py
git commit -m "feat(npc-layer): wire build_npcs into assemble (seeded rekey) + operator competency"
```

---

## Self-Review (planner)

- **Spec coverage:** §4 brick → Task 1; §5 nodes/located_in/operates → Tasks 2-4; §6 multi-location resolution →
  Task 4 (operators of multi-owner shops); §8 verifiers → Task 5; §2/§9 wiring + byte-stable + competency → Task 6.
  `role` unset (D2), operates-only (D3), no role node (D4) — all honored (no role/operator/role-node code).
- **No placeholders:** every code/test step is complete. The one threading subtlety (`varrock_shop_names` vs
  `varrock_npc_names` on `build_npcs`) is spelled out in Task 2 Step 3 + Task 4 Step 3; the final signature is
  `build_npcs(storeline_records, shop_infoboxes, npc_infoboxes, place_nodes, varrock_shop_names, varrock_npc_names)`.
- **Type consistency:** reused helpers (`build_place_name_index`, `resolve_shop_places`, `shop_roster`,
  `match_shop`, `_shop_slug`) are imported with their exact committed signatures; `_npc_slug` returns `npc:<slug>`
  everywhere; operates dst is always `_shop_slug(shop_name)` (a committed shop id).
