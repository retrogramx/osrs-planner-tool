# Charge Recipe Edges — Slice 2 (first edge-layer slice)

> **Status:** DESIGN (2026-06-25). The first **edge-layer** slice of build step 2/3 of the Entity-Graph Ontology v2
> (`2026-06-25-entity-graph-ontology-v2.md`). Branch: `feat/entity-graph-ontology`. Builds on the item node layer
> from `2026-06-25-node-import-items-slice1-design.md` (the variant nodes this slice connects already exist).

## 0. Why this slice

Slice 1 stood up the item **node** layer (page/variant/family identity). This is the first **edge** layer: the
**charging process** — consuming materials to refill a chargeable item — modeled as v2's reified `recipe` relation
(`recipe --consumes--> --produces-->`). It's the natural next step (the charged/uncharged endpoints already exist as
nodes), and it proves the recipe/consumes/produces model on a bounded, source-grounded set.

**Charge lifecycle context (3 composable edges over the same variant nodes):**
- **create/refill** (materials → charged) = `recipe`/`consumes`/`produces` — **THIS slice**.
- **deplete through use** (charged → less-charged → uncharged | destroyed) = a `degrades_to` downgrade ladder — **deferred** (§9).
- **cost-per-use** (gp per charge) = the cost layer, **derived** from this slice's recorded `charge_yield` — **deferred**.

## 1. Decisions (settled in brainstorming, 2026-06-25)

| # | Decision | Choice |
|---|---|---|
| 1 | Data source | **Curated `data/charge_recipes.json`** (editorial, source-grounded, verifier-gated) — mirrors `item_node_families.json` |
| 2 | Mechanic scope | **Consume-materials only** (no facility): Scythe of vitur + Ring of suffering |
| 3 | Recipe shape | `consumes`(materials `role:material` + uncharged `role:subject`) → `produces`(charged); record `charge_yield`/`charge_capacity` |
| 4 | Builder | **Generic `kg_ingest/builders/recipes.py`** (reads `charge_recipes.json` now; future crafting/smithing recipe slices reuse it) |
| 5 | Material import | Auto via the slice-1 referenced mechanism (recipe edges feed `referenced_item_ids`; `build_items` imports the materials) |
| 6 | Edge-id guard | **Add a global edge-id-uniqueness assert** in `assemble` (final-review forward recommendation; fail-fast for future item-`src` slices) |
| 7 | Deferred | facility-recharge, `degrades_to` (depletion incl. destroyed-terminal), cost-per-use, other charged items, recipe skill/quest gates |

## 2. Model additions (additive — spec permits new kind/edge)

- **`model.py`**: add `NodeKind.RECIPE = "recipe"`, `EdgeType.CONSUMES = "consumes"`, `EdgeType.PRODUCES = "produces"`.
  (The tested invariant `model-enum ⊆ schema` stays green — all three are already declared in `kg/schema.json`.)
- **`kg/schema.json`**: flip `recipe` (node), `consumes`, `produces` status `reserved` → `live`. Extend
  `node_kinds.recipe.data_keys` with `charge_yield`, `charge_capacity`, `notes`. Add a `vocab.consumes_role`
  enum `["material", "subject"]` (documentation for the builders; edge `data` is not schema-enforced).
- Existing declared domain/range (unchanged, now enforced): `consumes` `recipe → item`, `produces` `recipe → item`,
  both `dst: required`, both reified.
- **No `facility` / `requires_facility`** this slice.

## 3. The recipe model

`slugify` is `kg_ingest.ids.slugify`. Recipe node id `recipe:<slug>`.

**Recipe node** — the reified charging process:
- `id = recipe:<slug>` (e.g. `recipe:charge-scythe-of-vitur`), `kind = recipe`, `name` = display, `slug`
- `data = {"charge_yield": <int>, "charge_capacity": <int>, "notes"?: <str>}` (charge mechanics; the cost-per-use bridge)

**`consumes` edges** (recipe → item, one per material + one for the subject):
- `type = consumes`, `src = recipe:<slug>`, `dst = item:<id>`, `cond_group = None`
- `data = {"qty": <int>, "role": "material" | "subject"}` — `material` = a consumable (recurring) input;
  `subject` = the item being charged (transformed, not destroyed; the uncharged variant)

**`produces` edge** (recipe → item, the charged variant):
- `type = produces`, `src = recipe:<slug>`, `dst = item:<id>`, `cond_group = None`, `data = {"qty": 1}`

