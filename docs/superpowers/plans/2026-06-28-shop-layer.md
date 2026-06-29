# Shop Layer — All-Shops Scale-Up — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale the slice-7 Varrock-only shop layer to **every** `Bucket:Storeline` shop (581): each becomes a
`shop:` node parented `located_in` a world-skeleton place via a new shop-infobox brick, with item-only `sells`
edges, gated by a coverage verifier and a source-grounding verifier.

**Architecture:** A new builder `kg_ingest/builders/shops.py` (`build_shops`) consumes two committed sources —
`storeline_bucket.json` (roster + stock) and a NEW `wiki_shop_infoboxes.json` (location + members + the
shop-type `icon`). A NEW `wiki_shop_categories.json` is the coverage yardstick used only by
`verify_shop_coverage`. It emits `shop` nodes + `located_in` + item-only `sells`, wired into `assemble.py` after
`build_storeline`, rekeyed in its own seeded call (shop-`src` family). Mirrors the world-skeleton's
backbone+snapshot+infobox triad.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON data; pytest. Reuses
`kg_ingest.builders.world` (`parse_infobox_links`, `_norm`), `kg_ingest.builders.storeline` (`match_shop`,
`index_by_shop`), `kg_ingest.builders.map_varrock` (`make_item_resolver`), `kg_ingest.ids` (`slugify`,
`_stable_hash`, `item_id`), `osrs_planner.engine.kg.model` (`Node`, `Edge`, `NodeKind`, `EdgeType`).

## Global Constraints

- **Never fabricate.** Every datum traces to the wiki; ungroundable items stay **FLAGGED** (report-not-fail),
  never invented. Bricks carry `_provenance` (source_url, license `CC BY-NC-SA 3.0`, extraction method).
- **No `currency`/`price`/`cost` token in `kg/*.json`** — `validate_cost.py` Inv 6 hard-fails on it. Sells
  edges are **item-only**, byte-identical in shape to `build_storeline`'s (data = `{members?, source_token}`).
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run produces identical bytes;
  `tests/kg_ingest/test_assemble.py::test_committed_kg_matches_freshly_assembled` stays green.
- **≤1 `located_in` per shop.** Multi-location shops (>1 distinct resolved place) emit **no** location edge and
  set `multi_location: true`; zero resolved → `FLAG`. No arbitrary "primary" is ever chosen.
- **Roster = Storeline `sold_by`** minus the 15 Varrock-owned shops (`build_map` owns those). Derived shops
  carry **no** `operator` (deferred to the NPC layer).
- **shop-`src` edges rekeyed in their OWN seeded `rekey` call**; the global edge-id-uniqueness assert backstops.
- Source from the wiki **structured layer** (Bucket / Category API / `{{Infobox Shop}}`), never prose.
- All validators/verifiers exit 0; the existing test suite stays green.

## File Structure

- `data/fetch_shop_infoboxes.py` (NEW) — fetch script: enumerate `Category:Shops` subcategories → pages, fetch
  each `{{Infobox Shop}}`, extract location(s)/members/owner verbatim. Pure parsers are importable + unit-tested;
  `main()` does network + writes the two snapshots. Mirrors `data/fetch_world_infoboxes.py`.
- `data/raw/wiki_shop_categories.json` (NEW, committed) — `{category: [page titles]}` per `Category:Shops`
  subcat; the coverage yardstick used only by `verify_shop_coverage` (NOT by `build_shops`).
- `data/raw/wiki_shop_infoboxes.json` (NEW, committed) — `{page: {locations, members, owner, icon, source_url}}`.
- `kg_ingest/builders/shops.py` (NEW) — `build_shops` + helpers (`_shop_slug`, `build_place_name_index`,
  `shop_type_for`, `resolve_shop_places`). Emits nodes + `located_in` + item-only `sells`.
- `kg_ingest/assemble.py` (MODIFY) — load the two bricks; call `build_shops` after `build_storeline`; seeded rekey.
- `data/verify_shop_coverage.py` (NEW) — completeness gate (Storeline ↔ type-category cross-check; report-not-fail).
- `data/verify_shops.py` (NEW) — source-grounding gate (every sells→Storeline row; every located_in→infobox token).
- `kg/schema.json` (MODIFY) — add `multi_location` to `node_kinds.shop.data_keys` (additive).
- `kg/competency_questions.json` (MODIFY) — add shop competency questions.
- Tests under `tests/kg_ingest/` and `tests/` mirroring existing `test_storeline_*`, `test_world_*`,
  `test_verify_*` files.

---

### Task 1: Shop-infobox brick (fetch script + pure parsers + committed snapshots)

**Files:**
- Create: `data/fetch_shop_infoboxes.py`
- Create (committed output): `data/raw/wiki_shop_categories.json`, `data/raw/wiki_shop_infoboxes.json`
- Test: `tests/data/test_fetch_shop_infoboxes.py`, `tests/kg_ingest/test_shop_snapshot.py`

**Interfaces:**
- Produces (pure, importable): `extract_infobox_block(wikitext: str) -> str`,
  `split_top_level_params(block: str) -> dict[str, str]`, `shop_locations(params: dict) -> list[str]`,
  `shop_members(params: dict) -> str | None`, `shop_owners(params: dict) -> list[str]`.
- Produces (snapshots): `wiki_shop_categories.json` = `{"_provenance": {...}, "categories": {cat: [titles]}}`;
  `wiki_shop_infoboxes.json` = `{"_provenance": {...}, "infoboxes": {title: {"locations": [str],
  "members": str|None, "owner": [str], "icon": str|None, "source_url": str}}}`. `icon` is the verbatim
  infobox `icon` value (e.g. `[[File:Archery shop icon.png]]`) — the structured shop-type signal (the in-game
  map-icon legend); `build_shops` (Task 2) parses it into `shop_type`. The fine "X shops" categories do NOT
  exist as wiki categories, so the icon — not the category — is the type source.

