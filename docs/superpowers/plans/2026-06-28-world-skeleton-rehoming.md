# World Skeleton Re-homing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-home the world skeleton's 190 unparented places via a precision-first parenting signal stack, filter 15
non-place noise pages out, and add an acyclicity gate — driving the residual toward zero through reproducible signals.

**Architecture:** Rewrite `kg_ingest/builders/world.py:parent_for` into a 5-rung signal stack (owner-override →
category-match over **all** place nodes → name-suffix → infobox `location` → FLAG) returning `(parent, signal)`; make
`build_world` multi-pass (build a full name index before parenting) with a reachability resolve; add a shared
`is_excluded` OUT predicate; add a new reproducible infobox-`location` brick (fetcher + committed snapshot + parser) and
a small owner-authored override. Each graph-changing task re-assembles and commits `kg/*.json` (byte-stable invariant).

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON data; pytest; MediaWiki category/revision API.

## Global Constraints

- **Always use the venv:** `./venv/bin/python` for every command (Python 3.14).
- **Byte-stable assemble:** `./venv/bin/python -m kg_ingest.assemble` re-run = identical bytes. Every task that changes
  builder/data output MUST re-run assemble and commit the regenerated `kg/{nodes,edges,condition_groups}.json` in the
  SAME commit, or `tests/kg_ingest/test_assemble.py::test_committed_kg_matches_freshly_assembled` fails.
- **Never fabricate:** every re-homing traces to a wiki signal (a category, the verbatim infobox value, or an owner
  override citing `source_url` + a verbatim `source_token`). Unresolved → FLAG (report-not-fail), never guessed.
- **Report-not-fail on editorial residuals:** verifiers HARD-FAIL only on structural violations (dangling `located_in`,
  multiple roots, cycle/unreachable, `place_type` not in enum); they REPORT (exit 0) unparented + missing governance.
- **Place-`src` edge band unchanged:** `world.py` keeps `_EDGE_BAND = 0xB0000000`; re-homing changes edge `dst` only,
  not edge identity (`_edge_id(pid, "located_in")` is independent of `dst`).
- **Determinism:** iterate titles in `sorted()` order; tie-break by id sort. No `Date.now`/random.
- **Run the full suite** after each task: `./venv/bin/python -m pytest -q --continue-on-collection-errors` (the 4
  `tests/drop_rates/` collection errors are pre-existing & unrelated).

---

## File Structure

**Modify:**
- `kg_ingest/builders/world.py` — `is_excluded` + `IN_NAMES`/`NOISE_CATS`; multi-pass `build_world` with full name
  index + reachability resolve; 5-rung `parent_for` → `(parent, signal)`; `parse_infobox_links`; load infoboxes +
  overrides.
- `data/verify_world.py` — reachability/acyclicity hard-fail + per-signal re-homing breakdown.
- `data/verify_world_coverage.py` — exclude the noise set from each category denominator; add an `OUT (noise): N` line.
- `kg_ingest/assemble.py` — load + pass `infoboxes` and `overrides` to `build_world`.
- `kg/competency_questions.json` — add a re-homing competency question.
- `tests/kg_ingest/test_world_builder.py` — migrate the `parent_for` unit test to the `(parent, signal)` contract.

**Create:**
- `data/fetch_world_infoboxes.py` — paginated fetch of each snapshot page's infobox `location` wikitext.
- `data/raw/wiki_location_infoboxes.json` — committed snapshot (output of the fetcher).
- `data/map/world_parenting.json` — owner-authored override (drafted wiki-grounded; OWNER-REVIEW GATE).
- `tests/kg_ingest/test_world_rehoming.py` — new TDD tests for the signal stack, noise filter, reachability, parser.

---

## Task 1: Noise filter — shared `is_excluded` OUT predicate

**Files:**
- Modify: `kg_ingest/builders/world.py` (add `IN_NAMES`, `NOISE_CATS`, `is_excluded`; skip excluded in `build_world`)
- Modify: `data/verify_world_coverage.py` (exclude noise from denominator + `OUT (noise)` line)
- Test: `tests/kg_ingest/test_world_rehoming.py` (new)

**Interfaces:**
- Produces: `is_excluded(title: str, page_categories) -> bool`; module constants `IN_NAMES: set[str]`, `NOISE_CATS:
  set[str]`. `build_world` emits no node for an excluded page.

- [ ] **Step 1: Write the failing test**