```
recipe:charge-scythe-of-vitur   {charge_yield, charge_capacity}
   --consumes {qty, role:material}--> item:11697  Blood rune          ← imported by build_items (referenced)
   --consumes {qty, role:material}--> item:22446  Vial of blood       ← imported by build_items (referenced)
   --consumes {qty:1, role:subject}-> item:22486  Scythe (uncharged)  ← already a node (slice-1 family)
   --produces {qty:1}--------------> item:22325  Scythe (charged)     ← already a node (slice-1 family)

recipe:charge-ring-of-suffering {charge_yield, charge_capacity}
   --consumes {qty, role:material}--> item:2550   Ring of recoil
   --consumes {qty:1, role:subject}-> item:19550  Ring of suffering (uncharged)
   --produces {qty:1}--------------> item:20655  Ring of suffering (r) (recoil)
```

`consumes`/`produces` are recipe-`src` edges — the cross-call `rekey` item-collision risk (final-review note) does
**not** trigger (no item node is an edge `src` here). Charge **quantities + yield are source-grounded and
owner-reviewed**, never fabricated.

## 4. Data + verifier (editorial)

### 4a. `data/charge_recipes.json` — curated, source-grounded
Each record carries `source_url` + a verbatim `source_token`. Shape:
```json
{ "_provenance": {"note": "curated item-charging recipes (consume-materials); editorial — owner-reviewed",
                  "license": "CC BY-NC-SA 3.0", "accessed": "..."},
  "records": [
    { "slug": "charge-scythe-of-vitur", "name": "Charge Scythe of vitur",
      "produces": {"item_id": 22325, "qty": 1},
      "subject":  {"item_id": 22486, "qty": 1},
      "materials": [ {"item_id": 11697, "qty": <owner-verified>, "name": "Blood rune"},
                     {"item_id": 22446, "qty": <owner-verified>, "name": "Vial of blood"} ],
      "charge_yield": <owner-verified>, "charge_capacity": 20000,
      "source_url": "https://oldschool.runescape.wiki/w/Scythe_of_vitur", "source_token": "<verbatim wiki phrase>" },
    { "slug": "charge-ring-of-suffering", "name": "Charge Ring of suffering",
      "produces": {"item_id": 20655, "qty": 1},
      "subject":  {"item_id": 19550, "qty": 1},
      "materials": [ {"item_id": 2550, "qty": <owner-verified>, "name": "Ring of recoil"} ],
      "charge_yield": <owner-verified>, "charge_capacity": <owner-verified>,
      "source_url": "https://oldschool.runescape.wiki/w/Ring_of_suffering", "source_token": "<verbatim wiki phrase>" } ] }
```
The `<owner-verified>` quantities/yields are filled from the wiki during implementation and pass the **owner editorial
gate** before merge (never invented). Verified item ids (resolve in `item_dictionary.json`): produces 22325/20655,
subject 22486/19550, materials 11697/22446/2550.

### 4b. `data/verify_charge_recipes.py` — source-grounding gate
Follows the `verify_item_families.py` / `verify_diary_rewards.py` pattern (committed, exits non-zero on violation):
every `produces`/`subject`/`materials[]` `item_id` resolves in `item_dictionary.json`; every record has `source_url`
+ non-empty `source_token`; `slug` unique; every `qty` is a positive int; `charge_yield`/`charge_capacity` are
positive ints; and a sanity check that `produces` and `subject` share an item-family (same page or same
`*-family` — a wrong-pairing guard). **Owner editorial review of the recipe facts is a hard human gate.**

## 5. Builder + the material-import handoff

`kg_ingest/builders/recipes.py` — `build_recipes(records) -> (nodes, edges, groups={})`:
- per record: a `recipe:<slug>` node (data = charge_yield/capacity/notes) + a `consumes` edge per material
  (`role: material`) + a `consumes` edge for the subject (`role: subject`) + one `produces` edge.
- builder-local edge ids in a fresh disjoint band (e.g. `0x60000000`), re-keyed by `assemble.rekey` (owner = the
  recipe node, so no cross-builder collision).

**`assemble.py` wiring** (the material auto-import):
- Run `build_recipes(_load_charge_recipe_records())` and `rekey(r_nodes, r_edges, {})` **before** the reference
  collection / `build_items` call.
- Append `r_edges` to `edges` **before** `referenced_all = _collect_referenced_ids(edges, groups)` — so the
  consumed/produced item ids (materials + endpoints) land in `referenced_item_ids`, and `build_items` auto-imports
  the **material nodes** (11697/22446/2550 — in `item_dictionary`, not yet graph nodes) via the slice-1 mechanism.
  The endpoint nodes (22325/22486/19550/20655) are already imported by the slice-1 families.
- Add `r_nodes` to `owned_ids` (recipe nodes are owned by this builder) and into the final `dedup_nodes(...)`.