> **Network note:** `main()` requires network. If the implementer has no network access, implement + unit-test
> the pure parsers, then STOP and report `NEEDS_CONTEXT: run the fetch to materialize the committed snapshots`;
> the controller runs `./venv/bin/python data/fetch_shop_infoboxes.py` and commits the two snapshots. The
> snapshot test (below) validates whatever is committed.

- [ ] **Step 1: Write failing parser tests**

`tests/data/test_fetch_shop_infoboxes.py`:
```python
import importlib.util, os
_spec = importlib.util.spec_from_file_location(
    "fetch_shop_infoboxes",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "fetch_shop_infoboxes.py"))
fsi = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fsi)

SINGLE = "{{Infobox Shop\n|name = Lumbridge General Store\n|members = No\n|location = [[Lumbridge]]\n|owner = [[Shop keeper]]/[[Shop assistant]]\n}}\n==Stock=="
VERSIONED = ("{{Infobox Shop\n|name = Slayer Rewards\n|members = Yes\n"
             "|location1 = [[Burthorpe]]\n|location2 = [[Draynor Village]]\n"
             "|owner1 = [[Turael]]/[[Aya]]\n|owner2 = [[Spria]]\n}}")
NESTED = "{{Infobox Shop\n|name = X\n|location = [[Falador]] {{Map|x}}\n|members = Yes\n}}"

def test_extract_block_isolates_infobox():
    b = fsi.extract_infobox_block(SINGLE)
    assert "name = Lumbridge General Store" in b
    assert "==Stock==" not in b

def test_extract_block_handles_nested_template():
    b = fsi.extract_infobox_block(NESTED)
    assert "{{Map|x}}" in b           # nested template fully inside the block

def test_single_location():
    p = fsi.split_top_level_params(fsi.extract_infobox_block(SINGLE))
    assert fsi.shop_locations(p) == ["[[Lumbridge]]"]
    assert fsi.shop_members(p) == "No"
    assert fsi.shop_owners(p) == ["[[Shop keeper]]/[[Shop assistant]]"]

def test_versioned_locations_unioned_in_order():
    p = fsi.split_top_level_params(fsi.extract_infobox_block(VERSIONED))
    assert fsi.shop_locations(p) == ["[[Burthorpe]]", "[[Draynor Village]]"]
    assert fsi.shop_members(p) == "Yes"

def test_no_infobox_returns_empty():
    assert fsi.extract_infobox_block("just prose, no infobox") == ""

def test_nested_pipe_not_split():
    p = fsi.split_top_level_params(fsi.extract_infobox_block(NESTED))
    assert p["location"] == "[[Falador]] {{Map|x}}"   # the {{Map|x}} pipe did NOT split the param
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/data/test_fetch_shop_infoboxes.py -q`
Expected: FAIL (module/functions not defined).

- [ ] **Step 3: Implement `data/fetch_shop_infoboxes.py`**

```python
#!/usr/bin/env python3
"""Fetch each shop page's {{Infobox Shop}} location/members/owner (verbatim) + the
Category:Shops type-subcategory membership, for the all-shops layer. Deterministic +
sorted. Verbatim — no inference. Source: OSRS Wiki (CC BY-NC-SA).
Run: ./venv/bin/python data/fetch_shop_infoboxes.py
"""
import json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
WIKI = "https://oldschool.runescape.wiki/w/"


def extract_infobox_block(wikitext):
    """Return the {{Infobox Shop ...}} block (brace-depth counted so nested {{...}}
    are kept), or '' if absent. Robust to nested templates (naive non-greedy regex
    would truncate at the first nested }})."""
    m = re.search(r"\{\{Infobox Shop\b", wikitext or "", re.IGNORECASE)
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
    return wikitext[m.start():]          # unbalanced -> take the tail (verbatim, no inference)


def split_top_level_params(block):
    """Split an infobox block into {param: value} on '|' at brace/bracket depth 0
    (so nested {{...}} and [[...]] pipes do NOT split). First '=' splits key/value."""
    inner = block
    if inner.startswith("{{"):
        inner = inner[2:]
    if inner.endswith("}}"):
        inner = inner[:-2]
    parts, buf, depth = [], [], 0
    i = 0
    while i < len(inner):
        two = inner[i:i + 2]
        if two in ("{{", "[["):
            depth += 1; buf.append(two); i += 2; continue
        if two in ("}}", "]]"):
            depth = max(0, depth - 1); buf.append(two); i += 2; continue
        c = inner[i]
        if c == "|" and depth == 0:
            parts.append("".join(buf)); buf = []
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    out = {}
    for seg in parts[1:]:                # parts[0] is the template name
        if "=" in seg:
            k, v = seg.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def shop_locations(params):
    """Ordered, non-empty location values: |location=, else |location1..N= (verbatim)."""
    out = []
    if params.get("location"):
        out.append(params["location"])
    for i in range(1, 21):
        v = params.get(f"location{i}")
        if v:
            out.append(v)
    return out


def shop_members(params):
    v = params.get("members")
    return v if v else None


def shop_owners(params):
    out = []
    if params.get("owner"):
        out.append(params["owner"])
    for i in range(1, 21):
        v = params.get(f"owner{i}")
        if v:
            out.append(v)
    return out


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def _members(category, cmtype):
    out, cont = [], {}
    while True:
        d = _api({"action": "query", "list": "categorymembers", "cmtitle": category,
                  "cmlimit": "500", "cmtype": cmtype, **cont})
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" in d:
            cont = d["continue"]
        else:
            break
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    # 1) Category:Shops subcategories -> {subcat: [pages]} ; subcat title sans 'Category:' = shop_type source
    subcats = _members("Category:Shops", "subcat")
    categories = {}
    for sc in sorted(subcats):
        pages = _members(sc, "page")
        categories[sc.replace("Category:", "")] = sorted(pages)
        time.sleep(0.1)
    all_pages = sorted({p for pages in categories.values() for p in pages})
    # 2) {{Infobox Shop}} per page
    infoboxes = {}
    for i in range(0, len(all_pages), 20):
        batch = all_pages[i:i + 20]
        d = _api({"action": "query", "titles": "|".join(batch), "prop": "revisions",
                  "rvprop": "content", "rvslots": "main"})
        for pg in d.get("query", {}).get("pages", {}).values():
            title = pg["title"]
            revs = pg.get("revisions", [])
            wt = revs[0]["slots"]["main"]["*"] if revs else ""
            params = split_top_level_params(extract_infobox_block(wt))
            infoboxes[title] = {"locations": shop_locations(params), "members": shop_members(params),
                                "owner": shop_owners(params), "icon": params.get("icon"),
                                "source_url": WIKI + title.replace(" ", "_")}
        time.sleep(0.1)
    with open(os.path.join(RAW, "wiki_shop_categories.json"), "w", encoding="utf-8") as f:
        json.dump({"_provenance": {"domain": "wiki_shop_categories", "source": "OSRS Wiki category API",
                                   "license": "CC BY-NC-SA 3.0", "root": "Category:Shops"},
                   "categories": dict(sorted(categories.items()))}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RAW, "wiki_shop_infoboxes.json"), "w", encoding="utf-8") as f:
        json.dump({"_provenance": {"domain": "wiki_shop_infoboxes", "source": "OSRS Wiki revisions API",
                                   "license": "CC BY-NC-SA 3.0", "param": "Infobox Shop|location/members/owner"},
                   "infoboxes": dict(sorted(infoboxes.items()))}, f, ensure_ascii=False, indent=1)
    print(f"DONE: {len(categories)} shop-type categories, {len(all_pages)} pages, "
          f"{sum(1 for v in infoboxes.values() if v['locations'])} with a location")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run parser tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/data/test_fetch_shop_infoboxes.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Materialize the committed snapshots**

Run: `./venv/bin/python data/fetch_shop_infoboxes.py`
Expected: prints `DONE: <N> shop-type categories, <M> pages, <K> with a location`. Two files appear in
`data/raw/`. (No network → STOP with `NEEDS_CONTEXT`, controller runs this.)

- [ ] **Step 6: Write + run the snapshot shape test**

`tests/kg_ingest/test_shop_snapshot.py`:
```python
import json, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