Create `tests/kg_ingest/test_world_rehoming.py`:
```python
from kg_ingest.builders.world import is_excluded, build_world
from osrs_planner.engine.kg.model import EdgeType


def test_is_excluded_list_index_and_discontinued():
    # (a) "List of ..." index pages
    assert is_excluded("List of dungeons", ["Dungeons"]) is True
    # (b) a title equal to an IN-category name (self-referential index page)
    assert is_excluded("Minigames", ["Minigames"]) is True
    assert is_excluded("Guilds", ["Guilds"]) is True
    # (c) discontinued / non-existent
    assert is_excluded("Duel Arena", ["Minigames", "Discontinued content"]) is True
    assert is_excluded("Isle of Garmr", ["Islands", "Locations that do not appear in-game"]) is True
    # a real place is NOT excluded
    assert is_excluded("Brimhaven Dungeon", ["Dungeons", "Karamja"]) is False


NOISE_SNAP = {
    "categories": {"Dungeons": ["Brimhaven Dungeon", "List of dungeons"], "Minigames": ["Minigames"]},
    "free_to_play": [], "members": [],
    "page_categories": {"Brimhaven Dungeon": ["Dungeons", "Karamja"],
                        "List of dungeons": ["Dungeons"], "Minigames": ["Minigames"]},
}
NOISE_BACKBONE = {"places": [
    {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": ""},
    {"id": "place:karamja", "place_type": "island", "name": "Karamja", "located_in": "place:gielinor"},
]}


def test_build_world_skips_noise_pages():
    nodes, edges, _ = build_world(NOISE_BACKBONE, NOISE_SNAP, set())
    ids = {n.id for n in nodes}
    assert "place:brimhaven-dungeon" in ids          # real place kept
    assert "place:list-of-dungeons" not in ids        # list index page dropped
    assert "place:minigames" not in ids               # self-referential index dropped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py -v`
Expected: FAIL with `ImportError: cannot import name 'is_excluded'`.

- [ ] **Step 3: Write minimal implementation**

In `kg_ingest/builders/world.py`, after the `IN_TYPE` list (around line 33), add:
```python
IN_NAMES = {cat for cat, _pt, _ck in IN_TYPE}        # self-referential category-index page titles
NOISE_CATS = {"Discontinued content", "Locations that do not appear in-game"}


def is_excluded(title, page_categories):
    """The OUT clause of the IN/OUT filter: list/index pages + discontinued/non-existent.
    Shared by build_world AND verify_world_coverage so coverage stays honest."""
    if title.lower().startswith("list of "):
        return True
    if title in IN_NAMES:
        return True
    if set(page_categories) & NOISE_CATS:
        return True
    return False
```

In `build_world`'s content-ingest loop, immediately after `cls = classify(...)` and its `if cls is None: continue`
(around line 122-123), add the exclusion check BEFORE `pid = _slug(title)`:
```python
        if is_excluded(title, pc.get(title, [])):        # OUT: list/index/discontinued
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Make `verify_world_coverage.py` noise-aware**

In `data/verify_world_coverage.py`, import the shared predicate and exclude noise from each category's denominator.
After the existing imports add:
```python
sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.world import is_excluded  # noqa: E402
```
(where `ROOT` already exists). Then change the per-category loop body so an excluded member is counted as `OUT`, not
`miss`. Replace the loop in `main()`:
```python
    residual, out_noise = 0, 0
    for cat, members in snap["categories"].items():
        have, miss, claimed = [], [], set()
        for t in members:
            if is_excluded(t, snap["page_categories"].get(t, [])):
                out_noise += 1
                continue                                  # noise is OUT, not "missing"
            sg = _slug(t)
            if sg in place_ids and sg not in claimed:
                claimed.add(sg); have.append(t)
            else:
                miss.append(t)
        residual += len(miss)
        print(f"  {cat:18} {len(have):4}/{len(members) - sum(1 for t in members if is_excluded(t, snap['page_categories'].get(t, []))):4}")
        for m in sorted(miss)[:8]:
            print(f"        missing: {m}")
    print(f"\nOUT (noise: list/index/discontinued): {out_noise}")
    print(f"residual (snapshot members without a place node): {residual} — report-not-fail (to-do).")
```

- [ ] **Step 6: Re-assemble + verify byte-stable, commit**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py
./venv/bin/python data/verify_world.py
./venv/bin/python data/verify_world_coverage.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: validate_kg + verify_world + verify_world_coverage exit 0; `verify_world` now reports ~176 unparented
(190 − 14 noise that were unparented); coverage prints `OUT (noise: …): 15`; suite green. Then:
```bash
git add kg_ingest/builders/world.py data/verify_world_coverage.py tests/kg_ingest/test_world_rehoming.py \
        kg/nodes.json kg/edges.json kg/condition_groups.json
git commit -m "feat(world): noise filter (is_excluded) — drop 15 list/index/discontinued non-places"
```

---

## Task 2: Content-place parenting — the 5-rung signal stack (rungs 1-3) + multi-pass build

**Files:**
- Modify: `kg_ingest/builders/world.py` (`parent_for` → `(parent, signal)`; full name index incl. content; multi-pass)
- Modify: `tests/kg_ingest/test_world_builder.py` (migrate `parent_for` unit test to the new contract)
- Test: `tests/kg_ingest/test_world_rehoming.py` (add content-parenting cases)

**Interfaces:**
- Produces: `parent_for(title, page_categories, name_index, infobox_links=None, overrides=None) -> (parent_id: str,
  signal: str)` where `signal ∈ {"override", "category", "name-suffix", "infobox", "FLAG"}`. `build_world` signature
  gains `infoboxes=None, overrides=None` (both optional; rungs 1 & 4 inert when None — used by Tasks 4-5).
- Consumes: `is_excluded` (Task 1).

- [ ] **Step 1: Write the failing tests**

Add to `tests/kg_ingest/test_world_rehoming.py`:
```python
from kg_ingest.builders.world import parent_for


