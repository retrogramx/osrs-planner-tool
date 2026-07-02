# Recipe-id stability — Design

> **Status:** approved (brainstorm 2026-07-01, on `main` after the all-makeable slice `e60818e`).
> Makes every roster `recipe:` id a pure function of the recipe's intrinsic content, so ids survive
> re-derivation (Bucket row-order and sibling-count changes). Owner chose a **frozen readable-slug
> registry seeded from the current graph** → **zero id churn now** + a `validate_kg` stability invariant.
> Related: [[project_recipe_id_stability]], [[project_recipe_layer]].

## 1. Problem (measured)

The roster slug scheme (`build_recipe_roster`) disambiguates *only when needed*: a recipe gets a bare
slug (`recipe:crystal-bow`) when its wiki page has one makeable row, and a method suffix
(`recipe:crystal-bow-crafting`) once the page has 2+. Two consequences, both order/population-dependent:

- **Sibling-count churn:** adding rows (a new layer, a filter change) silently re-keys already-built
  recipes — the all-makeable slice re-slugged **19** slice-1 ids this way (payloads preserved, only the
  id moved).
- **Row-order churn:** the `-k` collision guard assigns `recipe:aether-rune-2/-3/-4` in Bucket
  **snapshot row order**. Measured: **816 / 4548 (17.9%)** recipe ids are genuine order-dependent
  collision guards. The graph is byte-stable *given the committed snapshot*, but ~1-in-5 recipe ids
  would reshuffle on a future wiki re-fetch that reorders rows.

Recipe nodes are the graph's stable addresses (competency questions, demo scripts, and any future
inbound edges reference them by id). The fix makes the id intrinsic and order-independent.

## 2. The identity key (what pins an id) — measured injective

A recipe's **identity key** = a deterministic hash over its intrinsic, resolved payload **plus** its
method label:

- sorted `consumes` `(item_id, qty, role)` (role ∈ material|tool)
- sorted `produces` `(item_id, qty)`
- sorted `requires_facility` `facility_id`
- sorted `requires` skill-gates `(skill_id, threshold)`
- `slugify(subtxt)` — the production-method label

Only **resolved** payload is included (the builder skips unresolvable materials/facilities — §5 recipe
layer — so the graph carries only resolved edges; the identity key matches by construction). Intrinsic
node `data` fields (`xp`, `ticks`, `members`) are **excluded** — they are properties, not identity, and
including them would couple the id to volatile data.

**Live-measured over the current 4548 recipe nodes** (payload alone → 4526 distinct; payload + subtxt →
**4544 distinct keys**). Adding subtxt cleanly separates "same cost, different source" recipes (imbued
rings via Nightmare Zone vs Soul Wars; potions via Brew'ma vs Herblore; first-time vs subsequent forge
recipes). The committed **roster registry excludes the 2 charge recipes**, so it holds **4542 identities
/ 4546 slugs** (= the 4546 roster recipes). The residual **7 recipes in 3 groups** collapse to one
identity each: **`small-chocolate-egg` ×3** is a genuine SAME-PAGE duplicate (fully interchangeable); the
two **`accursed-sceptre-u`** groups (4 recipes) are the SAME recipe documented on both `/w/Accursed_sceptre`
and its `/w/Accursed_sceptre_(a)` variant page — identical payload, **different source page**.

**Consequence for stability:** a recipe keeps its id across rebuilds as long as its
materials/facility/skill/method are unchanged. Row order and sibling count never affect a recipe's id or
edges. **Narrow residual (disclosed):** for a same-payload duplicate documented on multiple pages (the 4
`accursed-sceptre-u` recipes), the node ids and edges are stable, but *which* of the two interchangeable
nodes carries *which* (both-valid) `source_url`/`source_token` is assigned by emission order — a cosmetic
provenance detail, not an id/edge change, and any future swap is caught by the byte-stability gate (never
silent). Including `page` in the identity would wrongly model one real recipe as two, so it is deliberately
excluded. A genuine wiki *data* change to a recipe's materials/facility/skill re-addresses that one recipe
(rare, disclosed by the verifier).

## 3. The registry — `data/recipe_slug_registry.json`

A committed map, **seeded once from the current committed graph** so every existing recipe pins to its
current id (**zero churn**). Shape:

```json
{
  "recipes": {
    "<identity_hash_hex>": {"slugs": ["small-chocolate-egg", "small-chocolate-egg-2",
                                      "small-chocolate-egg-3"], "output": "Small chocolate egg"}
  }
}
```

- **Key** = the identity hash (§2). **Value.slugs** = the frozen slug(s) for that identity, a list to
  carry true-duplicate groups (length 1 for 4539 keys; length 2–3 for the 3 dupe keys → 4542 identities /
  4546 roster slugs total). **Value.output**
  = the human-readable output name, for owner review of the committed diff (advisory; not load-bearing).
- **Append-only:** existing entries are never rewritten. New recipes mint a fresh readable slug (output
  + method subtxt, guarded against every slug already in the registry) appended as a new entry. Once
  minted, a slug is frozen and never recomputed.