def test_shop_infobox_snapshot_shape():
    d = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_infoboxes.json"), encoding="utf-8"))
    assert "_provenance" in d and "infoboxes" in d
    assert d["infoboxes"] == dict(sorted(d["infoboxes"].items()))   # committed sorted (byte-deterministic)
    sample = next(iter(d["infoboxes"].values()))
    assert set(sample) >= {"locations", "members", "owner", "icon", "source_url"}
    assert isinstance(sample["locations"], list)

def test_shop_categories_snapshot_shape():
    d = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_categories.json"), encoding="utf-8"))
    assert "categories" in d and d["categories"]
    assert all(isinstance(v, list) for v in d["categories"].values())
```

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_shop_snapshot.py -q` → PASS.

- [ ] **Step 7: Commit**

```bash
git add data/fetch_shop_infoboxes.py data/raw/wiki_shop_infoboxes.json data/raw/wiki_shop_categories.json \
        tests/data/test_fetch_shop_infoboxes.py tests/kg_ingest/test_shop_snapshot.py
git commit -m "feat(shop-layer): shop-infobox brick (location/members/owner) + type-category snapshot"
```

---

### Task 2: `build_shops` roster + node emission (no edges yet)

**Files:**
- Create: `kg_ingest/builders/shops.py`
- Test: `tests/kg_ingest/test_shops_builder.py`

**Interfaces:**
- Consumes: Storeline records (list of `{sold_by, sold_item, ...}`); `shop_infoboxes`
  (`{title: {locations, members, owner, icon, source_url}}`); Varrock shop names (`set[str]`);
  `storeline.match_shop`, `ids.slugify`.
- Produces: `build_shops(storeline_records, shop_infoboxes, place_nodes, dict_records,
  varrock_shop_names) -> (nodes: list[Node], edges: list[Edge], groups: dict)`. This task emits **nodes only**
  (`located_in` in Task 3, `sells` in Task 4 return `[]` for now). Helpers: `_shop_slug(name) -> str`,
  `shop_roster(storeline_records, varrock_shop_names) -> list[str]`, `shop_type_for(icon: str | None) -> str | None`
  (parses the infobox icon, e.g. `[[File:Archery shop icon.png]]` → `Archery shop`).
  **`shop_categories` is NOT a `build_shops` input** — `shop_type` comes from the icon; the category snapshot is
  used only by `verify_shop_coverage` (Task 5).

- [ ] **Step 1: Write failing tests**