def test_parent_for_returns_signal_and_rungs():
    name_index = {"kandarin": "place:kandarin", "brimhaven": "place:brimhaven"}
    # rung 2: category-match
    assert parent_for("Catacombs of Kourend", {"Kandarin"}, name_index) == ("place:kandarin", "category")
    # rung 3: name-suffix
    assert parent_for("Brimhaven Dungeon", {"Caves"}, name_index) == ("place:brimhaven", "name-suffix")
    # rung 5: FLAG
    assert parent_for("Mystery Spot", set(), name_index) == ("place:gielinor", "FLAG")


# content place (an ingested island) must be eligible as a parent
CONTENT_SNAP = {
    "categories": {"Islands": ["Ardougne"], "Mines": ["Ardougne Sewers mine"]},
    "free_to_play": [], "members": [],
    "page_categories": {"Ardougne": ["Islands"], "Ardougne Sewers mine": ["Mines", "Ardougne"]},
}
CONTENT_BACKBONE = {"places": [
    {"id": "place:gielinor", "place_type": "world", "name": "Gielinor", "located_in": ""},
]}


def test_content_place_is_eligible_parent():
    nodes, edges, _ = build_world(CONTENT_BACKBONE, CONTENT_SNAP, set())
    li = {(e.src, e.dst) for e in edges if e.type is EdgeType.LOCATED_IN}
    # the mine parents to the INGESTED island 'place:ardougne' (not the root)
    assert ("place:ardougne-sewers-mine", "place:ardougne") in li
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py::test_parent_for_returns_signal_and_rungs tests/kg_ingest/test_world_rehoming.py::test_content_place_is_eligible_parent -v`
Expected: FAIL — `parent_for` returns `(pid, bool)` not `(pid, signal)`; the mine parents to `place:gielinor`.

- [ ] **Step 3: Rewrite `parent_for` (rungs 1-3 + 5; rung 4 stub)**

Replace `parent_for` in `kg_ingest/builders/world.py` with:
```python
def parent_for(title, page_categories, name_index, infobox_links=None, overrides=None):
    """Precision-first signal stack -> (parent_id, signal). First hit wins.
    name_index maps a normalized place name -> a place id (backbone + ingested content);
    a noise-excluded page is never in it, and a page never parents to itself."""
    slug = _slug(title)
    # (1) owner override (editorial escape hatch)
    if overrides and slug in overrides:
        return (overrides[slug]["parent"], "override")
    # (2) category-match: a place-node name among the page's categories (sorted -> deterministic)
    for c in sorted(page_categories):
        pid = name_index.get(_norm(c))
        if pid and pid != slug:
            return (pid, "category")
    # (3) name minus a type suffix -> a place node
    base = re.sub(r"\b(dungeon|caves?|mine|lair|tunnels?|cellar|crypt|vault|arena|course|guild|camp)\b.*$", "", title.lower())
    base = re.sub(r"\s*\(.*?\)\s*$", "", base).strip()
    if _norm(base):
        pid = name_index.get(_norm(base))
        if pid and pid != slug:
            return (pid, "name-suffix")
    # (4) infobox location (deterministic wikitext order); inert until Task 4 passes infobox_links
    for name in (infobox_links or []):
        pid = name_index.get(_norm(name))
        if pid and pid != slug:
            return (pid, "infobox")
    # (5) unresolved -> FLAG (never guess)
    return ("place:gielinor", "FLAG")
```

- [ ] **Step 4: Introduce the shared `resolve_parents` core + slim `build_world`**

Add a shared parenting core that both `build_world` and (Task 3) `verify_world` call — DRY, so the per-signal report
can't drift from the build. Add to `kg_ingest/builders/world.py`:
```python
def resolve_parents(backbone, snapshot, extra_seen=None, infoboxes=None, overrides=None):
    """Shared parenting core. Returns (kept, parent_map, signal_map):
      kept       = [(title, place_type, content_kind, pid)]   (filtered, typed, sorted)
      parent_map = {pid: parent_id}                            (Task 3 adds reachability)
      signal_map = {pid: signal}                               (override/category/name-suffix/infobox/FLAG)
    name_index spans backbone + ingested content; backbone WINS on a name collision."""
    pc = snapshot["page_categories"]
    by = {p["id"]: p for p in backbone["places"]}
    def _depth(p):
        d, cur = 0, p.get("located_in")
        while cur and cur in by and d < 12:
            d += 1; cur = by[cur].get("located_in")
        return d
    name_index = {}
    for p in sorted(backbone["places"], key=_depth):     # deepest-backbone-wins among backbone
        name_index[_norm(p["name"])] = p["id"]
    seen = {p["id"] for p in backbone["places"]}
    if extra_seen:
        seen |= set(extra_seen)
    kept = []
    for title in sorted({t for lst in snapshot["categories"].values() for t in lst}):
        cls = classify(set(pc.get(title, [])))
        if cls is None or is_excluded(title, pc.get(title, [])):
            continue
        pid = _slug(title)
        if pid in seen:
            continue
        seen.add(pid)
        kept.append((title, cls[0], cls[1], pid))
    for title, _pt, _ck, pid in kept:
        name_index.setdefault(_norm(title), pid)         # content joins; backbone precedence preserved
    parent_map, signal_map = {}, {}
    for title, _pt, _ck, pid in kept:
        parent, signal = parent_for(title, set(pc.get(title, [])), name_index,
                                    infobox_links=(infoboxes or {}).get(title), overrides=overrides)
        parent_map[pid] = parent; signal_map[pid] = signal
    return kept, parent_map, signal_map
