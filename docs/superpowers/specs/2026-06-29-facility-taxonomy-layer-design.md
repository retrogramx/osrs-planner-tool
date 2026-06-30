# Facility Taxonomy Layer — objects/resources slice 1 — Design

> **Status:** approved (brainstorm 2026-06-29; revised post source-verification 2026-06-29).
> The first slice of the bottom-up **objects/resources** layer (layer 3, after shops PR #21 /
> NPC operators PR #23). Builds a clean, source-grounded **`facility:` node roster** from
> `Bucket:recipe`. Pure-roster: **nodes only, zero edges** (deliberate — see §1, §10).
>
> **Source-verified facts (live, 2026-06-29):** bucket name is lowercase `recipe`; **7312** rows;
> fields are `uses_facility` (PAGE, repeated — *clean page names*), `uses_skill` (PAGE, repeated),
> `is_members_only` (BOOLEAN), `uses_material`/`uses_tool` (PAGE), `is_boostable`, `source_template`,
> `production_json`. **366** distinct non-empty `uses_facility` values. The skill field is
> `uses_skill` (NOT `skill`). Aggregation validated: `Anvil→{Smithing,Crafting,Prayer}`,
> `Cooking range→{Cooking,Firemaking}`, `Furnace→{Smithing,Crafting,Magic,Cooking}`,
> `Blast Furnace→{Smithing}`, altars→`Runecraft`/`Prayer`.

## 1. Goal

Turn the `uses_facility` page-references scattered across `Bucket:recipe` into a **normalized,
deduped, owner-vetted taxonomy of processing facilities** — anvil, furnace, cooking range,
spinning wheel, sawmill, the runecrafting/prayer altars, POH lecterns/easels, etc. — each
emitted as a `facility:<slug>` node tagged with the skill(s) it serves and its provenance.

This is the **vocabulary-normalization groundwork** the eventual recipe scale-up needs: it
cannot wire `requires_facility` cleanly until "what counts as a facility, under one canonical
name each" is settled. We settle it here, on the lowest-risk surface (zero edges), which also
proves the additive `NodeKind.FACILITY` enum member + the `reserved → live` schema flip before
the recipe layer leans on them.

**Non-goal (this slice):** `requires_facility` edges, `located_in` placement, `members`,
gather-site yields, `same_entity` bridges to scenery. All deferred — see §10.

## 2. Architecture (fits the existing pipeline)

A clone of the shop/NPC template, with **two raw bricks** (the bucket projection + the
infobox-classification brick that is the roster filter), no edges:

```
data/fetch_recipe_facilities.py   →  data/raw/recipe_facility_bucket.json    (Bucket:recipe projection)
data/fetch_facility_infoboxes.py  →  data/raw/wiki_facility_infoboxes.json   (per-value infobox classification = the filter)
data/map/facility_overrides.json  (owner-authored force_facility / force_exclude — the override rung)
                                          │
kg_ingest/builders/facilities.py  ──build_facilities()──>  facility: nodes
                                          │
kg_ingest/assemble.py  (new block after build_npcs ~line 540; node-only, no rekey;
                         register the new ids in dedup_nodes(...) ~line 584)
                                          │
kg/nodes.json   (+ the facility: nodes; byte-stable)
                                          │
data/verify_facilities.py            (structural, hard-fail)
data/verify_facility_coverage.py     (coverage, report-not-fail — incl. the ambiguous review queue)
```

## 3. Locked decisions (brainstorm outcomes + source-verification revisions)

- **D1 — Scope = facility taxonomy only.** Of the three pieces "objects/resources" splits into
  (processing facilities / farming patches / gather sites), build the well-sourced, schema-ready,
  geometry-free one first. Gather sites are blocked on a yield source-hunt (`Bucket:Mine` is
  empty) + the deferred chunk geometry; farming patches and gather sites are later slices.
- **D2 — Pure-roster, zero edges.** Facilities are *capabilities*, so they do not `located_in`
  (placement = deferred chunk geometry, deferred exactly like currency was for shops), and
  `requires_facility` has nothing to attach from (only 2 recipe nodes exist). The slice emits
  **nodes only**. Its value is the normalized taxonomy.
- **D3 — Roster rule = infobox-presence filter + curated overrides.** *(Revised from the original
  npc/shop-roster cross-reference, which source-verification showed is unreliable: the committed
  `npc:` roster is operator-only and misses NPCs-as-facility like `Thormac`/`Patchy`/`Sbott`/
  `Fossegrimen`/`Taxidermist`, which would have been wrongly admitted as facilities.)* The wiki's
  own `{{Infobox X}}` template on each `uses_facility` page is the structured classifier — the
  same "infobox brick IS the filter" trick the NPC layer used. See §7.
- **D4 — Node content = skill-tagged + provenance.** `data = { skills?, recipe_count, source_url,
  source_token }`. `skills` is **derived, optional, possibly empty** — the sorted distinct
  **non-empty** `uses_skill` values of the recipes pointing at the facility. A facility serving no
  skill-granting recipe (e.g. Armour stand = repair service, Sawmill = plank service) keeps its
  node with **no** `skills` field. Never fabricate a skill.
- **D5 — `members` omitted in v1.** No clean *per-facility* members signal (a furnace serves both
  f2p and p2p recipes; the live probe returned no usable per-facility members split). Deferred to
  when `{{Infobox Scenery}}` lands.
- **D6 — Raw snapshots scoped to what this slice needs** — the `Bucket:recipe` projection
  (`page_name`, `uses_facility`, `uses_skill`) + the per-value infobox classification; not the
  full bucket (`uses_material`/`uses_tool`/`production_json` are the future recipe layer's).
- **D7 — Scale ~336, disclosed, no arbitrary cap.** There are 366 distinct non-empty values;
  the infobox rung admits those classifying as `Scenery`/`Construction` (+ override-promoted),
  defers `NPC`/`Shop`, and routes the `Activity`/`Location`/redirect/none residual to the
  **coverage verifier's review queue**. Final facility count = whatever classifies in; the
  obscure quest/minigame objects are included iff their page is real scenery/construction.

## 4. Sources & the new bricks

### 4a. `Bucket:recipe` (verified live)

`bucket('recipe')` — 7312 rows. Projection this slice selects: `page_name`, `uses_facility`
(repeated PAGE, clean names), `uses_skill` (repeated PAGE). Rows with empty/null `uses_facility`
(~3403) are **dropped** (no-facility recipes, irrelevant here); empty `""` entries inside a
`uses_skill` list are dropped from the skill set. A row may list multiple facilities/skills
(repeated PAGE) — iterate each.

### 4b. NEW brick — `data/fetch_recipe_facilities.py` → `data/raw/recipe_facility_bucket.json`

Mirrors `data/fetch_storeline.py`: `action=bucket`, paginated `offset/limit(5000)`, UA
`GildedTome-research/1.0 (aalvarez0295@gmail.com)`. Writes a sorted, `_provenance`-stamped
snapshot (query string recorded) of the projected rows — the reproducible source for skill
aggregation + `recipe_count` + the distinct-value roster.

### 4c. NEW brick — `data/fetch_facility_infoboxes.py` → `data/raw/wiki_facility_infoboxes.json`

The roster filter (mirrors `data/fetch_npc_infoboxes.py`). For each **distinct** non-empty
`uses_facility` value, fetch its wiki page wikitext **with redirect resolution** (`redirects=1`;
`Cooking range`, `Bank` are redirects), detect the primary `{{Infobox X}}` template, and record
`{value → {infobox, classification, redirect_target?, source_url}}`, sorted + `_provenance`.
`classification` ∈ {`facility` (Scenery|Construction), `npc`, `shop`, `ambiguous`
(Activity|Location|other|none)}. Verified discriminator: `Anvil/Furnace/Spinning wheel/Air
Altar/Bone grinder/Refiner → Infobox Scenery`; `Thormac/Patchy/Sbott/Fossegrimen/Taxidermist/
Aggie/fishing-spots → Infobox NPC`; `Gilded altar → Infobox Construction`; `Sawmill → Infobox
Shop`; `Blast Furnace → Infobox Activity`; `Mycelium pool → Infobox Location`.

### 4d. `data/map/facility_overrides.json` (owner-authored override rung)

`{ "force_facility": [{value, reason, source_url}], "force_exclude": [{value, reason,
source_url}] }`. Highest precedence (§7). Seeded with the obvious `ambiguous`→facility promotions
(e.g. `Blast Furnace`) for owner confirmation; mirrors `data/map/world_parenting.json`.

## 5. Data model (what lands in the graph)

Per surviving, normalized facility value:

```
Node:
  id    = "facility:" + slugify(canonical_name)      # e.g. facility:anvil, facility:blast-furnace
  kind  = facility
  name  = canonical_name                              # the uses_facility PAGE name, e.g. "Anvil"
  data  = {
            "skills":       ["Smithing", ...],        # OPTIONAL: sorted distinct NON-empty uses_skill; omit if empty
            "recipe_count": 246,                       # evidence: # of snapshot rows resolving to this facility
            "source_url":   "https://oldschool.runescape.wiki/w/Anvil",
            "source_token": "Bucket:recipe.uses_facility=Anvil"      # VERBATIM grounding token
          }
```

- **Per-page-name granularity (link-don't-merge):** distinct PAGE names stay distinct — e.g.
  `Chaos altar` (Prayer, Wilderness) and `Chaos Altar` (Runecraft) are two facilities, correctly.
  No case-folding merge.
- **Slug collision guard** (as shops/npcs): slug collisions get `facility:<slug>-2`, etc.;
  deterministic, sorted, first-wins.
- **Edges:** none.

## 6. Schema changes (additive only)

1. **`src/osrs_planner/engine/kg/model.py`** — add one `NodeKind` member after `SHOP`:
   ```python
   FACILITY = "facility"   # processing station (anvil/furnace/altar/range); requires_facility target
   ```
   Hard load-time gate (`json_store` coerces every node via `NodeKind(...)`). **No new `EdgeType`.**
2. **`kg/schema.json`** — `facility` is already *reserved*; flip `status: live` + populate
   `data_keys` additively: `["skills", "recipe_count", "source_url", "source_token"]`. No
   `edge_kinds` change. `validate_kg.check_schema` then passes the live `facility` kind cleanly.

## 7. Roster rule & overrides (D3 detail) — precision-first rungs

Each distinct non-empty `uses_facility` value resolves by the first matching rung:

1. **Override rung (highest)** — `facility_overrides.json`: `force_exclude` → dropped;
   `force_facility` → emitted as a facility (promotes an `ambiguous`/edge case). Each carries
   `{value, reason, source_url}`.
2. **Infobox rung** — from `wiki_facility_infoboxes.json`:
   - `{{Infobox Scenery}}` or `{{Infobox Construction}}` → **facility** (emit node).
   - `{{Infobox NPC}}` → **defer** `service-via-npc` (a character; later a `service` edge).
   - `{{Infobox Shop}}` → **defer** `service-via-shop`.
3. **Ambiguous rung** — `{{Infobox Activity}}`/`{{Infobox Location}}`/other/none/unresolved-redirect
   → **ambiguous**: NOT emitted as a node; surfaced in the coverage verifier's **review queue**
   for owner triage (promote via `force_facility` or leave deferred).

**Normalization:** `uses_facility` values are already clean PAGE names; trim + collapse
whitespace for the display `name`; `slugify` → id. (No `[[...]]` stripping needed.)

## 8. Verification & never-fabricate

- **`data/verify_facilities.py`** (structural, **hard-fail exit 1**) — every facility node's name
  is a real distinct `uses_facility` value in `recipe_facility_bucket.json`; every `skills` entry
  traces to ≥1 real snapshot row (that facility × that skill); every node's value classifies as
  `facility` in `wiki_facility_infoboxes.json` **or** is `force_facility` in the overrides; every
  override carries a `source_url`/`reason`. Reuses the builder's pure helpers (import from
  `kg_ingest.builders.facilities`).
- **`data/verify_facility_coverage.py`** (coverage, **report-not-fail exit 0**) — denominator =
  distinct non-empty `uses_facility` values. Reports `facilities N / total`, `defer-npc`,
  `defer-shop`, **`ambiguous R` (itemized review queue — the owner-triage list)**,
  `override-forced`/`override-excluded`. `--refresh` re-queries `Bucket:recipe` + infoboxes live.
- **Never fabricate:** ambiguous/deferred values are reported, never invented into facilities;
  skill-less facilities get no skill; `members` is omitted, not guessed.

## 9. Testing & competency questions

- **Builder unit tests** (`tests/kg_ingest/test_facilities_builder.py`): infobox classification
  routing (Scenery/Construction→node, NPC/Shop→defer, Activity/none→ambiguous), override
  force_facility/force_exclude precedence, skill aggregation (distinct + sorted + drop-empty),
  skill-less facility keeps node with no `skills`, per-page-name distinctness (`Chaos altar` vs
  `Chaos Altar`), slug collision guard, determinism.
- **Assemble/byte-stability** (`tests/kg_ingest/test_facilities_in_graph.py`): `assemble` emits
  the nodes, re-run byte-identical, `validate_kg` green, the new `NodeKind` loads.
- **Fetch-shape tests** (`tests/data/test_fetch_recipe_facilities.py`,
  `tests/data/test_fetch_facility_infoboxes.py`): snapshot shape + provenance, offline-parseable.
- **Competency questions** (answerable from THIS slice alone — roster + skill tags, no
  `requires_facility` implied): (a) "Which facilities serve the Smithing skill?" → facility nodes
  whose `skills` contains `Smithing` (`facility:anvil`, `facility:furnace`, …); (b) "Is `Thormac`
  a facility?" → no — deferred `service-via-npc` (proves the infobox filter).

## 10. Scope / non-goals (explicit deferrals)

- **`requires_facility` edges** — needs the recipe roster (only 2 recipes today). This slice ships
  the *targets*; the recipe layer wires the edges.
- **`located_in` placement** — facilities are capabilities; physical-scenery placement needs the
  deferred chunk geometry. Deferred.
- **`members`** — no clean per-facility source (D5). Deferred to `{{Infobox Scenery}}`.
- **`same_entity` bridge** facility ↔ scenery/npc — scenery doesn't exist yet. Deferred.
- **Gather sites & farming patches** — separate objects/resources slices.
- **NPC/shop service providers** (`Thormac`, reward shops, `Sawmill`) — deferred-and-disclosed
  here; modeled later via the reserved `service` edge.

## 11. Open micro-items (settle in implementation)

- Multi-value `uses_facility`/`uses_skill` rows (repeated PAGE) — iterate each; confirmed present.
- Redirect resolution in the infobox brick (`redirects=1`); `Cooking range`/`Bank` are redirects —
  classify the *target* page's infobox.
- The starter `facility_overrides.json` content — seed obvious `ambiguous→facility` promotions
  (e.g. `Blast Furnace`, the `Singing Bowl`/`Funeral pyre` variants if Activity-typed) for owner
  confirmation; everything uncertain stays in the review queue.
- `recipe_count` for an override-forced value with 0 backing rows (carry 0 + the override
  `source_url`; the structural verifier treats overrides as grounded).
```