`tests/kg_ingest/test_shops_builder.py`:
```python
from kg_ingest.builders.shops import _shop_slug, shop_roster, shop_type_for, build_shops
from osrs_planner.engine.kg.model import NodeKind

def test_shop_slug_handles_apostrophe_and_trailing_period():
    assert _shop_slug("Aemad's Adventuring Supplies.") == "shop:aemads-adventuring-supplies"
    assert _shop_slug("General Store (Canifis)") == "shop:general-store-canifis"

def test_roster_excludes_varrock_owned():
    recs = [{"sold_by": "Zaff's Superior Staffs!"}, {"sold_by": "Al Kharid General Store"},
            {"sold_by": "Aubury's Rune Shop."}]
    # Varrock owns Zaff + Aubury (matched town-aware); only Al Kharid remains
    roster = shop_roster(recs, {"Zaff's Superior Staffs", "Aubury's Rune Shop"})
    assert roster == ["Al Kharid General Store"]

def test_shop_type_from_icon():
    assert shop_type_for("[[File:Archery shop icon.png]]") == "Archery shop"
    assert shop_type_for("[[File:General store icon.png]]") == "General store"
    assert shop_type_for(None) is None
    assert shop_type_for("[[File:weird.png]]") is None        # no ' icon.png' -> None, not fabricated

def test_build_shops_emits_node_with_type_and_members():
    recs = [{"sold_by": "Al Kharid General Store", "sold_item": "Pot"}]
    ib = {"Al Kharid General Store": {"locations": ["[[Al Kharid]]"], "members": "No",
                                      "owner": [], "icon": "[[File:General store icon.png]]"}}
    nodes, edges, groups = build_shops(recs, ib, [], [], set())
    n = next(n for n in nodes if n.id == "shop:al-kharid-general-store")
    assert n.kind is NodeKind.SHOP
    assert n.data["shop_type"] == "General store"
    assert n.data["members"] is False
    assert "operator" not in n.data            # operators deferred to the NPC layer

def test_collision_guard_disambiguates_loudly(capsys):
    # two DISTINCT names that slugify identically must NOT silently merge
    recs = [{"sold_by": "Cool Shop"}, {"sold_by": "Cool  Shop"}]   # double-space -> same slug
    nodes, _, _ = build_shops(recs, {}, [], [], set())
    ids = sorted(n.id for n in nodes)
    assert len(ids) == 2 and len(set(ids)) == 2   # two distinct nodes, no merge
    assert "collision" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_shops_builder.py -q`
Expected: FAIL (module not defined).

- [ ] **Step 3: Implement `kg_ingest/builders/shops.py` (nodes only)**

```python
"""build_shops — the all-shops layer (every Bucket:Storeline shop).

Roster = Storeline sold_by minus the Varrock-owned shops (build_map owns those).
Each shop -> a shop: node (shop_type from the type-category, members from the
infobox), parented located_in a skeleton place via its infobox location (Task 3),
with item-only sells from Storeline (Task 4). Operators are DEFERRED to the NPC
layer. Edges are shop-src -> assemble re-keys them in their OWN seeded call.
Never fabricates: unmatched/unparented -> reported, never invented.
"""
from __future__ import annotations

import re

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, slugify
from kg_ingest.builders.storeline import match_shop, index_by_shop

_EDGE_BAND = 0xF0000000        # shop-src family (shared with build_storeline); cosmetic — rekey replaces it


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _shop_slug(name: str) -> str:
    return "shop:" + slugify(name)


def shop_roster(storeline_records, varrock_shop_names):
    """Distinct Storeline sold_by, minus the Varrock-owned shops (matched town-aware so
    'Zaff's Superior Staffs' owns 'Zaff's Superior Staffs!'). Sorted -> deterministic."""
    soldby = sorted({r["sold_by"] for r in storeline_records if r.get("sold_by")})
    owned = {match_shop(name, soldby) for name in varrock_shop_names}
    owned.discard(None)
    return [s for s in soldby if s not in owned]


def shop_type_for(icon):
    """Derive the shop type from the infobox icon (the in-game map-icon legend IS the type taxonomy):
    '[[File:Archery shop icon.png]]' -> 'Archery shop'. The fine 'X shops' categories don't exist as wiki
    categories, so the icon is the structured source. None if absent/unparseable (never fabricated)."""
    m = re.search(r"File:\s*(.+?)\s+icon\.png", icon or "", re.IGNORECASE)
    return m.group(1).strip() if m else None


def _members(infobox):
    v = (infobox or {}).get("members")
    if v is None:
        return None
    return {"yes": True, "no": False}.get(v.strip().lower())


def build_shops(storeline_records, shop_infoboxes, place_nodes, dict_records, varrock_shop_names):
    nodes: list[Node] = []
    edges: list[Edge] = []                     # located_in (Task 3) + sells (Task 4) land here
    by_shop = index_by_shop(storeline_records)
    infobox_titles = list(shop_infoboxes)

    claimed: dict[str, str] = {}               # slug -> first sold_by (collision guard)
    for name in shop_roster(storeline_records, varrock_shop_names):
        sid = _shop_slug(name)
        if sid in claimed:                     # distinct names, same slug -> NEVER silently merge
            n = 2
            while f"{sid}-{n}" in claimed:
                n += 1
            print(f"[shops] slug collision: {name!r} and {claimed[sid]!r} -> {sid}; using {sid}-{n}")
            sid = f"{sid}-{n}"
        claimed[sid] = name

        ib_title = match_shop(name, infobox_titles)
        ib = shop_infoboxes.get(ib_title) if ib_title else None
        data: dict = {}
        st = shop_type_for((ib or {}).get("icon"))
        if st:
            data["shop_type"] = st
        m = _members(ib)
        if m is not None:
            data["members"] = m
        nodes.append(Node(id=sid, kind=NodeKind.SHOP, name=name, slug=sid.split(":", 1)[1], data=data))

    return nodes, edges, {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_shops_builder.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/shops.py tests/kg_ingest/test_shops_builder.py
git commit -m "feat(shop-layer): build_shops roster + node emission (shop_type, members, collision guard)"
```

---

### Task 3: Parenting + multi-location rule

**Files:**
- Modify: `kg_ingest/builders/shops.py`
- Test: `tests/kg_ingest/test_shops_parenting.py`

**Interfaces:**
- Consumes: `world.parse_infobox_links`, `world._norm`; `place_nodes` (list of `Node`, kind place).
- Produces: `build_place_name_index(place_nodes) -> dict[str, str]` (`_norm(name) -> place id`);
  `resolve_shop_places(locations: list[str], name_index: dict) -> list[str]` (distinct, ordered place ids).
  `build_shops` now emits `located_in` for single-location shops, sets `multi_location: true` for >1, and leaves
  zero-resolution shops unparented (no edge).