```
Then update the signature and replace the content-ingest section (current lines ~84-134, including the old backbone
`name_to_id` builder which `resolve_parents` now owns) so `build_world` emits backbone nodes/edges, then emits content
from `resolve_parents`:
```python
def build_world(backbone, snapshot, region_ids, extra_seen=None, infoboxes=None, overrides=None):
    nodes, edges = [], []
    for p in backbone["places"]:
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
    kept, parent_map, _signals = resolve_parents(backbone, snapshot, extra_seen, infoboxes, overrides)
    fpts, mbrs = set(snapshot["free_to_play"]), set(snapshot["members"])
    for title, place_type, content_kind, pid in kept:
        data = {"place_type": place_type, "content_kind": content_kind}
        m = members_of(title, fpts, mbrs)
        if m is not None:
            data["members"] = m
        nodes.append(Node(id=pid, kind=NodeKind.PLACE, name=title, slug=pid.split(":", 1)[1], data=data))
        edges.append(Edge(id=_edge_id(pid, "located_in"), type=EdgeType.LOCATED_IN,
                          src=pid, dst=parent_map[pid], cond_group=None, data={}))
    return nodes, edges, {}
```

- [ ] **Step 5: Migrate the existing `parent_for` unit test**

In `tests/kg_ingest/test_world_builder.py`, replace `test_parent_region_category_then_name_heuristic` with the
`(parent, signal)` contract (the build_world output tests below it stay unchanged — parents resolve the same):
```python
def test_parent_region_category_then_name_heuristic():
    name2id = {"kandarin": "place:kandarin", "brimhaven": "place:brimhaven"}
    assert parent_for("Catacombs of Kourend", {"Kandarin"}, name2id) == ("place:kandarin", "category")
    assert parent_for("Brimhaven Dungeon", {"Caves"}, name2id) == ("place:brimhaven", "name-suffix")
    assert parent_for("Mystery Spot", set(), name2id) == ("place:gielinor", "FLAG")
```

- [ ] **Step 6: Run the builder tests**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_builder.py tests/kg_ingest/test_world_rehoming.py -v`
Expected: PASS (all).

- [ ] **Step 7: Re-assemble + verify + commit**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py && ./venv/bin/python data/verify_world.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: exit 0; `verify_world` unparented drops to ~124; suite green (incl.
`test_committed_kg_matches_freshly_assembled`). Then:
```bash
git add kg_ingest/builders/world.py tests/kg_ingest/test_world_builder.py tests/kg_ingest/test_world_rehoming.py \
        kg/nodes.json kg/edges.json kg/condition_groups.json
git commit -m "feat(world): content-place parenting — let ingested places be parents (+52 re-homed)"
```

---

## Task 3: Reachability/acyclicity gate + per-signal report

**Files:**
- Modify: `kg_ingest/builders/world.py` (reachability resolve in `build_world`)
- Modify: `data/verify_world.py` (unreachable/cycle hard-fail + per-signal re-homing breakdown)
- Test: `tests/kg_ingest/test_world_rehoming.py` (cycle demotion + unreachable detection)

**Interfaces:**
- Produces: `_resolve_reachable(parent: dict[str, str]) -> dict[str, str]` in `world.py` (demotes any non-root node
  that can't reach `place:gielinor` to the root, deterministically). `verify_world` gains `_unreachable_places(nodes,
  edges) -> list[str]` (hard-fail when non-empty).

- [ ] **Step 1: Write the failing tests**

Add to `tests/kg_ingest/test_world_rehoming.py`:
```python
from kg_ingest.builders.world import _resolve_reachable


def test_resolve_reachable_demotes_cycle():
    # a -> b -> a is a cycle disconnected from the root; both demote to the root
    parent = {"place:gielinor": None, "place:a": "place:b", "place:b": "place:a"}
    out = _resolve_reachable(parent)
    assert out["place:a"] == "place:gielinor"
    assert out["place:b"] == "place:gielinor"