## 6. Hardening — global edge-id-uniqueness assert (decision 6)

After all builder edges are combined in `assemble` (i.e. after `edges = edges + i_edges`), assert global edge-id
uniqueness: `eids = [e.id for e in edges]; assert len(eids) == len(set(eids)), <offending ids>`. This is fail-fast
insurance against the cross-call `rekey` collision class (an `item:*` node that is an edge `src` in two separately
re-keyed builders). It is inert this slice (recipe-`src` edges only) but protects the upcoming item-`src` edge slices
(`has_bonuses` item→equipment_bonuses, `drops` monster→item). `validate_kg`'s duplicate-edge-id check (amendment C)
remains the committed backstop; this just surfaces the failure earlier.

## 7. Validation & success criteria (all must hold)

- `validate_kg` **exit 0** — recipe nodes + `consumes`/`produces` edges VIOLATION-clean (`recipe` node kind now live;
  `consumes`/`produces` domain `recipe` / range `item`, both endpoints resolve).
- `validate_cost` **exit 0** — the charge data carries no `price`/`cost`/`currency` tokens; `charge_recipes.json` is a
  new file the cost-free guard doesn't touch (it is NOT `data/recipes.json`, which stays owned by the cost overlay).
- `assemble` **byte-stable** (re-run → identical bytes); the global edge-id assert passes.
- **Golden + slice-1 tests stay green** (recipe nodes/edges are additive; existing item/quest behavior unchanged).
- New **TDD** tests: `build_recipes` (recipe node + material/subject `consumes` + `produces`, qty/role data); the
  material-import handoff (consumed materials become graph nodes via `build_items`); `verify_charge_recipes.py`
  (resolves/source-grounded/positive-qty/same-family). 
- **+1 competency question** (`kg/competency_questions.json`): *"What does it cost to charge a Scythe of vitur?"* →
  the recipe's `role:material` `consumes` edges → `{Blood rune, Vial of blood}` (`expect_min` 2).
- Full `pytest` green (the 4 pre-existing `tests/drop_rates/` collection errors excepted).

## 8. Out of scope — named follow-ups (not this slice)

1. **Facility-recharge** — `NodeKind.FACILITY` + `EdgeType.REQUIRES_FACILITY`; Amulet of glory (Fountain of Heroes,
   no consumed item) + Crystal pickaxe (crystal shards at the Singing Bowl).
2. **`degrades_to` depletion edge** (§9) — the reverse direction.
3. **Cost-per-use** (gp/charge) — the cost/income layer, derived from `charge_yield` + material cost + use rate.
4. **Other charged items** — Trident (chaos/death/fire runes + coins), Toxic blowpipe (scales + darts), dagger-poison
   — each needs its variants imported first (not in slice 1).
5. **Recipe skill/quest gates** — a recipe-level `requires` cond_group where charging is gated (rare).

## 9. Deferred: the degradation taxonomy (record for the future `degrades_to` slice)

The reverse-direction slice is a `degrades_to` **downgrade ladder** through charge-count variants (which already
exist as nodes — e.g. slice-1's Ring of dueling `(8)…(1)`, Dharok's `100…0`). Its key axis is the **terminal**:
- **Rechargeable** (Scythe, Ring of suffering): the ladder ends at the **uncharged variant** — refillable by THIS
  slice's recipe (`charged --degrades_to--> … --> uncharged`, then `recipe` refills).
- **Consumable / destroyed-on-depletion** (Ring of dueling `(8)`, Expeditious bracelet): the ladder ends in
  **destruction** — the last-charge variant `degrades_to` **nothing** (`dst = None` / a `consumed_on_depletion`
  flag). These items have **no charge recipe** (you make/buy a fresh one), so they never appear in this slice.

So the full charge lifecycle = `recipe`/`produces` (create, this slice) + `degrades_to` (deplete, deferred) with a
reverts-vs-destroyed terminal. Slice 1 = the variant nodes; this slice = the create direction.

## 10. Open micro-items (non-blocking, settle in implementation)

- Exact charge quantities / `charge_yield` / `charge_capacity` for the 2 seed recipes — source-grounded from the wiki
  + owner-reviewed (never fabricated).
- Recipe builder edge-id band must be disjoint from existing builder bands (quests/goals/diaries/items 0x10–0x50).
- The `produces`/`subject` same-family sanity check in the verifier is **data-level** — it compares `page_name` in
  `item_dictionary.json` (the verifier reads data, not the built graph). Confirmed: scythe 22325/22486 both
  `page_name "Scythe of vitur"`; suffering 20655/19550 both `page_name "Ring of suffering"`.
