# Recipe Layer — All Makeable (output-based) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the recipe layer's skill filter with an output filter — ingest every `Bucket:recipe` row whose output resolves to an item — capturing ~2,256 new recipes (the 1,832 no-skill combinations + 424 non-core skilled).

**Architecture:** Delete one filter line in the existing `build_recipe_roster`; the builder then keeps any row with a resolvable output (the `if out_dst is None: continue` already there). No-skill recipes fall out naturally as `recipe:` nodes with `consumes`/`produces` and no `requires`/`xp`. Reframe the coverage verifier from per-core-skill to output-based. Regenerate the committed graph.

**Tech Stack:** Python 3.14 via `./venv/bin/python`; committed JSON graph; `pytest`.

## Global Constraints

- Run Python ONLY via `./venv/bin/python` (3.14).
- **Byte-stable assemble:** re-running `./venv/bin/python -m kg_ingest.assemble` produces identical `kg/*.json`.
- **Never fabricate:** unresolvable output → recipe skipped; unresolvable material/tool/facility → edge skipped; all disclosed by the coverage verifier. Every recipe node keeps its verbatim `source_token`.
- `data/validate_kg.py` exits 0; `verify_recipes.py` exits 0 (structural hard-fail); full `pytest -q --continue-on-collection-errors` green (the 4 `tests/drop_rates/` collection errors are pre-existing & unrelated).
- **Near-superset:** removing the filter only ADDS rows and preserves all slice-1 recipe *data*, BUT re-slugs **19** slice-1 recipe ids (a page gaining a sibling method flips the `multi` disambiguation → the original recipe inherits its `-<method>` suffix; payloads preserved verbatim, only the id moves — owner-blessed deviation, spec §8). NOT byte-identical. Recipe-id stability (the pre-existing ~424 order-dependent ids on `main`) is deferred to its own next slice.
- Pre-flight (validated): output-based build = **4,546 recipe nodes** (2,290 core + 1,832 no-skill + 424 non-core); edges consumes 10,168 / produces 4,546 / requires_facility 1,467 / requires 2,714; **1,847 new item auto-imports** (item roster ~4,050 → ~5,900).
- Work on branch `feat/recipe-noncore` (the spec is committed there). Commit after each task.

## File Structure