- [ ] **Step 1: Write failing tests**

`tests/kg_ingest/test_shops_parenting.py`:
```python
from kg_ingest.builders.shops import build_place_name_index, resolve_shop_places, build_shops
from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType

PLACES = [Node(id="place:al-kharid", kind=NodeKind.PLACE, name="Al Kharid", slug="al-kharid", data={}),
          Node(id="place:burthorpe", kind=NodeKind.PLACE, name="Burthorpe", slug="burthorpe", data={}),
          Node(id="place:draynor-village", kind=NodeKind.PLACE, name="Draynor Village", slug="draynor-village", data={})]

def test_name_index_maps_norm_name_to_id():
    idx = build_place_name_index(PLACES)
    assert idx["alkharid"] == "place:al-kharid"

def test_resolve_distinct_ordered():
    idx = build_place_name_index(PLACES)
    assert resolve_shop_places(["[[Burthorpe]]", "[[Draynor Village]]", "[[Burthorpe]]"], idx) == \
        ["place:burthorpe", "place:draynor-village"]

def _locedges(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}

def _shop(recs_name, locations):
    recs = [{"sold_by": recs_name, "sold_item": "Pot"}]
    ib = {recs_name: {"locations": locations, "members": "No", "owner": [], "icon": None}}
    return build_shops(recs, ib, PLACES, [], set())

def test_single_location_emits_located_in():
    nodes, edges, _ = _shop("Al Kharid General Store", ["[[Al Kharid]]"])
    assert ("shop:al-kharid-general-store", "place:al-kharid") in _locedges(edges)

def test_multi_location_defers_no_edge_flag_set():
    nodes, edges, _ = _shop("Slayer Rewards", ["[[Burthorpe]]", "[[Draynor Village]]"])
    assert _locedges(edges) == set()                          # NO arbitrary primary
    n = next(n for n in nodes if n.id == "shop:slayer-rewards")
    assert n.data["multi_location"] is True

def test_zero_resolution_flagged_no_edge():
    nodes, edges, _ = _shop("Mystery Shop", ["[[Nowheresville]]"])
    assert _locedges(edges) == set()
    n = next(n for n in nodes if n.id == "shop:mystery-shop")
    assert "multi_location" not in n.data                     # unparented FLAG, not multi
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_shops_parenting.py -q`
Expected: FAIL (`build_place_name_index` not defined).

- [ ] **Step 3: Implement parenting in `kg_ingest/builders/shops.py`**