def test_resolve_reachable_keeps_valid_chain():
    parent = {"place:gielinor": None, "place:x": "place:gielinor", "place:y": "place:x"}
    out = _resolve_reachable(parent)
    assert out["place:y"] == "place:x" and out["place:x"] == "place:gielinor"
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py::test_resolve_reachable_demotes_cycle -v`
Expected: FAIL — `cannot import name '_resolve_reachable'`.

- [ ] **Step 3: Add the reachability resolve inside `resolve_parents`**

Add `_resolve_reachable` to `kg_ingest/builders/world.py`:
```python
def _resolve_reachable(parent):
    """Demote any non-root node that cannot reach place:gielinor (cycle/dangling) to the
    root. Deterministic fixpoint (sorted order). Guarantees single-root + acyclic."""
    def reaches_root(s):
        seen, cur = set(), s
        while cur != "place:gielinor":
            if cur is None or cur in seen:
                return False
            seen.add(cur); cur = parent.get(cur)
        return True
    out = dict(parent)
    changed = True
    while changed:
        changed = False
        for s in sorted(out):
            if s != "place:gielinor" and out[s] != "place:gielinor" and not reaches_root(s):
                out[s] = "place:gielinor"; changed = True
    return out
```
Then, in `resolve_parents`, seed the parent map with the backbone (already a DAG to the root) and run the resolve over
the union before returning. Replace the `return kept, parent_map, signal_map` tail with:
```python
    backbone_parent = {p["id"]: p.get("located_in") or None for p in backbone["places"]}
    backbone_parent["place:gielinor"] = None
    resolved = _resolve_reachable({**backbone_parent, **parent_map})
    for pid in parent_map:
        if resolved[pid] == "place:gielinor" and parent_map[pid] != "place:gielinor":
            signal_map[pid] = "FLAG"                      # demoted by reachability -> FLAG
        parent_map[pid] = resolved[pid]
    return kept, parent_map, signal_map
```
(`build_world` already emits from `parent_map`, so it now gets the reachability-resolved parents with no further change.)

- [ ] **Step 4: Run the reachability unit tests**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py -v`
Expected: PASS (all, incl. the two reachability tests).

- [ ] **Step 5: Add the verify_world hard-fail + per-signal report (best-effort signal inputs)**

In `data/verify_world.py`: (a) extend the import; (b) add best-effort loaders for the infobox/override inputs (return
`None` until Tasks 4-5 commit the files, so the report auto-upgrades with NO later edits to this file); (c) feed them to
BOTH the structural `build_world` call and the report's `resolve_parents`; (d) add the unreachable/cycle hard-fail;
(e) print the per-signal breakdown.

Extend the import and add loaders (after the existing `sys.path` / `build_world` import lines ~14). The
`parse_infobox_links` import is LAZY — it doesn't exist until Task 4, and is only reached once the snapshot file does:
```python
from kg_ingest.builders.world import build_world, resolve_parents  # noqa: E402

def _opt_infoboxes():
    p = os.path.join(ROOT, "data", "raw", "wiki_location_infoboxes.json")
    if not os.path.exists(p):
        return None
    from kg_ingest.builders.world import parse_infobox_links  # Task 4+
    raw = json.load(open(p, encoding="utf-8"))["infoboxes"]
    return {t: parse_infobox_links(r.get("location", "")) for t, r in raw.items()}

def _opt_overrides():
    p = os.path.join(ROOT, "data", "map", "world_parenting.json")
    return json.load(open(p, encoding="utf-8"))["overrides"] if os.path.exists(p) else None
```
Change the existing `build_world(backbone, snapshot, region_ids)` call (line ~27) to thread the optional inputs:
```python
    _ibx, _ovr = _opt_infoboxes(), _opt_overrides()
    nodes, edges, _ = build_world(backbone, snapshot, region_ids, infoboxes=_ibx, overrides=_ovr)
```
After the existing `for e in edges: ... dangling` check (line ~40), add the reachability hard-fail:
```python
    # reachability: every place must reach place:gielinor (acyclic, single-root)
    par = {e.src: e.dst for e in edges if e.type.value == "located_in"}
    def _reaches(s):
        seen, cur = set(), s
        while cur != "place:gielinor":
            if cur is None or cur in seen:
                return False
            seen.add(cur); cur = par.get(cur)
        return True
    for n in nodes:
        if n.id != "place:gielinor" and not _reaches(n.id):
            errors.append(f"[reachable] {n.id} does not reach place:gielinor (cycle/dangling)")
```
After the `unparented` print (line ~54), add the per-signal breakdown (DRY — same core the build used, same inputs):
```python
    from collections import Counter
    _kept, _pmap, signal_map = resolve_parents(backbone, snapshot, infoboxes=_ibx, overrides=_ovr)
    by = Counter(signal_map.values())
    print("  re-homed by signal: " + ", ".join(f"{k}={by[k]}" for k in
          ("override", "category", "name-suffix", "infobox") if by.get(k)))
    print(f"  re-homed {sum(v for k, v in by.items() if k != 'FLAG')}/{len(signal_map)} content places "
          f"· residual (FLAG): {by.get('FLAG', 0)}")
```