**Modify:**
- `kg_ingest/builders/recipes.py` — delete the `CORE_SKILLS` filter (lines 100-101); rename the local `core` list → `makeable` for clarity; (Task 2) delete the now-orphaned `CORE_SKILLS` constant.
- `tests/kg_ingest/test_recipe_roster_builder.py` — add a no-skill-recipe test; (Task 2) drop the unused `CORE_SKILLS` import.
- `tests/kg_ingest/test_recipes_roster_in_graph.py` — tighten the recipe/requires_facility count lower bounds.
- `kg/{nodes,edges,condition_groups}.json` — regenerated.
- `data/verify_recipe_coverage.py` — reframe from per-core-skill to output-based.
- (Contingent) a root brick, IF the 1,847-item auto-import surfaces a latent bug (as slice 1's did for `equipment_bonuses`).

---

### Task 1: Output-based builder + regenerate graph

**Files:**
- Modify: `kg_ingest/builders/recipes.py` (delete filter lines 100-101; rename `core`→`makeable`)
- Modify: `tests/kg_ingest/test_recipe_roster_builder.py` (add no-skill test)
- Modify: `tests/kg_ingest/test_recipes_roster_in_graph.py` (tighten count bounds)
- Modify: `kg/{nodes,edges,condition_groups}.json` (regenerated)

**Interfaces:**
- `build_recipe_roster(recipe_rows, item_dict_records, facility_nodes, existing_recipe_slugs)` — signature unchanged; behavior widens from core-skill-only to any-resolvable-output.

- [ ] **Step 1: Write the failing no-skill test (append to `tests/kg_ingest/test_recipe_roster_builder.py`)**

```python
def test_no_skill_recipe_builds_without_requires_or_xp():
    # a resolvable-output recipe with NO uses_skill -> should build as consumes/produces, no requires/xp
    rows = [_row("Combined thing", None, None, None,
                {"materials": [{"quantity": "1", "name": "Bronze bar"}],
                 "output": {"quantity": "1", "name": "Bronze dagger"}})]   # note: NO "skills" key
    nodes, edges, groups = build_recipe_roster(rows, _itemdict(), _facilities(), set())
    n = _map(nodes)["recipe:bronze-dagger"]
    assert "xp" not in n.data                                              # no skill -> no xp key
    assert groups == {}                                                    # no skill gate -> no cond_group
    assert not any(e.type is EdgeType.REQUIRES for e in edges)             # no requires edge
    assert any(e.type is EdgeType.CONSUMES for e in edges)                 # consumes still emitted
    assert any(e.type is EdgeType.PRODUCES for e in edges)                 # produces still emitted
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_recipe_roster_builder.py::test_no_skill_recipe_builds_without_requires_or_xp -q`
Expected: FAIL (`KeyError: 'recipe:bronze-dagger'` — the current `CORE_SKILLS` filter skips the no-skill row so the node isn't built).

- [ ] **Step 3: Delete the skill filter + rename the local list**

In `kg_ingest/builders/recipes.py`, in `build_recipe_roster`, DELETE these two lines (currently lines 100-101):

```python
        if not ({s for s in _as_list(r.get("uses_skill")) if s} & CORE_SKILLS):
            continue
```

Then rename the local accumulator `core` → `makeable` for accuracy (it's no longer core-skill-scoped). It appears in three places in the function — the initialization, the `.append(...)` inside the first loop, and the `Counter(...)` + `for ... in core` that follow. Rename all occurrences of the local `core` to `makeable`:

```python
    makeable = []
    for r in recipe_rows:
        try:
            pj = json.loads(r.get("production_json") or "{}")
        except Exception:
            pj = {}
        out = pj.get("output")
        if not (isinstance(out, dict) and out.get("name")):
            continue  # output-less activity -> deferred
        makeable.append((r, pj, out))
    page_rows = Counter(r.get("page_name") for r, _, _ in makeable)
    ...
    for r, pj, out in makeable:
        ...
```
(Leave the `CORE_SKILLS` constant at line ~59 in place for now — the coverage verifier + a test still import it; Task 2 removes it.)

- [ ] **Step 4: Run the builder tests (RED→GREEN) + the full builder file**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_recipe_roster_builder.py -q`
Expected: PASS (the new no-skill test + all existing slice-1 builder tests — they used core-skill fixtures, which still build).

- [ ] **Step 5: Regenerate the graph + verify the gates**

```bash
./venv/bin/python -m kg_ingest.assemble
./venv/bin/python data/validate_kg.py; echo "validate_kg exit=$?"
```
Expected: assemble prints no error (2 deterministic slug-collision lines are fine); `validate_kg` exit 0. Report counts:
`./venv/bin/python -c "import json; n=json.load(open('kg/nodes.json')); print('nodes',len(n),'edges',len(json.load(open('kg/edges.json'))),'recipes',sum(1 for x in n if x['id'].startswith('recipe:')))"`
Expected ≈ 4,548 recipes (4,546 roster + 2 charge), item roster grown by ~1,847.

**IMPORTANT — blast radius:** the ~1,847-item auto-import may surface a LATENT bug in another brick (the CLAUDE.md gotcha; slice 1 hit it in `equipment_bonuses`). If assemble or a test fails with an error in a NON-recipe brick, fix the ROOT brick (report what you changed). If you hit a failure you cannot resolve, report BLOCKED with the exact traceback. Do NOT hand-edit `kg/*.json` and do NOT weaken `validate_kg`.

- [ ] **Step 6: Byte-stability + tighten the in-graph count bounds**

Run assemble a second time; confirm `kg/nodes.json` is byte-identical (or use the byte-stable test below). In `tests/kg_ingest/test_recipes_roster_in_graph.py`, update the two loose lower bounds to reflect the larger roster:
- `assert len(recipes) >= 1500` → `assert len(recipes) >= 4000`
- `assert len(rf) >= 500` → `assert len(rf) >= 1000`

- [ ] **Step 7: Run the in-graph test + the full suite**

```bash
./venv/bin/python -m pytest tests/kg_ingest/test_recipes_roster_in_graph.py -q
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: in-graph PASS (incl. byte-stability + `verify_recipes` smoke test); full suite green (modulo the 4 pre-existing `tests/drop_rates/` errors + any root-brick fix from Step 5).

- [ ] **Step 8: Commit**

```bash
git add kg_ingest/builders/recipes.py tests/kg_ingest/test_recipe_roster_builder.py tests/kg_ingest/test_recipes_roster_in_graph.py kg/nodes.json kg/edges.json kg/condition_groups.json
git commit -m "feat(recipe-all-makeable): output-based filter (drop skill gate) — +~2256 recipes incl. no-skill combinations"
```
(If Step 5 required a root-brick fix, `git add` that file too and mention it in the commit body.)

---

### Task 2: Reframe the coverage verifier (output-based) + drop the orphaned CORE_SKILLS

**Files:**
- Modify: `data/verify_recipe_coverage.py` (output-based report; drop `CORE_SKILLS`)
- Modify: `kg_ingest/builders/recipes.py` (delete the now-unused `CORE_SKILLS` constant)
- Modify: `tests/kg_ingest/test_recipe_roster_builder.py` (drop the unused `CORE_SKILLS` import)

**Interfaces:**
- `verify_recipe_coverage.py` — reports `output rows / built / skipped-by-skill` over ALL skills (no core filter). Reuses only `_as_list` from the builder.

- [ ] **Step 1: Reframe the coverage verifier**

In `data/verify_recipe_coverage.py`:
1. Change the import to drop `CORE_SKILLS`: `from kg_ingest.builders.recipes import _as_list`.
2. Replace the per-core-skill loop body + report with an output-based one. The loop currently does `sk = {...} & CORE_SKILLS` then `if not sk: continue`. Replace the counting + report block so every row with a structured output is counted (buildable vs skipped), and skips are bucketed by skill:

```python
    from collections import Counter
    out_rows = 0
    built = 0
    unres_out, unres_mat, unres_fac = [], set(), set()
    skip_by_skill = Counter()
    for r in rows:
        try:
            pj = json.loads(r.get("production_json") or "{}")
        except Exception:
            pj = {}
        o = pj.get("output")
        if not (isinstance(o, dict) and o.get("name")):
            continue                                      # output-less activity -> not a make-recipe
        out_rows += 1
        if ri(o["name"]) is None:
            unres_out.append(o["name"])
            for s in ({s for s in _as_list(r.get("uses_skill")) if s} or {"(no skill)"}):
                skip_by_skill[s] += 1
            continue
        built += 1
        for m in (pj.get("materials") or []):
            if m.get("name") and ri(m["name"]) is None:
                unres_mat.add(m["name"])
        for f in _as_list(r.get("uses_facility")):
            if (f or "").strip() and (f or "").strip() not in fac_names:
                unres_fac.add((f or "").strip())

    print("RECIPE COVERAGE (report-not-fail):")
    print(f"  rows with a structured output: {out_rows}")
    print(f"  recipes built (resolvable output): {built}")
    print(f"  skipped (unresolvable output): {len(set(unres_out))} distinct; by skill: {dict(skip_by_skill.most_common(8))}")
    for n in sorted(set(unres_out))[:20]:
        print("     -", n)
    print(f"  unresolved MATERIAL/TOOL names (edge skipped): {len(unres_mat)}")
    for m in sorted(unres_mat)[:20]:
        print("     -", m)
    print(f"  unresolved FACILITIES (no requires_facility): {len(unres_fac)}")
    for f in sorted(unres_fac)[:20]:
        print("     -", f)
    return 0
```
(Keep the existing `rows` / `recs` / `fac_names` / `ri` setup at the top of `main()` — only the counting loop + report change. `ri` is the existing `html.unescape` + resolver closure.)

- [ ] **Step 2: Run the coverage verifier (report the output)**

Run: `./venv/bin/python data/verify_recipe_coverage.py; echo "exit=$?"`
Expected: exit 0. Output shows ~5,380 output rows, ~4,546 built, ~834 skipped dominated by Construction/Sailing. INCLUDE the full output in the task report.

- [ ] **Step 3: Delete the orphaned `CORE_SKILLS`**

Now that nothing filters on it, delete the `CORE_SKILLS = {...}` constant line (~line 59) in `kg_ingest/builders/recipes.py`, and remove `CORE_SKILLS` from the import in `tests/kg_ingest/test_recipe_roster_builder.py` (change `from kg_ingest.builders.recipes import build_recipe_roster, CORE_SKILLS` → `from kg_ingest.builders.recipes import build_recipe_roster`). Confirm nothing else references it: `grep -rn "CORE_SKILLS" kg_ingest/ data/ tests/` must return nothing.

- [ ] **Step 4: Run the affected tests + full suite**

```bash
./venv/bin/python -m pytest tests/kg_ingest/test_recipe_roster_builder.py -q
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: PASS (the builder tests import cleanly without `CORE_SKILLS`; full suite green).

- [ ] **Step 5: Commit**

```bash
git add data/verify_recipe_coverage.py kg_ingest/builders/recipes.py tests/kg_ingest/test_recipe_roster_builder.py
git commit -m "feat(recipe-all-makeable): reframe coverage verifier to output-based + drop orphaned CORE_SKILLS"
```

---

### Final: full gate + coverage review

- [ ] **Run the full gate**

```bash
./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python data/validate_kg.py
./venv/bin/python data/verify_recipes.py
./venv/bin/python data/verify_recipe_coverage.py
./venv/bin/python -m pytest -q --continue-on-collection-errors
```
Expected: byte-stable; validate_kg 0; verify_recipes PASSED (~4,546 grounded); coverage exit 0; pytest green. Surface the final graph size (~10,400 → ~14,000 nodes with the item auto-import) + the coverage residuals to the owner.

## Self-Review notes (spec coverage)

- Spec §2 (delete the skill filter; builder output-driven; coverage reframe; tests update) → Task 1 (builder + tests) + Task 2 (coverage + orphan cleanup). ✅
- Spec §3 (scope: 5,380 output rows → 4,546 buildable, ~2,256 new) → Task 1 Step 5 count check + Task 2 coverage report. ✅
- Spec §4 (no-skill recipes = node without requires/xp) → Task 1 Step 1 test proves it. ✅
- Spec §5 (confirmed shapes; blast-radius risk) → Task 1 Step 5 blast-radius handling (root-brick fix if needed). ✅
- Spec §6 (verification) → Task 1 gates + Task 2 coverage + Final. ✅
- Spec §7 (deferrals auto-skipped) → enforced by the output-resolution skip (no code path builds an unresolvable-output recipe). ✅
- Spec §8 (19 slice-1 recipe ids re-slugged; payloads preserved; recipe-id stability deferred) → surfaced by the whole-branch review, verified by payload-signature diff, owner-blessed. NOT byte-identical to slice 1. ✅
