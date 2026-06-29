# Edge-id SPAN widen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Lift the `stable_edge_id`/`stable_group_id` 2M collision ceiling (widen `SPAN` to `1<<48`) and delete
the all-shops sequential-id band so every edge goes back through the one deterministic `rekey` scheme.

**Architecture:** A constants change in `kg_ingest/assemble.py` (`SPAN`/`GROUP_OFFSET`/`EDGE_OFFSET`) + replacing
the shop block's sequential id assignment with the standard seeded `rekey` call. Triggers a one-time renumber of
every edge/group id; byte-stable thereafter. Only `test_assemble.py` hardcodes the id domains.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON graph; pytest.

## Global Constraints

- **`SPAN = 1 << 48`**, **`GROUP_OFFSET = 1 << 49`**, **`EDGE_OFFSET = 1 << 50`** (disjoint domains, both < 2⁵³ JS-safe).
- **Byte-stable** assemble (re-run = identical bytes); `test_committed_kg_matches_freshly_assembled` stays green.
- **Fail-fast preserved:** `rekey` still raises on a (now-negligible) collision — no resolution logic added.
- Graph semantics unchanged — only integer edge/group ids move; node slugs unchanged.
- All validators/verifiers exit 0; full suite green (4 `tests/drop_rates/` collection errors pre-existing).

## File Structure

- `kg_ingest/assemble.py` (MODIFY) — the 3 constants + docstring; replace the `_SHOP_EDGE_BASE` sequential block
  with a seeded `rekey` call.
- `tests/kg_ingest/test_assemble.py` (MODIFY) — domain-bound assertions + the two collision-raise tests' fixed values.
- `kg_ingest/builders/shops.py` (MODIFY) — revert the PR #21 "sequential overwrite" comments to "rekey replaces it".
- `kg/{edges,condition_groups,nodes}.json` (REGENERATE) — the one-time renumber.
- `CLAUDE.md` (MODIFY) — the SPAN-ceiling Convention + the "⚠️ DO FIRST" note now resolved.

---

### Task 1: Widen the id domains + retire the shop sequential band

**Files:**
- Modify: `kg_ingest/assemble.py` (constants `:46-48`, docstring `:11-13`, shop block `~:499-516`)
- Modify: `tests/kg_ingest/test_assemble.py` (`:18`, `:27`, `:72-74`, `:85-86`)
- Regenerate: `kg/edges.json`, `kg/condition_groups.json`, `kg/nodes.json`

**Interfaces:**
- `stable_group_id`/`stable_edge_id`/`_stable_int`/`rekey` signatures unchanged — only the module-level constants
  `GROUP_OFFSET`/`EDGE_OFFSET`/`SPAN` change value.

- [ ] **Step 1: Update the test domain bounds + collision values FIRST (red against old constants)**

In `tests/kg_ingest/test_assemble.py`:
- The group-domain assertion (currently `assert 4_000_000 <= a < 6_000_000`) →
```python
    assert (1 << 49) <= a < (1 << 49) + (1 << 48)
```
- The edge-domain assertion (currently `assert 6_000_000 <= e < 8_000_000`) →
```python
    assert (1 << 50) <= e < (1 << 50) + (1 << 48)
```
- The group-collision test (currently monkeypatches `stable_group_id` → `4_000_000` and matches
  `"group id collision at 4000000"`) →
```python
    monkeypatch.setattr(A, "stable_group_id", lambda owner, idx: 1 << 49)
    ...
    with pytest.raises(ValueError, match=f"group id collision at {1 << 49}"):
```
- The edge-collision test (currently monkeypatches `stable_edge_id` → `6_000_000` and matches
  `"edge id collision at 6000000"`) →
```python
    monkeypatch.setattr(A, "stable_edge_id", lambda owner, idx: 1 << 50)
    ...
    with pytest.raises(ValueError, match=f"edge id collision at {1 << 50}"):
```
Read the file first to match the exact surrounding lines (the `match=` strings and the assert variable names).

- [ ] **Step 2: Run those tests — verify they FAIL against the current 2M constants**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_assemble.py -q`
Expected: the domain-bound + collision tests FAIL (old ids are in the 4M/6M domains, not `1<<49`/`1<<50`).

- [ ] **Step 3: Change the three constants + the docstring in `kg_ingest/assemble.py`**

Replace:
```python
GROUP_OFFSET = 4_000_000
EDGE_OFFSET = 6_000_000
SPAN = 2_000_000
```
with:
```python
GROUP_OFFSET = 1 << 49          # group ids in [2^49, 2^49+SPAN)
EDGE_OFFSET = 1 << 50           # edge  ids in [2^50, 2^50+SPAN) — disjoint from groups
SPAN = 1 << 48                  # hash window; collisions negligible at any graph size, ids stay < 2^53 (JS-safe)
```
And update the docstring lines (currently `GROUP_OFFSET (4M) and EDGE_OFFSET (6M) are disjoint 2M-wide domains.`) to:
```
GROUP_OFFSET (1<<49) and EDGE_OFFSET (1<<50) are disjoint SPAN(=1<<48)-wide domains, both < 2^53 (JS-safe).
SPAN=1<<48 keeps sha1-mod-SPAN collisions negligible at any realistic graph size (rekey still fail-fasts on one).
```

- [ ] **Step 4: Retire the shop sequential band — replace it with the standard seeded rekey**

Read `kg_ingest/assemble.py` around the `build_shops` wiring (the block containing `_SHOP_EDGE_BASE = 100_000_000`
and `sh_edges = [Edge(id=_SHOP_EDGE_BASE + i, ...) for i, e in enumerate(...)]`). Replace the sequential-id
construction with the seeded `rekey` shape used by the `build_storeline` block directly above it:
```python
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
Delete the `_SHOP_EDGE_BASE` constant and its explanatory comment. Keep the surrounding guard
(`if _map is not None and _shop_ib is not None:`) and the `_place_nodes`/`_varrock_names` setup exactly as they are.