Add imports at top (with the existing imports):
```python
from kg_ingest.builders.world import parse_infobox_links, _norm
```
Add helpers (after `_shop_slug`):
```python
def build_place_name_index(place_nodes):
    """Map _norm(place name) -> place id over the committed place graph. setdefault +
    sorted-by-id -> deterministic first-wins on a name collision."""
    idx: dict[str, str] = {}
    for n in sorted(place_nodes, key=lambda n: n.id):
        if n.id.startswith("place:"):
            idx.setdefault(_norm(n.name), n.id)
    return idx


def resolve_shop_places(locations, name_index):
    """Parse each infobox location value -> wikilink targets -> place ids, distinct + ordered.
    A link that doesn't resolve to a place is dropped (reported as unparented, never guessed)."""
    out: list[str] = []
    for raw in locations:
        for target in parse_infobox_links(raw):
            pid = name_index.get(_norm(target))
            if pid and pid not in out:
                out.append(pid)
    return out
```
In `build_shops`, build the index once before the loop:
```python
    name_index = build_place_name_index(place_nodes)
```
Inside the loop, after building `data` (before `nodes.append`), resolve and emit:
```python
        places = resolve_shop_places((ib or {}).get("locations", []), name_index)
        if len(places) > 1:
            data["multi_location"] = True                    # deferred to the NPC layer (no arbitrary primary)
        nodes.append(Node(id=sid, kind=NodeKind.SHOP, name=name, slug=sid.split(":", 1)[1], data=data))
        if len(places) == 1:
            edges.append(Edge(id=_edge_id(sid, "located_in"), type=EdgeType.LOCATED_IN,
                              src=sid, dst=places[0], cond_group=None, data={}))
        # len(places) == 0 -> unparented FLAG (no edge), reported by verify_shop_coverage
```
(Move the `nodes.append(...)` line that Task 2 added so it now uses the `data` that includes `multi_location`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_shops_parenting.py tests/kg_ingest/test_shops_builder.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/shops.py tests/kg_ingest/test_shops_parenting.py
git commit -m "feat(shop-layer): parenting via infobox location + multi-location defer rule"
```

---

### Task 4: Sells scale-up (item-only)

**Files:**
- Modify: `kg_ingest/builders/shops.py`
- Test: `tests/kg_ingest/test_shops_sells.py`

**Interfaces:**
- Consumes: `map_varrock.make_item_resolver(dict_records)`; `storeline.index_by_shop`.
- Produces: `build_shops` now also emits item-only `sells` edges for each derived shop from its Storeline rows.
  Edge data = `{members?, source_token: "Bucket:Storeline"}` — **no currency/price** (Inv 6).

- [ ] **Step 1: Write failing tests**

`tests/kg_ingest/test_shops_sells.py`:
```python
from kg_ingest.builders.shops import build_shops
from osrs_planner.engine.kg.model import EdgeType

DICT = [{"item_id": 1931, "name": "Pot", "page_name": "Pot", "is_canonical": True, "members": False},
        {"item_id": 1935, "name": "Jug", "page_name": "Jug", "is_canonical": True, "members": False}]
RECS = [{"sold_by": "Al Kharid General Store", "sold_item": "Pot", "store_currency": "Coins"},
        {"sold_by": "Al Kharid General Store", "sold_item": "Jug", "store_currency": "Coins"},
        {"sold_by": "Al Kharid General Store", "sold_item": "Ghost item", "store_currency": "Coins"}]
IB = {"Al Kharid General Store": {"locations": ["[[Al Kharid]]"], "members": "No", "owner": []}}

def _sells(edges):
    return {(e.src, e.dst) for e in edges if e.type is EdgeType.SELLS}

def test_sells_emitted_for_resolved_items():
    nodes, edges, _ = build_shops(RECS, IB, [], DICT, set())
    s = _sells(edges)
    assert ("shop:al-kharid-general-store", "item:1931") in s
    assert ("shop:al-kharid-general-store", "item:1935") in s

def test_unresolved_item_skipped_not_fabricated():
    nodes, edges, _ = build_shops(RECS, IB, [], DICT, set())
    assert not any(e.dst == "item:None" for e in edges)
    assert all(e.dst is not None for e in edges)

def test_sells_edge_has_no_currency_or_price_keys():
    nodes, edges, _ = build_shops(RECS, IB, [], DICT, set())
    sells = next(e for e in edges if e.type is EdgeType.SELLS)
    for forbidden in ("currency", "store_currency", "price", "cost"):
        assert forbidden not in sells.data           # validate_cost Inv 6
    assert sells.data["source_token"] == "Bucket:Storeline"
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_shops_sells.py -q`
Expected: FAIL (no sells edges emitted yet).

- [ ] **Step 3: Implement sells in `kg_ingest/builders/shops.py`**

Add import at top:
```python
from kg_ingest.builders.map_varrock import make_item_resolver
from kg_ingest.ids import item_id
```
In `build_shops`, build the resolver + item-members lookup before the loop:
```python
    resolve = make_item_resolver(dict_records)
    dict_by_id = {r["item_id"]: r for r in dict_records}
```
Inside the loop, after emitting `located_in`, emit sells from the shop's Storeline rows:
```python
        for j, row in enumerate(by_shop.get(name, [])):
            iid = resolve(row.get("sold_item", ""))
            if iid is None:
                continue                                     # unresolved -> reported by verify_shops
            edata = {"source_token": "Bucket:Storeline"}     # NO currency/price -> validate_cost Inv 6
            mem = dict_by_id.get(iid, {}).get("members")
            if mem is not None:
                edata["members"] = mem
            edges.append(Edge(id=_edge_id(sid, f"sl#{j}"), type=EdgeType.SELLS,
                              src=sid, dst=item_id(iid), cond_group=None, data=edata))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_shops_sells.py tests/kg_ingest/test_shops_parenting.py tests/kg_ingest/test_shops_builder.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add kg_ingest/builders/shops.py tests/kg_ingest/test_shops_sells.py
git commit -m "feat(shop-layer): item-only sells scale-up from Storeline (no currency, Inv 6 safe)"
```

---

### Task 5: Verifiers (coverage + source-grounding)

**Files:**
- Create: `data/verify_shop_coverage.py`, `data/verify_shops.py`
- Test: `tests/kg_ingest/test_verify_shops.py`

**Interfaces:**
- Consumes the committed `kg/nodes.json`, `kg/edges.json`, `data/raw/storeline_bucket.json`, the two bricks,
  and reuses `shops.shop_roster`, `storeline.index_by_shop`, `map_varrock.make_item_resolver`.
- Produces two CLI scripts (exit 0 = report-not-fail for coverage; `verify_shops` exits 1 on structural breach).

- [ ] **Step 1: Write a failing smoke test**

`tests/kg_ingest/test_verify_shops.py`:
```python
import subprocess, sys, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

def _run(script):
    return subprocess.run([sys.executable, os.path.join(ROOT, "data", script)],
                          capture_output=True, text=True)

def test_verify_shop_coverage_runs_and_reports():
    r = _run("verify_shop_coverage.py")
    assert r.returncode == 0                       # report-not-fail
    assert "COVERAGE" in r.stdout

def test_verify_shops_passes_on_committed_graph():
    r = _run("verify_shops.py")
    assert r.returncode == 0, r.stdout
    assert "SHOP VERIFICATION" in r.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_verify_shops.py -q`
Expected: FAIL (scripts don't exist). (Will also fail until Task 6 wires the graph; that is expected — this
task delivers the scripts, Task 6 makes the committed-graph assertions green.)

- [ ] **Step 3: Implement `data/verify_shop_coverage.py`**

```python
#!/usr/bin/env python3
"""SHOP COMPLETENESS GATE (offline, report-not-fail). Cross-checks the two shop rosters —
Storeline sold_by vs the Category:Shops type-category union — and reports, per shop_type,
how many have a shop node and how many of those are parented / multi-location-deferred /
FLAGged (no location). A residual is the to-do, not an error. --refresh = live drift.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.shops import shop_roster, _shop_slug              # noqa: E402


def main() -> int:
    rows = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    cats = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_categories.json"), encoding="utf-8"))["categories"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))

    shop_ids = {n["id"] for n in nodes if n["id"].startswith("shop:")}
    multi = {n["id"] for n in nodes if n["id"].startswith("shop:") and n.get("data", {}).get("multi_location")}
    located = {e["src"] for e in edges if e.get("type") == "located_in" and e["src"].startswith("shop:")}

    roster = shop_roster(rows, varrock)
    have = [name for name in roster if _shop_slug(name) in shop_ids]
    parented = [name for name in have if _shop_slug(name) in located]
    multi_def = [name for name in have if _shop_slug(name) in multi]
    flagged = [name for name in have if _shop_slug(name) not in located and _shop_slug(name) not in multi]
    print("SHOP COVERAGE (graph vs Storeline roster):")
    print(f"  roster (Storeline sold_by minus Varrock): {len(roster)}")
    print(f"  have a shop node:        {len(have)}/{len(roster)}")
    print(f"  parented (located_in):   {len(parented)}")
    print(f"  multi-location deferred: {len(multi_def)}")
    print(f"  FLAGged (no location):   {len(flagged)}")
    for name in sorted(flagged)[:20]:
        print(f"        no-location: {name}")

    # cross-check vs the type-category union (the second yardstick)
    cat_pages = {p for pages in cats.values() for p in pages}
    print(f"\n  type-category union pages: {len(cat_pages)} ; Storeline shops: {len(roster) + len(varrock)}")
    print("  residual (roster shops without a node, or category pages with no Storeline match) — report-not-fail.")
    if "--refresh" in sys.argv:
        print("  (--refresh: re-query the live category API and diff vs the committed snapshot.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implement `data/verify_shops.py`**

```python
#!/usr/bin/env python3
"""Source-grounding gate for the all-shops layer. REPORTS (never fails) resolution
residuals: shops with no infobox location (FLAG), unresolved sold_item names, deferred
multi-location shops. HARD-FAILS (exit 1) on structural violations: a derived sells edge
whose (shop, item) has no backing Storeline row, or a derived located_in whose dst is not
a committed place node. Reuses the builder helpers.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.shops import shop_roster, _shop_slug                  # noqa: E402
from kg_ingest.builders.storeline import index_by_shop                        # noqa: E402
from kg_ingest.builders.map_varrock import make_item_resolver                 # noqa: E402


def main() -> int:
    errors, unresolved = [], []
    rows = json.load(open(os.path.join(ROOT, "data", "raw", "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    varrock = {s["name"] for s in json.load(open(os.path.join(ROOT, "data", "map", "varrock.json"), encoding="utf-8"))["shops"]}
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    resolve = make_item_resolver(json.load(open(os.path.join(ROOT, "data", "item_dictionary.json"), encoding="utf-8"))["records"])

    place_ids = {n["id"] for n in nodes if n["id"].startswith("place:")}
    by_shop = index_by_shop(rows)
    roster = shop_roster(rows, varrock)
    slug_to_name = {_shop_slug(name): name for name in roster}

    # every derived sells edge -> a backing Storeline row (the shop sells the item per Storeline)
    for e in edges:
        if e.get("type") != "sells" or not e["src"].startswith("shop:"):
            continue
        name = slug_to_name.get(e["src"])
        if name is None:
            continue                                  # Varrock shop (build_storeline) — not this verifier's scope
        backing = {resolve(r.get("sold_item", "")) for r in by_shop.get(name, [])}
        iid = e["dst"].split(":", 1)[1]
        if f"item:{iid}" not in {f"item:{b}" for b in backing if b is not None}:
            errors.append(f"[sells] {e['src']} -> {e['dst']} has no backing Storeline row")

    # every derived located_in -> a committed place node
    for e in edges:
        if e.get("type") == "located_in" and e["src"] in slug_to_name and e["dst"] not in place_ids:
            errors.append(f"[located_in] {e['src']} -> {e['dst']} dst is not a committed place node")

    # resolution residual (report): unresolved sold_item names across the roster
    for name in roster:
        for r in by_shop.get(name, []):
            if resolve(r.get("sold_item", "")) is None:
                unresolved.append(f"{_shop_slug(name)}: {r.get('sold_item')!r}")

    if errors:
        print(f"SHOP VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print("SHOP VERIFICATION PASSED — derived shop stock + locations source-grounded.")
    print(f"  derived shops in roster: {len(roster)}")
    if unresolved:
        print(f"  {len(unresolved)} unresolved sold_item name(s) (residual — alias pass):")
        for u in unresolved[:30]:
            print("    -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Commit (scripts; tests go green after Task 6)**

```bash
git add data/verify_shop_coverage.py data/verify_shops.py tests/kg_ingest/test_verify_shops.py
git commit -m "feat(shop-layer): coverage + source-grounding verifiers (report-not-fail / structural-fail)"
```

---

### Task 6: Assemble wiring + schema + competency + byte-stable

**Files:**
- Modify: `kg_ingest/assemble.py`, `kg/schema.json`, `kg/competency_questions.json`
- Regenerate: `kg/nodes.json`, `kg/edges.json`, `kg/condition_groups.json`
- Test: existing `tests/kg_ingest/test_assemble.py`, `tests/kg_ingest/test_competency_questions.py`,
  `tests/kg_ingest/test_verify_shops.py`

**Interfaces:**
- Consumes everything above. Wires `build_shops` into the pipeline; sanity-checks the icon-derived `shop_type`;
  registers `multi_location`; adds shop competency questions.

- [ ] **Step 1: Add `multi_location` to the schema (additive)**

In `kg/schema.json`, change the `shop` node-kind `data_keys` from
`["operator", "shop_type", "aliases"]` to `["operator", "shop_type", "multi_location", "aliases"]`.

- [ ] **Step 2: Add loaders + the build_shops block to `assemble.py`**

Add path constants near the other `*_PATH` definitions (after `WORLD_PARENTING_PATH`):
```python
SHOP_INFOBOX_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "wiki_shop_infoboxes.json"
```
Add a loader near `_load_storeline_records` (the category snapshot is loaded only by `verify_shop_coverage`, not
assemble — `shop_type` comes from the infobox icon, so `build_shops` needs no categories):
```python
def _load_shop_infoboxes() -> dict | None:
    if not SHOP_INFOBOX_PATH.exists():
        return None
    return json.loads(SHOP_INFOBOX_PATH.read_text())["infoboxes"]
```
Add the import near `from kg_ingest.builders.storeline import build_storeline`:
```python
from kg_ingest.builders.shops import build_shops
```
Immediately AFTER the `build_storeline` block (after `groups.update(st_groups)`), add the `build_shops` block.
`world_nodes` and `map_nodes` are already in scope; gather place nodes from both for the name-index:
```python
    # All-shops layer: every Storeline shop (minus the 15 Varrock-owned) -> a shop: node parented into the
    # skeleton. shop-src edges (located_in + item-only sells) -> their OWN seeded rekey (same owner class as
    # build_map's located_in + build_storeline's sells, so seed from the per-owner counts already in `edges`).
    _shop_ib = _load_shop_infoboxes()
    if _map is not None and _shop_ib is not None:
        _place_nodes = [n for n in (world_nodes + map_nodes) if n.kind == NodeKind.PLACE]
        _varrock_names = {s["name"] for s in _map["shops"]}
        sh_nodes, sh_edges, _ = build_shops(
            _load_storeline_records(), _shop_ib, _place_nodes,
            _load_item_dict_records(), _varrock_names)
        _seed_sh: dict[str, int] = {}
        for _e in edges:
            _seed_sh[_e.src] = _seed_sh.get(_e.src, 0) + 1
        sh_nodes, sh_edges, _ = rekey(sh_nodes, sh_edges, {}, edge_index_seed=_seed_sh)
        edges = edges + sh_edges
        owned_ids = owned_ids | {n.id for n in sh_nodes}
```
Ensure `NodeKind` is imported in `assemble.py` (check the import block; add `NodeKind` if absent). Ensure
`sh_nodes` are appended to whatever node list assemble writes (follow how `world_nodes`/`map_nodes` are
collected into the final node set — add `sh_nodes` to the same accumulation).

- [ ] **Step 3: Re-assemble + run the structural validators**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python -m kg_ingest.assemble   # run twice — byte-stable
git diff --stat kg/                        # second run shows NO change
./venv/bin/python data/validate_kg.py      # exit 0
./venv/bin/python data/validate_cost.py    # exit 0 — confirms NO currency/price token leaked into kg/*.json
```
Expected: `validate_kg` and `validate_cost` both PASS; re-running assemble leaves `kg/*.json` byte-identical.

- [ ] **Step 4: Sanity-check the icon-derived `shop_type` distribution**

```bash
./venv/bin/python -c "import json,collections; n=json.load(open('kg/nodes.json')); print(collections.Counter(x['data'].get('shop_type') for x in n if x['id'].startswith('shop:')).most_common(25))"
```
Expected: clean type names (`General store`, `Magic shop`, `Archery shop`, `Gem shop`, …) — the in-game
map-icon taxonomy. A tail of `None` (shops whose page has no parseable icon) is acceptable — `shop_type` is
advisory/report-not-fail. No code change unless a malformed type name appears (then fix `shop_type_for`'s regex).

- [ ] **Step 5: Run the verifiers (now against the wired graph)**

```bash
./venv/bin/python data/verify_shop_coverage.py     # exit 0; reports have N/total, parented/multi/FLAG
./venv/bin/python data/verify_shops.py             # exit 0; "SHOP VERIFICATION PASSED"
./venv/bin/python -m pytest tests/kg_ingest/test_verify_shops.py -q   # PASS
```
If `verify_shops` reports structural errors, fix the builder (a real bug) — do not weaken the verifier.

- [ ] **Step 6: Add shop competency questions**

Pick a derived shop + item that exist post-assembly, then add records to `kg/competency_questions.json`'s
`records` list (reusing the existing `shop_stock` / `sold_by` / `region_chain` method handlers). Verify each
target exists and set `expect_min` to a value the assembled graph satisfies:
```bash
./venv/bin/python -c "import json; n={x['id'] for x in json.load(open('kg/nodes.json'))}; print('shop:al-kharid-general-store' in n)"
```
Example records (adjust ids/`expect_min` to the assembled graph — they MUST pass):
```json
{ "id": "cq-shop-stock-al-kharid-general", "question": "What does the Al Kharid General Store sell?",
  "method": "shop_stock", "target": "shop:al-kharid-general-store", "expect_min": 3 },
{ "id": "cq-shop-region-chain-al-kharid-general", "question": "Where is the Al Kharid General Store?",
  "method": "region_chain", "target": "shop:al-kharid-general-store", "expect_min": 2 }
```

- [ ] **Step 7: Run the full suite + commit**

```bash
./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py tests/kg_ingest/test_assemble.py -q
./venv/bin/python -m pytest -q --continue-on-collection-errors   # full suite (4 drop_rates collection errors pre-existing)
git add kg_ingest/assemble.py kg/schema.json kg/competency_questions.json kg/nodes.json kg/edges.json kg/condition_groups.json kg_ingest/builders/shops.py
git commit -m "feat(shop-layer): wire build_shops into assemble (seeded rekey) + multi_location schema + competency"
```
Expected: all green; `validate_kg`, `validate_cost`, `verify_shops`, `verify_shop_coverage` exit 0; assemble byte-stable.

---

## Self-Review notes (planner)

- **Spec coverage:** §4 brick → Task 1; §5 nodes/located_in/sells + multi-location → Tasks 2-4; §8 verifiers →
  Task 5; §2/§6 wiring + schema + byte-stable + §9 competency → Task 6. Currency (§7) is OUT — no task, by design.
- **Type consistency:** `build_shops(storeline_records, shop_infoboxes, shop_categories, place_nodes,
  dict_records, varrock_shop_names)` is identical across Tasks 2/3/4/6. `_shop_slug` returns `shop:<slug>`
  everywhere. Edge data shape matches `build_storeline` (`{members?, source_token}`), satisfying Inv 6.
- **No placeholders:** every code/test step has complete code; the only deferred tuning is `SHOP_TYPE_PRIORITY`
  (advisory) and the competency `expect_min` (must match the assembled graph) — both with explicit verify steps.
- **Network caveat:** Task 1's fetch needs network; the pure parsers are TDD'd offline and the snapshot is
  materialized by the controller if the implementer can't reach the wiki.