- [ ] **Step 6: Re-assemble + verify + commit**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py && ./venv/bin/python data/verify_world.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: exit 0 (0 cycles today, so no demotions; graph bytes UNCHANGED from Task 2 — re-assemble is a no-op for the
graph, confirming the resolve is inert when acyclic); `verify_world` prints `re-homed … · residual …`. Then:
```bash
git add kg_ingest/builders/world.py data/verify_world.py tests/kg_ingest/test_world_rehoming.py \
        kg/nodes.json kg/edges.json kg/condition_groups.json
git commit -m "feat(world): reachability gate (acyclic, single-root) + per-signal re-homing report"
```

---

## Task 4: Infobox `location` brick — fetcher + snapshot + parser + rung 4

**Files:**
- Create: `data/fetch_world_infoboxes.py`
- Create: `data/raw/wiki_location_infoboxes.json` (output of the fetcher)
- Modify: `kg_ingest/builders/world.py` (`parse_infobox_links`; build the per-title `infobox_links` map)
- Modify: `kg_ingest/assemble.py` (load `wiki_location_infoboxes.json`, pass to `build_world`)
- Test: `tests/kg_ingest/test_world_rehoming.py` (parser cases)

**Interfaces:**
- Produces: `parse_infobox_links(location_wikitext: str) -> list[str]` (ordered, de-duped link targets). The assembler
  passes `infoboxes={title: parse_infobox_links(rec["location"])}` to `build_world`.

- [ ] **Step 1: Write the failing parser test**

Add to `tests/kg_ingest/test_world_rehoming.py`:
```python
from kg_ingest.builders.world import parse_infobox_links


def test_parse_infobox_links():
    assert parse_infobox_links("Located in southern [[Misthalin]]") == ["Misthalin"]
    # alias links: keep the target, drop the alias; order preserved; de-duped
    assert parse_infobox_links("[[Karamja|the island]], near [[Brimhaven]] and [[Karamja]]") == ["Karamja", "Brimhaven"]
    assert parse_infobox_links("") == []
    assert parse_infobox_links("no links here") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py::test_parse_infobox_links -v`
Expected: FAIL — `cannot import name 'parse_infobox_links'`.

- [ ] **Step 3: Implement the parser**

Add to `kg_ingest/builders/world.py`:
```python
def parse_infobox_links(location_wikitext):
    """Extract [[Target]] / [[Target|alias]] link targets from an infobox location value,
    in order, de-duped. Verbatim source -> deterministic targets (no inference)."""
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", location_wikitext or ""):
        target = m.group(1).strip()
        if target and target not in out:
            out.append(target)
    return out
```

- [ ] **Step 4: Run to verify the parser passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py::test_parse_infobox_links -v`
Expected: PASS.

- [ ] **Step 5: Write the fetcher**

Create `data/fetch_world_infoboxes.py` (mirrors `fetch_world_locations.py`; pulls each page's raw wikitext and extracts
the infobox `location` parameter verbatim):
```python
#!/usr/bin/env python3
"""Fetch each location page's infobox `location` parameter (verbatim wikitext) from the
OSRS Wiki, for parenting the world skeleton's residual. Deterministic + sorted. Verbatim —
no inference. Source: OSRS Wiki (CC BY-NC-SA). Run: ./venv/bin/python data/fetch_world_infoboxes.py
"""
import json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
WIKI = "https://oldschool.runescape.wiki/w/"
# the infobox parameter(s) that carry the containing area (confirmed at fetch time)
LOC_PARAM_RE = re.compile(r"\|\s*location\s*=\s*(.+?)(?=\n\s*\||\n\}\})", re.IGNORECASE | re.DOTALL)


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def _location_param(wikitext):
    m = LOC_PARAM_RE.search(wikitext or "")
    return m.group(1).strip() if m else ""


