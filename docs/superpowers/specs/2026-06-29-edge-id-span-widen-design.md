# Edge-id SPAN widen — Design

> **Status:** DESIGN (finalized 2026-06-29). Branch: `feat/edge-id-span-widen` (off `main`, all-shops layer
> merged PR #21). A small, self-contained pipeline change that pays down the PR #21 deviation: it removes the
> shop sequential-id band and lifts the `stable_edge_id`/`stable_group_id` collision ceiling so every edge can
> go back through the one deterministic `rekey` scheme.

---

## 1. Problem

`kg_ingest/assemble.py` mints global ids as `OFFSET + sha1("{owner}#e{idx}") % SPAN` with **`SPAN = 2_000_000`**.
The id is a pure function of `(owner, local_index)`, so an unrelated edge never renumbers others — **per-edge
id-stability (no churn)** is the scheme's virtue. But a 2M-wide hash window birthday-collides at ~9k total edges
(the committed graph is now 9,337 edges), and `rekey` **raises** on a collision (fail-fast, to avoid silent edge
loss). The all-shops layer (PR #21) hit this and worked around it by assigning its ~6k shop edges **sequential**
ids in a `[100_000_000, …)` band — which is collision-free but **loses id-stability**: one added/removed
Storeline row renumbers every later shop edge, churning `kg/edges.json` on each data refresh.

## 2. Decision (Approach A — widen, keep fail-fast)

Widen the hash window so collisions are negligible for any realistic graph, and **delete the shop sequential
band** so shop edges rejoin the normal seeded `rekey`. Keep the existing fail-fast-on-collision contract (the
widened window makes it effectively never trigger; if it ever did, it fails loudly, never silently).

Approach B (deterministic collision *resolution* so the build can never halt) was considered and **rejected** as
YAGNI: at the new window size a collision is a ~1-in-100,000 event even at 30× today's edge count, and it would
add new resolution logic + rewrite the collision-raise tests for a scenario that effectively never occurs.

## 3. Constants (the whole change, numerically)

In `kg_ingest/assemble.py`:
- **`SPAN = 1 << 48`** (281,474,976,710,656). Collision probability ≈ `n²/(2·SPAN)`: ~2e-7 at today's 9,337
  edges, ~1e-5 at 100k edges, ~1e-3 at 1M edges — negligible for any OSRS-scale graph.
- **`GROUP_OFFSET = 1 << 49`**, **`EDGE_OFFSET = 1 << 50`** — group ids ∈ `[2⁴⁹, 2⁴⁹+2⁴⁸)`, edge ids ∈
  `[2⁵⁰, 2⁵⁰+2⁴⁸)`: disjoint domains (debuggable by magnitude, preserves the existing test's spirit) and both
  **< 2⁵³** (JavaScript's safe-integer limit — the future public web UI consumes these ids as JSON numbers).

`_stable_int`, `stable_group_id`, `stable_edge_id`, and the whole `rekey` mechanism are otherwise unchanged.

## 4. Retire the shop sequential band

In `assemble.py`, the `build_shops` block currently builds `sh_edges` with `id = _SHOP_EDGE_BASE + i`
(`_SHOP_EDGE_BASE = 100_000_000`). Replace that with the standard seeded rekey (the shape every other shop-`src`
builder uses), mirroring the `build_storeline` block:
```python
sh_nodes, sh_edges, _ = build_shops(...)
_seed_sh = {}
for _e in edges:
    _seed_sh[_e.src] = _seed_sh.get(_e.src, 0) + 1
sh_nodes, sh_edges, _ = rekey(sh_nodes, sh_edges, {}, edge_index_seed=_seed_sh)
edges = edges + sh_edges
```
The builder-local `_edge_id`/`_EDGE_BAND` in `shops.py` become live placeholders again (rekey replaces them, as
for every other builder) — so the PR #21 "sequential overwrite" comments in `shops.py` revert to the normal
"rekey replaces it" wording.

## 5. Blast radius & non-goals

- **One-time renumber:** every edge id (`kg/edges.json`, and the `cond_group` refs) and every group id
  (`kg/condition_groups.json`, and `parent` refs) changes. This is a large, expected one-time diff; the build
  stays **byte-stable** thereafter (re-run = identical bytes).
- **Node ids are slugs — unchanged.** Only integer edge/group ids move.
- **Tests that query by semantics are unaffected** (golden set, competency, all builders/verifiers). The only
  test that hardcodes the id domains is `tests/kg_ingest/test_assemble.py` — its domain-bound assertions
  (`4M≤group<6M`, `6M≤edge<8M`) and its two collision-raise tests (which monkeypatch a fixed `4_000_000` /
  `6_000_000`) update to the new constants. The fail-fast *behavior* they assert is preserved.
- **Non-goals:** no change to the id *formula*, the per-`src` seeded-rekey discipline, or any builder logic; no
  collision resolution (Approach B); no schema change.

## 6. Verification (the gate)

- **Byte-stable:** `./venv/bin/python -m kg_ingest.assemble` re-run twice → identical bytes.
- `validate_kg` · `validate_cost` · `verify_shops` · `verify_shop_coverage` · `verify_equipment_bonuses` — all
  exit 0 (graph semantics unchanged; only ids moved).
- The committed-graph edge-id-uniqueness assert in `assemble.py` passes (it is the live proof the widened scheme
  is collision-free for the actual graph).
- **Shop edges are no longer in `[100M,…)`** — confirm min/max shop-sells edge id now falls in the new
  `EDGE_OFFSET` domain (the band is gone).
- Full suite green (the 4 `tests/drop_rates/` collection errors are pre-existing & unrelated).
- CLAUDE.md updated: the "⚠️ DO FIRST: widen SPAN" note becomes "done"; the SPAN-ceiling Convention reflects the
  new window + that shop edges rekey normally again.
