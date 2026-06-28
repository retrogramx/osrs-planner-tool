# World Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the comprehensive location graph of Gielinor — an owner-authored geographic *backbone* plus a wiki-category *content ingest* — parented into one place hierarchy, proven complete by a coverage verifier.

**Architecture:** Two committed data sources feed one builder. `data/map/world.json` = the owner-authored geographic frame (gielinor▸continents▸oceans▸seas▸kingdoms▸regions + governance + `members` + `same_entity` bridges), drafted wiki-grounded and owner-reviewed. `data/raw/wiki_location_categories.json` = a fetched, reproducible snapshot of the IN content type-categories (Dungeons/Islands/Settlements/Minigames/Guilds/Agility/Hunter/Castles/named-Mines) + F2P/Members membership. `build_world` emits the backbone + filters/parents/types the content under it. A coverage verifier proves the graph covers every IN-category member.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; MediaWiki category API; committed JSON graph; pytest.

**Spec:** `docs/superpowers/specs/2026-06-27-world-skeleton-design.md` (read it; this plan implements it).

## Global Constraints

- Run everything via `./venv/bin/python`. Branch: continue on `feat/world-skeleton` (do NOT branch).
- **`assemble` must be byte-stable** — re-run produces identical `kg/{nodes,edges,condition_groups}.json` bytes.
- **`build_world`'s edges are place-`src`** (`located_in`/`same_entity`) — the SAME owner class as `build_map`'s `located_in`. `rekey` ids by `stable_edge_id(owner, index)` with no type component, so `build_world`'s OWN rekey call passes `edge_index_seed` = per-owner counts already in `edges`; and `build_map`'s rekey (which now runs AFTER `build_world`) must ALSO be seeded. The global edge-id assert (`assemble.py`) is the backstop. **Builder band `0x?0` for build_world edges, disjoint from map `0xE0`/storeline `0xF0`** — use `0xB0000000` (free; degrade uses `0xA0`, but that's a builder-LOCAL pre-rekey band and build_world gets its own rekey, so any free band works — `0xB0` chosen).
- **Never fabricate** — every place traces to a wiki page (`source_url`); an unresolved ruler or an unparented content place is **FLAGGED (located_in left explicit/`place:gielinor` + reported), never guessed**.
- **Verifiers report, never hard-fail, on residuals** (unparented places, missing governance, coverage gaps); structural violations hard-fail.
- **`place_type` ∈ the schema enum** (now incl. `sea`, `point_of_interest`); two-level typing = coarse `place_type` + fine `content_kind` (free string).
- **Owner-review editorial gates** (not subagent-decidable): the `world.json` backbone, the major-mines curation, and the unparented-residual re-homing. The controller pauses for these.
- Pre-existing `tests/drop_rates/` 4 collection errors are unrelated — ignore them.

## File Structure

- `kg/schema.json` (modify) — append `sea`, `point_of_interest` to `node_kinds.place.place_type_enum`; append `content_kind`, `members` to its `data_keys`.
- `data/fetch_world_locations.py` (new) — paginated category-API pull → `data/raw/wiki_location_categories.json` (committed).
- `data/map/world.json` (new, owner-authored) — the geographic backbone.
- `kg_ingest/builders/world.py` (new) — `_norm`, `place_type_for`/`content_kind_for`, `parent_for`, `build_world`.
- `data/verify_world.py` (new) — structural gate + report-not-fail residuals.
- `data/verify_world_coverage.py` (new) — offline coverage gate + `--refresh`.
- `kg_ingest/assemble.py` (modify) — wire `build_world` before `build_map`; seed both place-`src` rekeys; load helpers.
- `data/map/varrock.json` (modify) — remove the 3 backbone places (gielinor/misthalin/varrock); re-parent the kept Varrock subtree.
- `kg/competency_questions.json` + `tests/kg_ingest/test_competency_questions.py` (modify) — add `in_region` + `region_chain` CQs.
- Tests: `tests/kg_ingest/test_world_snapshot.py`, `test_world_backbone.py`, `test_world_builder.py`, `test_world_in_graph.py`, `test_verify_world.py`, `test_verify_world_coverage.py`.

---

### Task 1: Schema — add `sea` + `point_of_interest` place_types (additive)

**Files:**
- Modify: `kg/schema.json` (`node_kinds.place.place_type_enum` + `data_keys`)
- Test: `tests/kg_ingest/test_world_schema.py`

**Interfaces:**
- Produces: the `place` kind's `place_type_enum` now includes `"sea"`, `"point_of_interest"`; its `data_keys` include `"content_kind"`, `"members"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/kg_ingest/test_world_schema.py
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_place_type_enum_has_sea_and_poi():
    place = json.loads((ROOT / "kg" / "schema.json").read_text())["node_kinds"]["place"]
    assert "sea" in place["place_type_enum"]
    assert "point_of_interest" in place["place_type_enum"]
    assert "content_kind" in place["data_keys"]
    assert "members" in place["data_keys"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_schema.py -v`
Expected: FAIL (`sea` not in the enum).

- [ ] **Step 3: Edit `kg/schema.json`** — in `node_kinds.place`, append `"sea"` and `"point_of_interest"` to `place_type_enum`, and `"content_kind"` and `"members"` to `data_keys`. (Append at the end of each list; keep the existing entries + ordering.)

- [ ] **Step 4: Run to verify it passes + the model⊆schema invariant stays green**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_schema.py tests/engine/test_kg_model.py -q`
Expected: PASS. (`place_type` is a data string, not a `model.py` enum, so the model⊆schema guard is unaffected.)

- [ ] **Step 5: Confirm assemble still byte-stable (no graph change yet) + commit**

Run: `./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/` → no `kg/` change.
```bash
git add kg/schema.json tests/kg_ingest/test_world_schema.py
git commit -m "feat(kg): add sea + point_of_interest place_types (additive schema)"
```

---

### Task 2: Fetch + commit the location-category snapshot

**Files:**
- Create: `data/fetch_world_locations.py`
- Create (generated, commit): `data/raw/wiki_location_categories.json`
- Test: `tests/kg_ingest/test_world_snapshot.py`

**Interfaces:**
- Produces: `data/raw/wiki_location_categories.json` = `{"_provenance": {...}, "categories": {<IN-cat>: [titles]}, "free_to_play": [titles], "members": [titles], "page_categories": {<title>: [category names]}}`. `page_categories` carries each location page's categories (for region parentage). All lists sorted.

- [ ] **Step 1: Write the failing snapshot test**

```python
# tests/kg_ingest/test_world_snapshot.py
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_snapshot_shape():
    d = json.loads((ROOT / "data" / "raw" / "wiki_location_categories.json").read_text())
    cats = d["categories"]
    assert len(cats["Dungeons"]) >= 150          # exhaustive dungeon list
    assert "Catacombs of Kourend" in cats["Dungeons"]
    assert len(cats["Settlements"]) >= 80
    assert d["members"] and d["free_to_play"]      # F2P/Members membership pulled
    assert "page_categories" in d                  # per-page categories for parentage
    # deterministic ordering
    for lst in cats.values():
        assert lst == sorted(lst)
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_snapshot.py -v`
Expected: FAIL (file does not exist).

- [ ] **Step 3: Write `data/fetch_world_locations.py`**

```python
#!/usr/bin/env python3
"""Fetch the IN location type-categories + F2P/Members membership + each page's
categories (for parentage) from the MediaWiki category API. Deterministic + sorted.
Source: OSRS Wiki (CC BY-NC-SA). Verbatim — no inference. Run: ./venv/bin/python data/fetch_world_locations.py
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
# IN type-categories (the granularity filter; banks/scenery/NPCs/granular-mines are OUT)
IN_CATS = ["Dungeons", "Slayer dungeons", "Caves", "Raids", "Minigames", "Guilds",
           "Agility courses", "Hunter areas", "Castles", "Settlements", "Islands", "Mines"]
ACCESS = ["Free-to-play locations", "Members' locations"]


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def members(cat):
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": f"Category:{cat}", "cmlimit": "500", "cmtype": "page"}
        if cont:
            p["cmcontinue"] = cont
        d = _api(p)
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", []) if m["ns"] == 0]
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        time.sleep(0.1)
    return sorted(out)


def main():
    os.makedirs(RAW, exist_ok=True)
    cats = {c: members(c) for c in IN_CATS}
    access = {c: members(c) for c in ACCESS}
    titles = sorted({t for lst in cats.values() for t in lst})
    # each page's categories (batched 50) for region parentage
    page_cats = {}
    for i in range(0, len(titles), 50):
        d = _api({"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "categories", "cllimit": "500"})
        for pg in d.get("query", {}).get("pages", {}).values():
            page_cats[pg["title"]] = sorted(c["title"].replace("Category:", "") for c in pg.get("categories", []))
        time.sleep(0.08)
    out = {"_provenance": {"domain": "wiki_location_categories", "source": "OSRS Wiki category API",
                           "license": "CC BY-NC-SA 3.0", "in_categories": IN_CATS, "counts": {c: len(v) for c, v in cats.items()}},
           "categories": cats, "free_to_play": access["Free-to-play locations"],
           "members": access["Members' locations"], "page_categories": dict(sorted(page_cats.items()))}
    with open(os.path.join(RAW, "wiki_location_categories.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DONE:", {c: len(v) for c, v in cats.items()}, "| pages:", len(titles))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the fetch (network) + commit the snapshot**

Run: `./venv/bin/python data/fetch_world_locations.py`
Expected: prints counts (`Dungeons: ~177 …`) + page count; writes `data/raw/wiki_location_categories.json`. (Network required; the env reaches the wiki — confirmed in brainstorm. If blocked, run on a connected machine + commit the file.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_snapshot.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add data/fetch_world_locations.py data/raw/wiki_location_categories.json tests/kg_ingest/test_world_snapshot.py
git commit -m "feat(data): fetch + commit wiki location-category snapshot (IN cats + F2P/Members + page categories)"
```

---

### Task 3: The owner-authored geographic backbone `world.json` — OWNER REVIEW CHECKPOINT

**Files:**
- Create: `data/map/world.json`
- Test: `tests/kg_ingest/test_world_backbone.py`

**This task produces owner-authored editorial data — gated by owner review.** The controller drafts `world.json` from the brainstorm-verified geographic data (continents/oceans/seas/kingdoms/regions, wiki-grounded with `source_url`s, `ruled_by`/`faction`/`members`) and presents it to the owner for sign-off (the visual tree from the brainstorm is the review medium). Do NOT hand a subagent free rein to author owner geography — the controller assembles it from the grounded brainstorm data.

**Interfaces:**
- Produces: `data/map/world.json` = `{"places": [ {id, place_type, name, located_in, ruled_by?, faction?, members?, source_url, same_entity?} ]}`. The geographic FRAME only (no content sites): `place:gielinor` (root, `located_in:""`) ▸ `mainland`/`zeah` (continent) + the 9 oceans ▸ ~110 seas (under oceans) + ~15 kingdoms + ~15 regions ▸ (capitals/cities may be here or come via the Settlements ingest — keep cities that are kingdom CAPITALS here). `place:misthalin` `located_in: place:mainland`; `place:varrock` `located_in: place:misthalin`; `place:gielinor` present. `same_entity` set on places with a legacy `region:` match.

- [ ] **Step 1: Write the failing structural test**

```python
# tests/kg_ingest/test_world_backbone.py
import json, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_backbone_is_a_connected_single_root_tree():
    places = json.loads((ROOT / "data" / "map" / "world.json").read_text())["places"]
    ids = {p["id"] for p in places}
    roots = [p for p in places if not p.get("located_in")]
    assert [r["id"] for r in roots] == ["place:gielinor"]          # exactly one root
    assert json.dumps(places)                                       # valid json
    # every located_in resolves within the backbone
    for p in places:
        if p["id"] != "place:gielinor":
            assert p["located_in"] in ids, f"{p['id']} -> {p['located_in']} dangling"
    # the integration anchors + the re-parent
    by = {p["id"]: p for p in places}
    assert by["place:misthalin"]["located_in"] == "place:mainland"
    assert by["place:varrock"]["located_in"] == "place:misthalin"
    # every place is wiki-sourced + has a place_type in the enum
    enum = set(json.loads((ROOT / "kg" / "schema.json").read_text())["node_kinds"]["place"]["place_type_enum"])
    for p in places:
        assert p["source_url"].startswith("https://oldschool.runescape.wiki/")
        assert p["place_type"] in enum
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_backbone.py -v`
Expected: FAIL (`world.json` does not exist).

- [ ] **Step 3: Author `data/map/world.json`** (controller, from the brainstorm-grounded geographic data; owner-reviewed). Include `place:gielinor` (root) + continents (`mainland`, `zeah`) + the 9 oceans + the seas (under their ocean) + kingdoms (under continent/ocean) + regions + kingdom capitals, each with `place_type`, `name`, `located_in`, `source_url`, and `ruled_by`/`faction`/`members` where known (`""`/omit where unknown — never guessed). Set `same_entity` (e.g. `"region:varrock"`) where a legacy region node matches. **Present the result to the owner for sign-off before proceeding.**

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_backbone.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data/map/world.json tests/kg_ingest/test_world_backbone.py
git commit -m "data(map): owner-authored world.json geographic backbone (owner-reviewed)"
```

---

### Task 4: `build_world` typing + parenting helpers

**Files:**
- Create: `kg_ingest/builders/world.py` (helpers; `build_world` added in Task 5)
- Test: `tests/kg_ingest/test_world_builder.py`

**Interfaces:**
- Produces: `_norm(s) -> str`; `IN_TYPE` (priority list of `(category, place_type, content_kind)`); `classify(page_categories: set) -> (place_type, content_kind) | None`; `parent_for(title, page_categories, name_to_id) -> (parent_id, flagged: bool)`; `members_of(title, fpts, mbrs) -> bool|None`. Band consts `_EDGE_BAND=0xB0000000`.

- [ ] **Step 1: Write the failing helper tests**

```python
# tests/kg_ingest/test_world_builder.py
from kg_ingest.builders.world import _norm, classify, parent_for, members_of

def test_classify_priority():
    assert classify({"Raids", "Dungeons"}) == ("dungeon", "raid")          # raid beats dungeon
    assert classify({"Dungeons"}) == ("dungeon", "dungeon")
    assert classify({"Guilds"}) == ("point_of_interest", "guild")          # guild -> POI
    assert classify({"Minigames"}) == ("point_of_interest", "minigame")
    assert classify({"Settlements"}) == ("settlement", "settlement")
    assert classify({"Banks"}) is None                                     # OUT category -> not a place

def test_parent_region_category_then_name_heuristic():
    name2id = {"kandarin": "place:kandarin", "brimhaven": "place:brimhaven"}
    # region-category match (deepest)
    pid, flag = parent_for("Catacombs of Kourend", {"Kandarin"}, name2id)
    assert pid == "place:kandarin" and not flag
    # name-suffix fallback: "Brimhaven Dungeon" -> Brimhaven
    pid, flag = parent_for("Brimhaven Dungeon", {"Caves"}, name2id)
    assert pid == "place:brimhaven" and not flag
    # nothing matches -> flagged, parent gielinor
    pid, flag = parent_for("Mystery Spot", set(), name2id)
    assert pid == "place:gielinor" and flag

def test_members_flag():
    assert members_of("Lletya", {"Catherby"}, {"Lletya"}) is True
    assert members_of("Lumbridge", {"Lumbridge"}, {"Darkmeyer"}) is False
    assert members_of("Nowhere", {"X"}, {"Y"}) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_builder.py -v`
Expected: FAIL (`ModuleNotFoundError: kg_ingest.builders.world`).

- [ ] **Step 3: Write the helpers in `kg_ingest/builders/world.py`**

```python
"""build_world — the comprehensive location graph (world skeleton).

Reads data/map/world.json (owner-authored geographic backbone) + the committed
wiki location-category snapshot, filters by the IN/OUT granularity rule, types each
place (coarse place_type + fine content_kind), parents it (region-category ->
name-heuristic -> FLAG), and emits place nodes + located_in + same_entity. Edges are
place-src -> assemble re-keys them in their OWN seeded call. Never fabricates.
"""
from __future__ import annotations

import re

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash

_EDGE_BAND = 0xB0000000


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s*\(.*?\)\s*$", "", s.lower()))


# priority-ordered IN type-categories -> (place_type, content_kind). First match wins.
IN_TYPE = [("Raids", "dungeon", "raid"), ("Slayer dungeons", "dungeon", "slayer dungeon"),
           ("Dungeons", "dungeon", "dungeon"), ("Caves", "dungeon", "cave"),
           ("Minigames", "point_of_interest", "minigame"), ("Guilds", "point_of_interest", "guild"),
           ("Agility courses", "point_of_interest", "agility course"), ("Hunter areas", "point_of_interest", "hunter area"),
           ("Castles", "point_of_interest", "castle"), ("Mines", "point_of_interest", "mine"),
           ("Islands", "island", "island"), ("Settlements", "settlement", "settlement")]


def classify(page_categories):
    for cat, pt, ck in IN_TYPE:
        if cat in page_categories:
            return (pt, ck)
    return None


def parent_for(title, page_categories, name_to_id):
    # (1) a backbone place whose name is among the page's region/area categories.
    # name_to_id is built deepest-wins (Task 5) so a name resolves to its deepest id;
    # sorted() makes the pick deterministic when a page sits in several region categories.
    cands = [name_to_id[_norm(c)] for c in sorted(page_categories) if _norm(c) in name_to_id]
    if cands:
        return (cands[0], False)
    # (2) name minus a type suffix -> match a backbone place
    base = re.sub(r"\b(dungeon|caves?|mine|lair|tunnels?|cellar|crypt|vault)\b.*$", "", title.lower())
    base = re.sub(r"\s*\(.*?\)\s*$", "", base).strip()
    if _norm(base) and _norm(base) in name_to_id:
        return (name_to_id[_norm(base)], False)
    # (3) unresolved -> FLAG (never guess)
    return ("place:gielinor", True)


def members_of(title, fpts, mbrs):
    if title in mbrs:
        return True
    if title in fpts:
        return False
    return None
```

(Note: Task 5 passes a `name_to_id` already ordered so the *deepest* match is first; the simple `cands[0]` then yields the deepest. The plan's Task 5 builds that ordering.)

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_builder.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/world.py tests/kg_ingest/test_world_builder.py
git commit -m "feat(kg): build_world helpers — IN/OUT classify + region/name parenting + members"
```

---

### Task 5: `build_world` — backbone + content ingest → place nodes/edges

**Files:**
- Modify: `kg_ingest/builders/world.py` (add `build_world`)
- Test: `tests/kg_ingest/test_world_builder.py` (add builder tests)

**Interfaces:**
- Consumes: `classify`/`parent_for`/`members_of`/`_edge_id` (Task 4).
- Produces: `build_world(backbone: dict, snapshot: dict, region_ids: set[str]) -> tuple[list[Node], list[Edge], dict]`. `nodes` = backbone places + ingested content places; `edges` = `located_in` (place-`src`) + `same_entity` (place-`src`); groups `{}`.

- [ ] **Step 1: Write the failing builder tests**

```python
# add to tests/kg_ingest/test_world_builder.py
from kg_ingest.builders.world import build_world
from osrs_planner.engine.kg.model import EdgeType

BACKBONE = {"places": [
    {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": "",
     "source_url": "https://oldschool.runescape.wiki/w/Gielinor"},
    {"id": "place:mainland", "place_type": "continent", "name": "Mainland", "located_in": "place:gielinor",
     "source_url": "https://oldschool.runescape.wiki/w/Gielinor"},
    {"id": "place:kandarin", "place_type": "kingdom", "name": "Kandarin", "located_in": "place:mainland",
     "ruled_by": "King Lathas", "members": True, "source_url": "https://oldschool.runescape.wiki/w/Kandarin",
     "same_entity": "region:kandarin"},
    {"id": "place:brimhaven", "place_type": "town", "name": "Brimhaven", "located_in": "place:kandarin",
     "source_url": "https://oldschool.runescape.wiki/w/Brimhaven"},
]}
SNAP = {"categories": {"Dungeons": ["Brimhaven Dungeon", "Catacombs of Kourend"], "Banks": ["Brimhaven bank"]},
        "free_to_play": [], "members": ["Brimhaven Dungeon", "Catacombs of Kourend"],
        "page_categories": {"Brimhaven Dungeon": ["Dungeons", "Karamja"], "Catacombs of Kourend": ["Dungeons", "Kandarin"]}}

def test_build_world_backbone_plus_ingest():
    nodes, edges, groups = build_world(BACKBONE, SNAP, {"region:kandarin"})
    ids = {n.id for n in nodes}
    assert "place:gielinor" in ids and "place:brimhaven" in ids   # backbone emitted
    assert "place:brimhaven-dungeon" in ids                        # ingested dungeon
    assert "place:brimhaven-bank" not in ids                       # Banks is OUT
    # ingested dungeon typed + parented (name-heuristic -> Brimhaven)
    d = next(n for n in nodes if n.id == "place:brimhaven-dungeon")
    assert d.data["place_type"] == "dungeon" and d.data["content_kind"] == "dungeon"
    li = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:brimhaven-dungeon", "place:brimhaven") in li    # parented
    assert ("place:kandarin", "place:mainland") in li              # backbone located_in
    # same_entity bridge only where region node exists
    se = {(e.src, e.dst) for e in edges if e.type is EdgeType.SAME_ENTITY}
    assert ("place:kandarin", "region:kandarin") in se
    assert d.data["members"] is True                               # members flag

def test_catacombs_parents_to_kandarin_via_region_category():
    nodes, edges, groups = build_world(BACKBONE, SNAP, set())
    li = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:catacombs-of-kourend", "place:kandarin") in li
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_builder.py -k build_world -v`
Expected: FAIL (`ImportError: build_world`).

- [ ] **Step 3: Add `build_world` to `kg_ingest/builders/world.py`**

```python
def _slug(name: str) -> str:
    return "place:" + re.sub(r"[^a-z0-9]+", "-", re.sub(r"\s*\(.*?\)\s*$", "", name.lower())).strip("-")


def build_world(backbone, snapshot, region_ids):
    nodes: list[Node] = []
    edges: list[Edge] = []

    # --- backbone (owner-authored geographic frame) ---
    bb_ids = set()
    name_to_id: dict[str, str] = {}
    # order backbone deepest-last so name_to_id keeps the DEEPEST id per name (Task-4 parent_for takes cands[0])
    def _depth(p, by):
        d, cur = 0, p.get("located_in")
        while cur and cur in by and d < 12:
            d += 1; cur = by[cur].get("located_in")
        return d
    by = {p["id"]: p for p in backbone["places"]}
    for p in sorted(backbone["places"], key=lambda p: _depth(p, by)):
        name_to_id[_norm(p["name"])] = p["id"]   # deeper places overwrite -> deepest wins
    for p in backbone["places"]:
        bb_ids.add(p["id"])
        data = {"place_type": p["place_type"]}
        for k in ("ruled_by", "faction", "members"):
            if p.get(k) not in (None, ""):
                data[k] = p[k]
        nodes.append(Node(id=p["id"], kind=NodeKind.PLACE, name=p["name"], slug=p["id"].split(":", 1)[1], data=data))
        if p.get("located_in"):
            edges.append(Edge(id=_edge_id(p["id"], "located_in"), type=EdgeType.LOCATED_IN,
                              src=p["id"], dst=p["located_in"], cond_group=None, data={}))
        se = p.get("same_entity")
        if se and se in region_ids:
            edges.append(Edge(id=_edge_id(p["id"], "same_entity"), type=EdgeType.SAME_ENTITY,
                              src=p["id"], dst=se, cond_group=None, data={}))

    # --- content ingest (filtered, typed, parented) ---
    pc = snapshot["page_categories"]
    fpts, mbrs = set(snapshot["free_to_play"]), set(snapshot["members"])
    seen = set(bb_ids)
    for title in sorted({t for lst in snapshot["categories"].values() for t in lst}):
        cls = classify(set(pc.get(title, [])))
        if cls is None:                                  # OUT category -> skip
            continue
        pid = _slug(title)
        if pid in seen:                                  # already a backbone place (dedup)
            continue
        seen.add(pid)
        place_type, content_kind = cls
        parent, _flagged = parent_for(title, set(pc.get(title, [])), name_to_id)
        data = {"place_type": place_type, "content_kind": content_kind}
        m = members_of(title, fpts, mbrs)
        if m is not None:
            data["members"] = m
        nodes.append(Node(id=pid, kind=NodeKind.PLACE, name=title, slug=pid.split(":", 1)[1], data=data))
        edges.append(Edge(id=_edge_id(pid, "located_in"), type=EdgeType.LOCATED_IN,
                          src=pid, dst=parent, cond_group=None, data={}))

    return nodes, edges, {}
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_builder.py -v`
Expected: PASS (helpers + builder).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/world.py tests/kg_ingest/test_world_builder.py
git commit -m "feat(kg): build_world — backbone + filtered/typed/parented content ingest"
```

---

### Task 6: `verify_world.py` — structural gate + report-not-fail residuals

**Files:**
- Create: `data/verify_world.py`
- Test: `tests/kg_ingest/test_verify_world.py`

**Interfaces:**
- Reuses `build_world` against the committed sources; checks the produced node/edge set.

- [ ] **Step 1: Write the failing test**

```python
# tests/kg_ingest/test_verify_world.py
import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_verify_world_passes():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_world.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WORLD VERIFICATION PASSED" in r.stdout
    assert "unparented" in r.stdout.lower()       # residual is reported
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_world.py -v`
Expected: FAIL (`data/verify_world.py` does not exist).

- [ ] **Step 3: Write `data/verify_world.py`**

```python
#!/usr/bin/env python3
"""Source-grounding gate for the world skeleton. STRUCTURAL hard-fails (exit 1): every
located_in resolves to a place; exactly one root (place:gielinor); no slug duplicate;
every place_type is in the schema enum. REPORTS (exit 0): unparented content places
(located_in == place:gielinor that aren't the root's legit children), and places missing
ruled_by/faction (best-effort governance). Reuses build_world (no drift).
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.world import build_world  # noqa: E402


def main() -> int:
    errors, unparented = [], []
    backbone = json.load(open(os.path.join(ROOT, "data", "map", "world.json"), encoding="utf-8"))
    snapshot = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_location_categories.json"), encoding="utf-8"))
    region_ids = {n["id"] for n in json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
                  if n["id"].startswith("region:")}
    enum = set(json.load(open(os.path.join(ROOT, "kg", "schema.json"), encoding="utf-8"))["node_kinds"]["place"]["place_type_enum"])
    nodes, edges, _ = build_world(backbone, snapshot, region_ids)

    ids = {n.id for n in nodes}
    if len(ids) != len(nodes):
        errors.append("[slug] duplicate place id")
    roots = [n for n in nodes if not any(e.src == n.id and e.type.value == "located_in" for e in edges)]
    if [r.id for r in roots] != ["place:gielinor"]:
        errors.append(f"[root] expected exactly place:gielinor as root, got {[r.id for r in roots][:5]}")
    for n in nodes:
        if n.data.get("place_type") not in enum:
            errors.append(f"[place_type] {n.id} has {n.data.get('place_type')!r} not in enum")
    for e in edges:
        if e.type.value == "located_in" and e.dst not in ids:
            errors.append(f"[located_in] {e.src} -> {e.dst} dangling")
    # residual: ingested content parented to the root (flagged-unparented)
    backbone_ids = {p["id"] for p in backbone["places"]}
    for e in edges:
        if e.type.value == "located_in" and e.dst == "place:gielinor" and e.src not in backbone_ids:
            unparented.append(e.src)

    if errors:
        print(f"WORLD VERIFICATION FAILED — {len(errors)} violation(s):")
        for x in errors[:60]:
            print("  -", x)
        return 1
    print("WORLD VERIFICATION PASSED — world skeleton source-grounded.")
    print(f"  places: {len(nodes)}  located_in edges: {sum(1 for e in edges if e.type.value=='located_in')}")
    print(f"  unparented content places (residual — owner to re-home): {len(unparented)}")
    for u in sorted(unparented)[:40]:
        print("    -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run + commit**

Run: `./venv/bin/python data/verify_world.py && ./venv/bin/python -m pytest tests/kg_ingest/test_verify_world.py -v`
Expected: PASS (exit 0, "WORLD VERIFICATION PASSED", residual reported).
```bash
git add data/verify_world.py tests/kg_ingest/test_verify_world.py
git commit -m "feat(data): verify_world — structural gate + report-not-fail unparented residual"
```

---

### Task 7: `verify_world_coverage.py` — the completeness gate

**Files:**
- Create: `data/verify_world_coverage.py`
- Test: `tests/kg_ingest/test_verify_world_coverage.py`

**Interfaces:**
- Offline: every IN-category member in the committed snapshot has a place node in the committed graph (or was deliberately a backbone dedup). Reports `have N/total` per category. `--refresh` re-queries live.

- [ ] **Step 1: Write the failing test**

```python
# tests/kg_ingest/test_verify_world_coverage.py
import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_coverage_gate_passes_and_reports_metric():
    r = subprocess.run([sys.executable, str(ROOT / "data" / "verify_world_coverage.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "COVERAGE" in r.stdout
    assert "Dungeons" in r.stdout and "/" in r.stdout      # the have/total metric
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_world_coverage.py -v`
Expected: FAIL (file does not exist).

- [ ] **Step 3: Write `data/verify_world_coverage.py`**

```python
#!/usr/bin/env python3
"""THE COMPLETENESS GATE (offline). Asserts the committed graph contains a place node for
every IN-category member in the committed snapshot (a member maps in iff its slug is a
place id), and reports have N/total per IN category. Report-not-fail: a residual is the
to-do, not an error. --refresh re-queries the live API to flag snapshot-vs-wiki drift.
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_slug = lambda t: "place:" + re.sub(r"[^a-z0-9]+", "-", re.sub(r"\s*\(.*?\)\s*$", "", t.lower())).strip("-")


def main() -> int:
    snap = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_location_categories.json"), encoding="utf-8"))
    place_ids = {n["id"] for n in json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
                 if n["id"].startswith("place:")}
    print("COVERAGE (graph vs committed snapshot, per IN category):")
    residual = 0
    for cat, members in snap["categories"].items():
        have = [t for t in members if _slug(t) in place_ids]
        miss = [t for t in members if _slug(t) not in place_ids]
        residual += len(miss)
        print(f"  {cat:18} {len(have):4}/{len(members):4}")
        for m in sorted(miss)[:8]:
            print(f"        missing: {m}")
    print(f"\nresidual (snapshot members without a place node): {residual} — report-not-fail (to-do / OUT-filtered).")
    if "--refresh" in sys.argv:
        print("(--refresh: re-query the live category API and diff vs the committed snapshot to flag game-update drift.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run + commit**

Run: `./venv/bin/python data/verify_world_coverage.py && ./venv/bin/python -m pytest tests/kg_ingest/test_verify_world_coverage.py -v`
Expected: PASS (prints `Dungeons NNN/177` etc.).
```bash
git add data/verify_world_coverage.py tests/kg_ingest/test_verify_world_coverage.py
git commit -m "feat(data): verify_world_coverage — offline completeness gate (have N/total) + --refresh"
```

---

### Task 8: Wire `build_world` into assemble + the `varrock.json` refactor + regen

**Files:**
- Modify: `kg_ingest/assemble.py`
- Modify: `data/map/varrock.json` (remove the 3 backbone places; keep the Varrock subtree)
- Modify (generated): `kg/{nodes,edges,condition_groups}.json`
- Test: `tests/kg_ingest/test_world_in_graph.py` (new); update `test_map_in_graph.py`

**Interfaces:**
- Consumes: `build_world` (Task 5). Adds `_load_world_backbone()` + `_load_world_snapshot()` to assemble.

- [ ] **Step 1: Write the failing integration test**

```python
# tests/kg_ingest/test_world_in_graph.py
import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType
ROOT = pathlib.Path(__file__).resolve().parents[2]

def _store():
    return JsonKGStore.from_dir(str(ROOT / "kg"))

def test_continent_level_inserted_and_misthalin_reparented():
    s = _store()
    li = {(e.src, e.dst) for e in s.edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:misthalin", "place:mainland") in li       # re-parented under the continent
    assert ("place:mainland", "place:gielinor") in li
    assert ("place:varrock", "place:misthalin") in li        # subtree intact

def test_content_sites_present_and_parented():
    s = _store()
    ids = {n for n in s.nodes}
    assert "place:catacombs-of-kourend" in ids               # the gap you found, now in
    assert any(e.type is EdgeType.LOCATED_IN and e.src == "place:catacombs-of-kourend" for e in s.edges)

def test_all_edge_ids_unique():
    s = _store()
    eids = [e.id for e in s.edges]
    assert len(eids) == len(set(eids))                       # seeded place-src rekey holds
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_in_graph.py -v`
Expected: FAIL (no world places in the committed graph yet).

- [ ] **Step 3: Add loaders to `assemble.py`** (near `_load_varrock_map`)

```python
WORLD_BACKBONE_PATH = Path(__file__).resolve().parents[1] / "data" / "map" / "world.json"
WORLD_SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "wiki_location_categories.json"


def _load_world_backbone() -> dict | None:
    return json.loads(WORLD_BACKBONE_PATH.read_text()) if WORLD_BACKBONE_PATH.exists() else None


def _load_world_snapshot() -> dict:
    return json.loads(WORLD_SNAPSHOT_PATH.read_text())
```

- [ ] **Step 4: Wire `build_world` BEFORE the `build_map` block** (after `content_nodes` is built, before the `build_map` block). Add the import `from kg_ingest.builders.world import build_world`. Insert:

```python
    # World skeleton: the geographic backbone + the location-category content ingest.
    # Place-src edges (located_in/same_entity) -> their OWN rekey, SEEDED from prior per-owner
    # counts (build_map's located_in is place-src too; seeding keeps ids disjoint). Runs BEFORE
    # build_map so the Varrock districts' located_in -> place:varrock resolves to a world node.
    world_nodes: list[Node] = []
    _wbb = _load_world_backbone()
    if _wbb is not None:
        world_region_ids = {n.id for n in content_nodes if n.id.startswith("region:")}
        world_nodes, world_edges, _ = build_world(_wbb, _load_world_snapshot(), world_region_ids)
        _seed = {}
        for _e in edges:
            _seed[_e.src] = _seed.get(_e.src, 0) + 1
        world_nodes, world_edges, _ = rekey(world_nodes, world_edges, {}, edge_index_seed=_seed)
        edges = edges + world_edges
        owned_ids = owned_ids | {n.id for n in world_nodes}
```

Then make the EXISTING `build_map` rekey **seeded** too (build_map now runs after build_world; both place-`src`):
```python
        # (in the build_map block) seed from prior per-owner counts incl. the world backbone
        _seed_m = {}
        for _e in edges:
            _seed_m[_e.src] = _seed_m.get(_e.src, 0) + 1
        map_nodes, map_edges, map_groups = rekey(map_nodes, map_edges, map_groups, edge_index_seed=_seed_m)
```
Add `world_nodes` to the `dedup_nodes(...)` call.

- [ ] **Step 5: Refactor `data/map/varrock.json`** — remove the `place:gielinor`, `place:misthalin`, `place:varrock` entries from its `places` array (now owned by `world.json`, which also carries `place:varrock`'s `same_entity → region:varrock`). The Varrock districts/pubs keep `located_in: place:varrock`. (Owner-reviewed edit — the controller confirms the 3 removals + that no district loses its parent.)

- [ ] **Step 6: Regenerate + verify byte-stability + the edge-id assert**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/`
Expected: the SECOND run leaves `kg/` unchanged; the global edge-id assert does not raise.

- [ ] **Step 7: Update `tests/kg_ingest/test_map_in_graph.py`** — it asserted `build_map` emits `place:gielinor`/`misthalin`/`varrock`; those now come from `build_world`. Keep the containment assertions but source the backbone from the graph (they still resolve — the graph is the same shape plus the continent level). Run:

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_in_graph.py tests/kg_ingest/test_map_in_graph.py tests/kg_ingest/test_storeline_in_graph.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add kg_ingest/assemble.py data/map/varrock.json kg/nodes.json kg/edges.json kg/condition_groups.json tests/kg_ingest/test_world_in_graph.py tests/kg_ingest/test_map_in_graph.py
git commit -m "feat(kg): wire build_world (seeded place-src rekey) + varrock backbone refactor; regenerate graph"
```

---

### Task 9: Competency questions (`in_region`, `region_chain`)

**Files:**
- Modify: `kg/competency_questions.json`
- Modify: `tests/kg_ingest/test_competency_questions.py`

- [ ] **Step 1: Add the CQ records (methods unknown to the runner) — RED**

Append to the `records` array:
```json
    ,{ "id": "cq-kandarin-contents",
      "question": "What locations are in Kandarin?",
      "method": "in_region", "target": "place:kandarin", "expect_min": 10 }
    ,{ "id": "cq-varrock-region-chain",
      "question": "What kingdom and continent is Varrock in?",
      "method": "region_chain", "target": "place:varrock", "expect_min": 3 }
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: FAIL with `unknown method 'in_region'`.

- [ ] **Step 3: Add the helpers + dispatch branches** in `tests/kg_ingest/test_competency_questions.py`:

```python
def _in_region(store, target):
    # transitive: all places whose located_in chain passes through target
    li = {e.src: e.dst for e in store.edges if e.type is EdgeType.LOCATED_IN}
    out = set()
    for src in li:
        cur = li.get(src)
        while cur:
            if cur == target:
                out.add(src); break
            cur = li.get(cur)
    return out

def _region_chain(store, target):
    # the located_in ancestry of target (varrock -> misthalin -> mainland -> gielinor)
    li = {e.src: e.dst for e in store.edges if e.type is EdgeType.LOCATED_IN}
    chain, cur = [], li.get(target)
    while cur:
        chain.append(cur); cur = li.get(cur)
    return chain
```
Dispatch (before the final `else: raise`):
```python
        elif cq["method"] == "in_region":
            answer = _in_region(store, cq["target"])
        elif cq["method"] == "region_chain":
            answer = set(_region_chain(store, cq["target"]))
```

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v`
Expected: PASS (Kandarin has ≥10 descendants; Varrock's chain reaches misthalin▸mainland▸gielinor).

- [ ] **Step 5: Commit**

```bash
git add kg/competency_questions.json tests/kg_ingest/test_competency_questions.py
git commit -m "feat(kg): competency questions — what's in Kandarin / Varrock's region chain"
```

---

### Task 10: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Byte-stable assemble**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python -m kg_ingest.assemble && git diff --stat kg/`
Expected: no `kg/` change after the second run.

- [ ] **Step 2: All validators + verifiers exit 0**

Run:
```bash
for v in validate_kg validate_cost verify_map verify_storeline verify_world verify_world_coverage verify_equipment_bonuses; do ./venv/bin/python data/$v.py >/dev/null 2>&1 && echo "$v=0" || echo "$v=FAIL"; done
```
Expected: every line `=0`. (`verify_world_coverage` prints the per-category metric.)

- [ ] **Step 3: Full test suite**

Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: all pass except the 4 pre-existing `tests/drop_rates/` collection errors.

- [ ] **Step 4: Spot-check the win**

Run: `./venv/bin/python data/verify_world_coverage.py`
Expected: comprehensive per-category coverage (e.g. `Dungeons 1xx/177`); the residual is the OUT-filtered/unparented to-do. Confirm `place:catacombs-of-kourend`, the continent level, and Misthalin's re-parent are in the graph.

---

## Notes for the executor

- **The seeded place-`src` rekeys (Task 8) are the highest-risk step.** Three builders now emit place/npc/shop-`src` edges in sequence (build_world → build_map → build_storeline); each rekey seeds from the per-owner counts in the accumulated `edges`. If the global edge-id assert raises, a seed is missing — confirm all three rekeys pass `edge_index_seed`.
- **Owner-review gates** (controller pauses, does not delegate): Task 3 (the `world.json` backbone), the major-mines curation (Task 2's `Mines` category — present the named list, owner picks "major"), and the unparented residual re-homing (Task 6 reports them; owner assigns parents in a `world.json`/snapshot-override follow-up).
- **`content_kind` is advisory** (the "slayer dungeon over-tag" lesson) — it's display metadata, not an adversarially-verified fact; the coarse `place_type` is the load-bearing field.
- **Network** is needed only for Task 2's fetch (and Task 7's `--refresh`); every test runs offline against the committed snapshot + graph.