def main():
    snap = json.load(open(os.path.join(RAW, "wiki_location_categories.json"), encoding="utf-8"))
    titles = sorted({t for lst in snap["categories"].values() for t in lst})
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        d = _api({"action": "query", "titles": "|".join(batch), "prop": "revisions",
                  "rvprop": "content", "rvslots": "main"})
        for pg in d.get("query", {}).get("pages", {}).values():
            title = pg["title"]
            revs = pg.get("revisions", [])
            wt = revs[0]["slots"]["main"]["*"] if revs else ""
            out[title] = {"location": _location_param(wt), "source_url": WIKI + title.replace(" ", "_")}
        time.sleep(0.1)
    payload = {"_provenance": {"domain": "wiki_location_infoboxes", "source": "OSRS Wiki revisions API",
                               "license": "CC BY-NC-SA 3.0", "param": "Infobox location="},
               "infoboxes": dict(sorted(out.items()))}
    with open(os.path.join(RAW, "wiki_location_infoboxes.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("DONE:", len(out), "pages;", sum(1 for v in out.values() if v["location"]), "with a location param")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the fetcher (commits the snapshot)**

Run: `./venv/bin/python data/fetch_world_infoboxes.py`
Expected: `DONE: <~577> pages; <N> with a location param`. Inspect a few entries to confirm the param name was right:
`./venv/bin/python -c "import json; d=json.load(open('data/raw/wiki_location_infoboxes.json'))['infoboxes']; print({k:d[k] for k in list(d)[:5]})"`
If `with a location param` is near 0, the infobox uses a different param name — widen `LOC_PARAM_RE` to also try
`kingdom`/`map`/`region` (micro-item §11), re-run, re-inspect.

- [ ] **Step 7: Wire the snapshot into the assembler**

In `kg_ingest/assemble.py`, near the world path constants (line ~291) add:
```python
WORLD_INFOBOX_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "wiki_location_infoboxes.json"
```
and a loader:
```python
def _load_world_infoboxes() -> dict | None:
    if not WORLD_INFOBOX_PATH.exists():
        return None
    raw = json.loads(WORLD_INFOBOX_PATH.read_text())["infoboxes"]
    from kg_ingest.builders.world import parse_infobox_links
    return {title: parse_infobox_links(rec.get("location", "")) for title, rec in raw.items()}
```
In the `build_world(...)` call (line ~418), pass `infoboxes=_load_world_infoboxes()`:
```python
        world_nodes, world_edges, _ = build_world(
            _wbb, _load_world_snapshot(), world_region_ids,
            extra_seen=_map_place_ids, infoboxes=_load_world_infoboxes())
```

- [ ] **Step 8: Re-assemble + verify + commit**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py && ./venv/bin/python data/verify_world.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: exit 0; `verify_world` residual drops below 124 (by however many the infobox resolves); suite green. Then:
```bash
git add data/fetch_world_infoboxes.py data/raw/wiki_location_infoboxes.json \
        kg_ingest/builders/world.py kg_ingest/assemble.py tests/kg_ingest/test_world_rehoming.py \
        kg/nodes.json kg/edges.json kg/condition_groups.json
git commit -m "feat(world): infobox-location brick — fetch + parse + rung 4 parenting"
```

---

## Task 5: Owner override + backbone additions (EDITORIAL — owner-review gate)

**Files:**
- Create: `data/map/world_parenting.json` (owner-authored override; drafted wiki-grounded)
- Modify: `kg_ingest/assemble.py` (load + pass `overrides`)
- Modify: `data/map/world.json` (only genuinely-absent real places — owner-reviewed)
- Test: `tests/kg_ingest/test_world_rehoming.py` (override precedence)

**Interfaces:**
- Produces: `overrides` dict `{ "<place:slug>": {"parent": "<place:id>", "source_url": "...", "source_token": "..."} }`
  passed to `build_world(..., overrides=...)`; rung 1 (Task 2) already consumes it.

- [ ] **Step 1: Write the failing override-precedence test**

Add to `tests/kg_ingest/test_world_rehoming.py`:
```python
def test_override_beats_heuristics():
    name_index = {"kandarin": "place:kandarin"}
    overrides = {"place:catacombs-of-kourend": {"parent": "place:great-kourend"}}
    # even though the category would resolve to Kandarin, the override wins
    assert parent_for("Catacombs of Kourend", {"Kandarin"}, name_index, overrides=overrides) \
        == ("place:great-kourend", "override")
```

- [ ] **Step 2: Run to verify it fails or passes**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_world_rehoming.py::test_override_beats_heuristics -v`
Expected: PASS (rung 1 was implemented in Task 2). If it fails, fix rung 1 ordering in `parent_for`.

- [ ] **Step 3: Generate the residual list to draft from**

```bash
./venv/bin/python data/verify_world.py 2>&1 | grep "    - place:" > /tmp/residual.txt
wc -l /tmp/residual.txt
```
For each residual slug, look up its wiki page (`source_url` in `wiki_location_infoboxes.json` / the page categories) and
determine the correct parent place id that already exists in the graph. Draft `data/map/world_parenting.json`:
```json
{
  "_provenance": {"domain": "world_parenting", "note": "owner-authored re-homing override; each entry source-grounded"},
  "overrides": {
    "place:draynor-village": {"parent": "place:misthalin", "source_url": "https://oldschool.runescape.wiki/w/Draynor_Village", "source_token": "Draynor Village is a small settlement in southern Misthalin"}
  }
}
```
Add only entries you can ground in a verbatim wiki token. Leave genuinely-ambiguous ones FLAGGED (report-not-fail).

- [ ] **Step 4: Wire overrides into the assembler**

In `kg_ingest/assemble.py`, add near the world path constants:
```python
WORLD_PARENTING_PATH = Path(__file__).resolve().parents[1] / "data" / "map" / "world_parenting.json"


def _load_world_parenting() -> dict | None:
    if not WORLD_PARENTING_PATH.exists():
        return None
    return json.loads(WORLD_PARENTING_PATH.read_text())["overrides"]
```
and pass it in the `build_world(...)` call:
```python
        world_nodes, world_edges, _ = build_world(
            _wbb, _load_world_snapshot(), world_region_ids, extra_seen=_map_place_ids,
            infoboxes=_load_world_infoboxes(), overrides=_load_world_parenting())
```

- [ ] **Step 5: Add genuinely-absent backbone places (if any)**

For residual whose parent place does not exist as ANY node (e.g. `Brimhaven`), add it to `data/map/world.json`'s
`places` with `{id, place_type, name, located_in, members, source_url}` — owner-reviewed shape, like the existing
backbone. Only where the place is genuinely missing (not merely itself-unparented).

- [ ] **Step 6: OWNER-REVIEW GATE**

STOP. Present `data/map/world_parenting.json` + any `world.json` additions to the owner (the collapsible
`world_skeleton.html` tree is the sign-off medium). Do not proceed until the owner approves the editorial entries.

- [ ] **Step 7: Re-assemble + verify + commit**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py && ./venv/bin/python data/verify_world.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: exit 0; residual at its floor (the disclosed, owner-accepted remainder). Then:
```bash
git add data/map/world_parenting.json data/map/world.json kg_ingest/assemble.py \
        tests/kg_ingest/test_world_rehoming.py kg/nodes.json kg/edges.json kg/condition_groups.json
git commit -m "feat(world): owner-authored re-homing override + backbone additions (residual -> floor)"
```

---

## Task 6: Competency question + final verification

**Files:**
- Modify: `kg/competency_questions.json`
- Test: `tests/kg_ingest/test_competency_questions.py` (existing runner exercises the new record)

**Interfaces:**
- Consumes: the `region_chain` competency method (existing runner).

- [ ] **Step 1: Add the competency question**

In `kg/competency_questions.json`'s `records`, add a record whose target Task 2 guarantees re-homed
(`place:ardougne-sewers-mine` → `place:ardougne` → … → root):
```json
{"id": "cq-rehomed-region-chain", "question": "What contains the Ardougne Sewers mine?",
 "method": "region_chain", "target": "place:ardougne-sewers-mine", "expect_min": 2}
```
(If the owner override re-homed `place:draynor-village`, optionally add
`{"id": "cq-draynor-region-chain", "question": "What region is Draynor Village in?", "method": "region_chain",
 "target": "place:draynor-village", "expect_min": 2}`.)

- [ ] **Step 2: Run the competency + full suite**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_competency_questions.py -v && ./venv/bin/python -m pytest -q --continue-on-collection-errors`
Expected: PASS (the new CQ resolves a non-trivial ancestry chain); full suite green.

- [ ] **Step 3: Final acceptance gate**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py
./venv/bin/python data/verify_world.py
./venv/bin/python data/verify_world_coverage.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: all exit 0; `verify_world` shows the re-homed/residual breakdown; coverage shows `OUT (noise): 15` and
`have N/total` honest; byte-stable. Then commit:
```bash
git add kg/competency_questions.json
git commit -m "feat(world): re-homing competency question (region_chain over a re-homed place)"
```

- [ ] **Step 4: Whole-branch review + PR**

Request a code review (superpowers:requesting-code-review) over the branch diff; address findings; open the PR with the
re-homed/residual numbers and the per-signal breakdown in the body.

---

## Self-Review (run against the spec)

**1. Spec coverage:**
- §3 signal stack (5 rungs) → Task 2 (rungs 1-3,5) + Task 4 (rung 4) + Task 5 (rung 1 data). ✓
- §3.1 reachability resolve → Task 3. ✓
- §4 shared `is_excluded` (builder + coverage verifier) → Task 1. ✓
- §5 infobox brick (fetcher + snapshot + parser) → Task 4. ✓
- §6 owner override + backbone additions → Task 5 (with owner gate). ✓
- §7 verify_world reachability hard-fail + per-signal report → Task 3; coverage `OUT (noise)` → Task 1. ✓
- §7 assemble byte-stable, `0xB0` band unchanged → every task's Step "Re-assemble + verify". ✓
- §7 competency question → Task 6. ✓
- §8 TDD cases (content-parent, cycle demote, reachability hard-fail, noise excluded, infobox parses, override beats
  heuristics) → Tasks 1-5 tests. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases"; every code step shows full code; the one open micro-item (exact
infobox param name) has a concrete confirm-and-widen instruction (Task 4 Step 6). ✓

**3. Type consistency:** `parent_for(... ) -> (parent_id, signal)` used identically in Tasks 2-5; `build_world(...,
infoboxes=None, overrides=None)` signature introduced in Task 2 and fed in Tasks 4-5; `is_excluded(title,
page_categories)` identical in Task 1 builder + coverage verifier; `parse_infobox_links` produced in Task 4, consumed by
the assembler loader. ✓
