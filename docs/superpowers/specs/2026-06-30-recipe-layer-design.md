# Recipe Layer — slice 1 (core production skills) — Design

> **Status:** approved (brainstorm 2026-06-30, design validated by live source-verification).
> Scales the reified `recipe:` layer from `Bucket:recipe` for the six core production skills,
> wiring recipes to materials, output, tools, the 255 `facility:` nodes (PR #24), and skill gates.
> This is the layer that makes the facilities pay off and answers "how do I make / train X."
>
> **Source-verified live (2026-06-30):** `Bucket:recipe` = 7,312 rows / 4,812 pages; the rich payload
> is `production_json` (JSON-as-text, parses 100%). Core-skill subset = **2,489 rows** (Crafting 760,
> Cooking 536, Smithing 446, Herblore 403, Fletching 220, Runecraft 190; 383 multi-skill, 109
> output-less). Distinct items to resolve ≈ 2,605. **Item resolution 95.4%** (outputs 96.8%, higher
> with `html.unescape`); **facility resolution 98.1%**. The reified recipe-node model is the
> universally-converged KG pattern (schema.org/HowTo, W3C n-ary, PROV-O, FoodOn, Factorio/GregTech).

## 1. Goal

Turn `Bucket:recipe` into ~2,380 source-grounded reified `recipe:` nodes for the six core
production skills, each connected to its inputs (materials + tools), its output, its facility,
and its skill-level gate — so the planner can answer "what do I need to make/train X" and
"what are all the ways to make X", and the 255 facilities stop being floating targets.

**Scope = the six core production skills** (Smithing, Cooking, Crafting, Fletching, Runecraft,
Herblore). Other skills, output-less XP activities, probabilistic byproducts, and currency are
deferred (§10).

## 2. Architecture (fits the existing pipeline)

Clones the established brick shape; EXTENDS the existing 2-node charge-recipe layer additively
(link-don't-merge — recipes never re-ingest items; consumed/produced items auto-import):

```
data/fetch_recipes.py  →  data/raw/recipe_bucket.json   (Bucket:recipe projection incl. production_json)
                                  │
kg_ingest/builders/recipes.py  ──build_recipe_roster()──>  recipe: nodes + consumes/produces/requires_facility/requires edges
   (reuses: item-name resolver [map_varrock.make_item_resolver]; facility name->node resolver [from the committed facility nodes];
    the quests requires+SKILL_LEVEL-atom template; coexists with build_recipes charge recipes)
                                  │
kg_ingest/assemble.py  (recipes built FIRST so item dsts auto-import via build_items; recipe-src seeded rekey; fresh edge-id band)
                                  │
kg/{nodes,edges,condition_groups}.json   (byte-stable)
                                  │
data/verify_recipes.py            (structural, hard-fail)
data/verify_recipe_coverage.py    (coverage, report-not-fail: per-skill have/total + unresolved residuals)
```

## 3. Locked decisions (brainstorm outcomes + verified facts)

- **D1 — Scope = the six core production skills.** 2,489 rows → ~2,380 recipe nodes (defer 109
  output-less rows). Other skills are later slices.
- **D2 — Reified recipe node, one per METHOD-ROW.** Bronze bar's Furnace / Blast Furnace /
  Superheat are 3 distinct nodes (each its own materials/facility/ticks). This dissolves both
  "alternative recipes" (N nodes `produces` the same item) and "facility multiplicity" (each
  method-row has exactly ONE facility — no OR-of-facilities, which the schema forbids on
  `requires_facility`).
- **D3 — Edges:** `consumes` (recipe→item, `{qty, role}` with role ∈ {material, **tool**});
  `produces` (recipe→item, `{qty}`); `requires_facility` (recipe→facility); `requires`
  (recipe→cond_group of `skill_level` atoms).
- **D4 — Tools INCLUDED** as `consumes role:'tool'` (required-not-depleted), from the clean
  indexed `uses_tool` column. Additive `consumes_role` vocab change.
- **D5 — xp is a per-skill dict** in `recipe.data.xp` (handles multi-skill; never loses data).
- **D6 — Slug = stable on names+method, never on mutable numbers.** `slugify(html.unescape(output.name))`;
  multi-method pages append `-slugify(subtxt)`; deterministic `-2` collision guard; skip any slug
  that collides with an existing charge-recipe slug (additive coexistence).
- **D7 — Resolve, never fabricate.** Item names via the resolver (with `html.unescape`); facility
  names via the committed facility roster. Unresolvable → skip the edge (or the whole recipe, if
  its OUTPUT is unresolvable) and DISCLOSE. (Verified bases: items 95.4%/outputs 96.8%, facilities 98.1%.)
- **D8 — Coverage verifier is report-not-fail** (per-skill have/total + unresolved residuals);
  the structural verifier hard-fails on ungrounded edges. (The charge-recipe verifier's hard-fail
  discipline is fine for 2 curated rows but wrong for a ~2.4k auto-derived roster.)

## 4. Sources & the new brick

### 4a. `Bucket:recipe` (verified live)

Per row the layer reads: `page_name`, `uses_skill` (indexed, for the core-skill FILTER),
`uses_tool` (indexed, clean PAGE names → tools), `uses_facility` (indexed, clean → facility),
and **`production_json`** (the rich payload): `materials[]{name, quantity}`,
`skills[]{name, level, experience}`, `output{name, quantity, subtxt?}`, `members`, `ticks`.

Field realities (handled in §5–6): `quantity` is a string (usually int, sometimes a decimal
expected-value like Roe 0.66 — true distribution is prose, deferred); `experience`/`level` are
numeric for ~98% but 127/64 are formulas/ranges ("1.5×Smithing level") → omit that atom/xp +
disclose; item NAMES carry no id and may be HTML-entity-encoded; `output` is a single dict or
absent (output-less rows deferred).

### 4b. NEW brick — `data/fetch_recipes.py` → `data/raw/recipe_bucket.json`

Mirrors `data/fetch_recipe_facilities.py`: `action=bucket` paginated by 5000, UA
`GildedTome-research/1.0 (aalvarez0295@gmail.com)`. Projects the fields above for ALL rows
(filter to core skills in the builder, so the snapshot stays reusable for later slices), drops
nothing at fetch except truly-empty rows. Sorted + `_provenance`-stamped (CC BY-NC-SA 3.0).

## 5. Data model (what lands in the graph)

Per core-skill method-row with a resolvable output:

```
Node:
  id    = "recipe:" + slug      # slugify(html.unescape(output.name)) [+ "-" + slugify(subtxt) if the page has >1 method-row]
  kind  = recipe
  name  = html.unescape(output.name)     # the OUTPUT item (e.g. "Bronze bar"); method/subtxt lives in the slug + source_token, NOT the name
  data  = {
            "xp":          {"Smithing": 62.5, ...},   # per-skill numeric experience (omit non-numeric + disclose)
            "ticks":       5,                          # if present & numeric
            "members":     true,
            "source_url":  "https://oldschool.runescape.wiki/w/Bronze_platebody",
            "source_token":"Bucket:recipe page=Bronze platebody output=Bronze platebody"   # + method=<subtxt> when multi-method
          }
Edges:
  consumes recipe->item {qty:<number>, role:"material"}   # per production_json material (qty parsed)
  consumes recipe->item {qty:1,        role:"tool"}       # per indexed uses_tool entry (required-not-depleted)
  produces recipe->item {qty:<number>}                    # the single output (qty parsed; may be a decimal expected-value)
  requires_facility recipe->facility                       # the row's uses_facility -> resolved facility node (>=0; usually 1)
  requires recipe->[cond_group AND of skill_level atoms]   # one atom per skill with a numeric level; data={boostable}
```

- **Slug collision guard** (`-2`) + skip-on-charge-recipe-collision. Per-page-name distinctness
  preserved.
- **Quantities** stored as parsed numbers (int, or float for decimal expected-values). Ranges /
  probabilities / byproducts remain advisory prose — DEFERRED (§10).

## 6. Resolution (the verified-hard part — never fabricate)

- **Item names → ids:** `make_item_resolver(item_dictionary.json)` after `html.unescape(name)`.
  `output.name` is the precise variant (`Antipoison(4)`). Unresolvable **material/tool** name →
  skip that edge + disclose; unresolvable **output** → skip the whole recipe + disclose (no
  usable product). Measured base: 95.4% items / 96.8% outputs resolve (higher with unescape).
- **Facility names → `facility:` nodes:** build a lookup from the committed facility nodes'
  `name` + `data.aliases` (so `Cooking range`→`facility:range`). Resolve each row's indexed
  `uses_facility` value. Unresolvable (npc/shop-deferred, force-excluded, or niche) → no
  `requires_facility` edge + disclose. Measured base: 98.1%. A row with >1 facility → one
  `requires_facility` edge each (implicit AND); flag if that's actually an OR (rare).
- **Skill names → `skill:` nodes:** leaf domain (auto via `build_supporting`); the `skill_level`
  atom's `ref_node` = `skill:<name>`, threshold = numeric level, `data={boostable}`.

## 7. Schema / model changes (additive only)

- **`src/osrs_planner/engine/kg/model.py`** — add `REQUIRES_FACILITY = "requires_facility"` to the
  `EdgeType` enum (verified ABSENT today; the lone grep hit is the FACILITY-NodeKind comment).
- **`kg/schema.json`** — `requires_facility` `status: reserved → live`; `consumes_role` vocab
  `["material", "subject"]` **+ `"tool"`**; add `"members"` to `recipe.node_kind.data_keys`
  (already has `xp`/`ticks`). `consumes`/`produces`/`requires` are already live. No re-ingest.

## 8. Verification

- **`data/verify_recipes.py`** (structural, **hard-fail exit 1**): every `consumes`/`produces` dst
  is a committed `item:` node; every `requires_facility` dst is a committed `facility:` node; every
  `requires` cond_group's `skill_level` ref is a `skill:` node; every recipe has a `source_token`;
  slugs unique; roles ∈ {material, tool}; the recipe's output item traces to a real Bucket row.
  Reuses the builder's pure helpers.
- **`data/verify_recipe_coverage.py`** (coverage, **report-not-fail exit 0**): per core skill,
  `recipes built N / Bucket rows total`; itemized residuals — unresolved output names (recipe
  skipped), unresolved material/tool names (edge skipped), unresolved facilities (no
  requires_facility), non-numeric xp/level omissions. `--refresh` re-queries live.

## 9. Testing & competency questions

- **Builder unit tests** (fixtures): method-row → node; multi-method slug discrimination; xp
  per-skill dict; multi-skill → multiple `skill_level` atoms; tool → `consumes role:'tool'`;
  `html.unescape` resolution; unresolvable output → recipe skipped; facility name/alias
  resolution; charge-recipe slug-collision skip; determinism.
- **Assemble/byte-stability**: recipes emitted, re-run byte-identical, `validate_kg` green, item
  auto-import works, no duplicate edge ids.
- **Fetch-shape test** (offline): snapshot shape + provenance.
- **Competency questions** (answerable from this slice): "What's needed to smith a Bronze
  platebody?" (5 Bronze bar + Smithing 18 + Anvil + Hammer); "What are all the ways to make a
  Bronze bar?" (the method-row alternatives); "What can I make at a Spinning wheel?" (incoming
  `requires_facility`).

## 10. Scope / non-goals (explicit deferrals)

Non-core skills (Construction, Magic, Firemaking, Prayer, Farming, Agility, Thieving, …) · the
~1,949 output-less XP activities · probabilistic byproducts / secondary outputs / quantity
ranges (prose only — later: reuse the `drop_table` node + `contains` rates) · non-numeric
xp/level formulas (omitted + disclosed) · currency-as-material (`Coins`, 257 recipes → the cost
layer) · GE `output.cost` (drift-prone) · `is_boostable` normalization beyond the per-atom flag.

## 11. Open micro-items (settle in implementation)

- Exact `source_token` format for method-rows (page + output + method); confirm uniqueness.
- Tool `qty` convention (use `qty:1` + `role:'tool'`, or omit qty for tools — decide and keep
  consistent so cost rollups treat tools as not-consumed).
- Edge-id band for the recipe-src family (the existing charge recipes use 0x80; the scaled roster
  shares the recipe-src rekey — confirm the seed spans both builders).
- Multi-facility rows (AND vs OR): default to one `requires_facility` edge each (AND); detect &
  disclose any that are semantically OR.