- The registry scope is the **roster** builder only. Charge recipes (`build_recipes`,
  `data/charge_recipes.json`) have hand-authored stable slugs and stay out; the roster keeps *reserving*
  them (existing `existing_recipe_slugs` mechanism).

## 4. Build flow — `build_recipe_roster` reads the registry (assemble stays pure + byte-stable)

The builder currently assigns the slug at emission time from `slugify(output)` + `multi`/`-k`. Change it
to a **registry lookup**:

1. Resolve each makeable recipe's payload (materials/tools/facility/skill) — as today, but computed
   *before* slug assignment so the identity key is available.
2. Compute the identity hash; group makeable rows by identity hash in **emission order** (the committed
   `makeable` order — deterministic given the snapshot).
3. For each group, look up `registry[hash].slugs` and assign them to the group's rows **in emission
   order**. Genuine same-page dupes are byte-identical (fully interchangeable); for a same-payload
   duplicate documented on multiple pages (the `accursed-sceptre-u` case, §2), ids and edges are stable
   but the emission-order assignment decides which node carries which (both-valid) `source_url` — a
   cosmetic provenance detail, gate-caught.
4. **Fail fast** if a recipe's identity hash is absent, or a group has more rows than registered slugs
   (a genuinely new/changed recipe): raise with a clear message —
   `"N unregistered recipes — run data/update_recipe_registry.py"`.

Assemble **never writes** the registry — it is a pure read, so `kg/*.json` stays byte-deterministic. The
`multi` flag and the emission-time `-k` guard are removed from the builder (the registry is now the sole
source of slugs).

## 5. Registry maintenance — `scripts/update_recipe_registry.py`

A committed, deterministic tool (like the `fetch_*` snapshotters): reads the recipe rows + item
dictionary + facility nodes + current registry, computes each recipe's identity hash, and for any
**unregistered** identity mints a readable slug — `slugify(output)` + `-slugify(subtxt)` when a subtxt
exists, `-k` guarded against **all** existing registry slugs — appending a new entry. For a new row that
extends an existing true-dupe group, it appends one more slug to that entry's list. Existing entries are
never rewritten. Writes the updated registry (sorted deterministically). Re-run with nothing new = a
byte-stable no-op. Run deliberately when recipes change; the diff is owner-reviewed + committed.

The **initial seed** is this same tool in a one-time seed mode (or a `--seed` flag): it reads the
*current committed graph* and emits the registry that pins every existing id to itself. Acceptance test:
seed → re-run assemble → `kg/*.json` byte-identical to `main` (zero churn).

## 6. The invariant — `validate_kg` (hard-fail) + `verify_recipe_ids.py` (report)

`validate_kg` hard-fails if:

- two recipe nodes share an id (reaffirms node-id uniqueness for the roster);
- any roster recipe's id is not one of `registry[identity_hash(recipe)].slugs` (id not derived from the
  registry — catches an id that drifted from its intrinsic content);
- the registry is not a bijection on slugs (a slug appears under two identity hashes, or twice in one
  entry).

`verify_recipe_ids.py` (report-not-fail, exit 0) discloses: registry size, count of roster recipes, any
recipes whose identity hash is unregistered (should be 0 on a committed graph), and the true-dupe groups.

Append-only-across-git-history is a review discipline (not snapshot-checkable) — noted here, enforced in
review, not in `validate_kg`.

## 7. Verification & testing

- Same gates: **byte-stable assemble** (the seed acceptance test *is* the zero-churn proof),
  `validate_kg` exit 0, `verify_recipes` still PASSED (grounding unchanged), full pytest green.
- Builder fixture tests: (a) a recipe's id is taken from the registry, not recomputed; (b) row-order
  independence — permuting the input rows yields the same id→recipe mapping; (c) an unregistered recipe
  **fails the build** with the expected message; (d) a true-dupe group (identical payload+subtxt) maps
  to its frozen slug list deterministically.
- Registry-updater tests: seeding the current graph reproduces the committed ids; a new recipe mints a
  fresh guarded slug and appends (existing entries untouched); re-run is a byte-stable no-op.
- `validate_kg` tests: id-not-from-registry and duplicate-slug both hard-fail.

## 8. Scope / non-goals

- **Charge recipes** stay out of the registry (hand-authored stable slugs; roster keeps reserving them).
- The cosmetic `-k` ids (`recipe:aether-rune-3`) **freeze as-is** — zero-churn is the priority. A future
  optional "re-mint readable slugs" pass could clean them at a one-time, owner-reviewed churn; out of
  scope here.
- No change to edges, node `data`, or the 2 competency-question ids (`recipe:bronze-platebody`,
  `recipe:charge-scythe-of-vitur`) — both survive zero-churn seeding.
- The 816 order-dependent ids are *frozen*, not renamed — this slice removes the *mechanism* that would
  churn them on re-derivation, it does not relabel them.
