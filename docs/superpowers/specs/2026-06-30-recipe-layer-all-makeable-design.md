# Recipe Layer — slice 2: all makeable recipes (output-based) — Design

> **Status:** approved (brainstorm 2026-06-30; pivoted from "non-core skills" to output-based after
> the owner surfaced 1,832 no-skill make-recipes the skill filter missed). A small additive change
> to the merged recipe layer ([[project_recipe_layer]], PR #25): **replace the skill filter with an
> output filter** — ingest every recipe whose output resolves to an item, regardless of skill.

## 1. Goal

Complete the "how do I make X" coverage: ingest **every** `Bucket:recipe` row whose output resolves
to a real item — not just recipes tagged with an in-scope skill. This captures the large body of
**no-skill make-recipes** (ornament kits, poison, part-assembly, item combinations) that slice 1's
skill filter skipped, plus the non-core skilled recipes.

## 2. The change (delete the skill filter; the builder becomes output-driven)

Slice 1's builder filters `if not (sks & CORE_SKILLS): continue`. **Remove that filter.** The builder
then processes every row and keeps it iff its output resolves (`if out_dst is None: continue`, which
already exists). Nothing else about node/edge construction changes — the skill-gate (`requires`) and
`xp` are already built from each recipe's *own* `skills` list, so they simply don't appear when a
recipe has no skill.

- `kg_ingest/builders/recipes.py`: delete the `CORE_SKILLS` filter line (and the now-unused
  `CORE_SKILLS` import/definition in the builder). The layer is defined by *resolvable output*, not skill.
- `data/verify_recipe_coverage.py`: reframe from per-core-skill to **output-based**: report `output rows`,
  `buildable (resolvable output)`, and the itemized `skipped (unresolvable output)` residual broken down
  by skill (which discloses that the skips are dominated by Construction/Sailing scenery).
- Tests: update the builder/coverage tests that assumed a skill filter — a **no-skill recipe now BUILDS**
  (recipe node + `consumes`/`produces`, no `requires`, no `xp`), where slice 1 skipped it.
- Everything else — item/facility resolution, the four edge types, per-skill xp dict, slug scheme,
  `verify_recipes`, assemble wiring — is **unchanged**. Byte-stable re-assemble; **near-superset** of
  slice 1 (all slice-1 recipe *data* preserved; **19 core recipe ids are re-slugged** by method-
  disambiguation — see §8), purely additive.

## 3. Live-measured scope (committed snapshot)

- Rows with a structured output: **5,380**. Resolvable → **4,546 buildable** (the full roster).
  Unresolvable → **834 skipped** (disclosed).
- Buildable breakdown: 2,290 already-built (core skill) + **1,832 NEW no-skill** + **424 NEW non-core
  skilled** = **~2,256 new recipes**. Recipe roster ~2,292 → **~4,548** (+2 charge).
- Skipped-output residual (834) is dominated by **Construction 672** (POH scenery), **Sailing 152**
  (unsourced items), + small tails (Herblore 62, Farming 30, …) — all correctly auto-skipped because
  their output is not an inventory item.

## 4. No-skill / no-xp recipes (the owner's question, answered)

A make-recipe that needs no skill and grants no XP is a first-class `recipe:` node that simply **omits
the optional facets**: no `requires` edge (no `skill_level` atoms → `if atoms:` is false) and no
`data.xp` key (no numeric xp → `if xp:` is false). It keeps `consumes` (materials/tools) + `produces`
(+ `requires_facility` if any). E.g. `Abyssal tentacle` = `consumes` Abyssal whip + Kraken tentacle,
`produces` Abyssal tentacle — no `requires`, no `xp`. The reified model needs nothing new to store it.

## 5. Confirmed shapes (spot-checked live — no new edge cases)

- Non-core skilled: **Magic** multi-skill (Superheat = Smithing+Magic → per-skill xp dict + 2-atom gate)
  + no-facility spells + lectern facilities; **Farming** tools (`Watering can`) + multi-material plant-pot
  recipes. **Zero multi-output** (`output` as a list) anywhere.
- No-skill: pure `consumes`→`produces` combinations (Abyssal tentacle/bludgeon, ornament-kit overrides,
  poison variants, part-assembly) — the builder emits them with no `requires`/`xp`.
- **Risk:** the item auto-import grows (materials of ~2,256 more recipes; larger than slice 1's ~2,600).
  Per the CLAUDE.md gotcha it *could* surface a latent bug in another brick — if so, fix the root brick
  (as slice 1 did for `equipment_bonuses`).

## 6. Verification & testing

- Same gates: byte-stable assemble, `validate_kg` exit 0, `verify_recipes` hard-fail PASSED (now
  ~4,546 grounded), `verify_recipe_coverage` report-not-fail (reframed to output-based), full pytest green.
- Add builder fixture tests: a **no-skill combination** (assert recipe node built, `consumes`+`produces`,
  NO `requires` edge, NO `xp`), a Magic **multi-skill + no-facility** recipe, a Farming **tool** recipe.
- Update the in-graph test lower bounds (recipe count ~2,292 → ~4,500; `requires_facility` ticks up).

## 7. Scope / non-goals (auto-skipped by output-resolution)

- The 834 unresolvable-output rows — **Construction** POH buildables (scenery), **mounted trophies**,
  **Sailing** (unsourced) → the future **scenery/objects layer** (`produces → scenery`).
- The ~1,898 output-less XP activities (Agility / Prayer-offerings / Thieving / gather-training) →
  a future **training-method** node kind (no output to produce).

## 8. Known deviation — 19 slice-1 recipe ids re-slugged (owner-blessed)

The slug scheme disambiguates only *when needed*: a recipe gets a bare slug (`recipe:crystal-bow`)
when its wiki page has one makeable row, and a method suffix (`recipe:crystal-bow-crafting`) once the
page has 2+. Admitting each page's previously-filtered sibling methods (mostly no-skill **NPC
recharge/combine** recipes — Ilfeen, Oziach, Abbot Langley, …) flips `multi` true on 19 single-method
pages, so those recipes inherit their `-<method>` suffix. **All 19 payloads (materials/tools/facility/
skill-gate/xp) are preserved verbatim — only the node id moved** (verified by payload-signature diff of
merge-base vs head). Nothing outside `kg/*.json` references the 19 ids (both competency-question recipe
ids survive), so the graph stays internally consistent.

This is NOT a strict byte-identical superset. It is the visible symptom of a slug scheme that was
never order-stable: **424/2292 (18.5%) of the recipe ids already on `main` are order-dependent
collision guards** (`recipe:aether-rune-3`, …) whose numeric suffix is assigned in Bucket-snapshot
row order. The graph is byte-stable given the committed snapshot, but ~1-in-5 recipe ids would
reshuffle on a future re-fetch that reorders rows. **Recipe-id stability is deferred to its own next
slice** — an intrinsic (content-addressed) slug + a `validate_kg` stability invariant, covering the
full order-dependent surface across both layers.