- [ ] **Step 5: Regenerate the graph + run the updated assemble tests (green)**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python -m pytest tests/kg_ingest/test_assemble.py -q
```
Expected: assemble succeeds (the uniqueness assert passes → the widened scheme is collision-free for the real
graph); the domain-bound + collision tests now PASS.

- [ ] **Step 6: Prove byte-stability + verify the renumber moved every edge into the new domain**

```bash
./venv/bin/python -m kg_ingest.assemble && git status --porcelain kg/ && echo "BYTE-STABLE (empty above)"
./venv/bin/python -c "import json; e=[x['id'] for x in json.load(open('kg/edges.json'))]; print('edges', len(e), 'unique', len(set(e)), 'min', min(e), 'max', max(e)); assert all((1<<50) <= i < (1<<50)+(1<<48) for i in e), 'an edge id is outside the new domain'; print('all edge ids in [2^50, 2^50+2^48) — shop band gone')"
```
Expected: re-run leaves `kg/` unchanged after the first regenerate; all 9337 edge ids unique and inside
`[2^50, 2^50+2^48)` (no `[100M,…)` shop ids remain).

- [ ] **Step 7: Run every gate + the full suite**

```bash
for g in validate_kg validate_cost verify_shops verify_shop_coverage verify_equipment_bonuses; do ./venv/bin/python data/$g.py >/dev/null 2>&1; echo "$g exit $?"; done
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: every gate exit 0; full suite green (865 passed + the 4 pre-existing drop_rates collection errors).

- [ ] **Step 8: Commit**

```bash
git add kg_ingest/assemble.py tests/kg_ingest/test_assemble.py kg/nodes.json kg/edges.json kg/condition_groups.json
git commit -m "feat(edge-id): widen SPAN to 1<<48 + retire shop sequential band (one-time renumber)"
```

---

### Task 2: Docs — revert shops.py comments + update CLAUDE.md

**Files:**
- Modify: `kg_ingest/builders/shops.py` (the PR #21 sequential-id comments)
- Modify: `CLAUDE.md` (the SPAN Convention + the "⚠️ DO FIRST" note)

- [ ] **Step 1: Revert the shops.py edge-id comments**

In `kg_ingest/builders/shops.py`, the module-header docstring line and the `_EDGE_BAND` comment were changed in
PR #21 to describe assemble's *sequential overwrite*. Now that shop edges rekey normally again, restore the
"shop-`src` → assemble re-keys them in their own seeded call" wording (matching the other builders). No code
change — only the two comments. (Read the file to find the exact current comment text.)

- [ ] **Step 2: Update CLAUDE.md**

- The "← NOW" section line `**⚠️ DO FIRST, before the next layer: widen `assemble.SPAN` …**` — remove it (done).
- The Conventions bullet `**⚠️ `stable_edge_id`'s `SPAN=2_000_000` is an edge-id CEILING…**` — rewrite to record
  the resolution: `SPAN` is now `1<<48` (collisions negligible; ids < 2⁵³ JS-safe; group `1<<49` / edge `1<<50`
  disjoint domains), shop edges rekey normally (the sequential band was retired), and `rekey` still fail-fasts.
- The Status line edge count is unchanged (9337 — only ids moved), so leave the counts; optionally note the
  edge-id scheme was widened.

- [ ] **Step 3: Verify nothing regenerated + commit**

```bash
./venv/bin/python -m kg_ingest.assemble && git status --porcelain kg/   # empty — comments/docs don't touch output
git add kg_ingest/builders/shops.py CLAUDE.md
git commit -m "docs(edge-id): revert shops.py sequential-id comments + record SPAN widen in CLAUDE.md"
```

---

## Self-Review (planner)

- **Spec coverage:** §3 constants → Task 1 Step 3; §4 retire band → Task 1 Step 4; §5 blast radius (test_assemble
  only) → Task 1 Steps 1-2; §6 verification → Task 1 Steps 5-7; CLAUDE.md → Task 2.
- **No placeholders:** the constants, the rekey replacement, and the test edits are given verbatim; the only
  "read the file to match exact lines" notes are for comment text whose surrounding context the implementer must
  match (not logic).
- **Type consistency:** constant names (`GROUP_OFFSET`/`EDGE_OFFSET`/`SPAN`) and the `rekey(..., edge_index_seed=)`
  signature match the existing code; the seeded-rekey block mirrors the committed `build_storeline` block.
