# Facility Taxonomy Layer — objects/resources slice 1 — Design

> **Status:** approved (brainstorm 2026-06-29). The first slice of the bottom-up
> **objects/resources** layer (layer 3, after shops PR #21 / NPC operators PR #23).
> Builds a clean, source-grounded **`facility:` node roster** from `Bucket:Recipe.uses_facility`.
> Pure-roster: **nodes only, zero edges** (deliberate — see §1, §7).

## 1. Goal

Turn the free-text `uses_facility` wikilinks scattered across `Bucket:Recipe` into a
**normalized, deduped, owner-vetted taxonomy of processing facilities** — anvil, furnace,
cooking range, spinning wheel, sawmill, the runecrafting/prayer altars, etc. — each emitted
as a `facility:<slug>` node tagged with the skill(s) it serves and its provenance.

This is the **vocabulary-normalization groundwork** the eventual recipe scale-up needs: it
cannot wire `requires_facility` cleanly until "what counts as a facility, under one canonical
name each" is settled. We settle it here, on the lowest-risk possible surface (zero edges),
which also proves the additive `NodeKind.FACILITY` enum member + the `reserved → live` schema
flip before the recipe layer leans on them.

**Non-goal (this slice):** `requires_facility` edges, `located_in` placement, `members`,
gather-site yields, `same_entity` bridges to scenery. All deferred — see §10.

## 2. Architecture (fits the existing pipeline)

A clean clone of the shop/NPC template (`fetch_*` → `data/raw/*` snapshot → pure builder →
`assemble` wiring → structural verifier → coverage verifier), minus the parenting/edge stages
(there are no edges):

```
data/fetch_recipe_facilities.py   →  data/raw/recipe_facility_bucket.json   (committed snapshot)
                                          │
kg_ingest/builders/facilities.py  ──build_facilities()──>  facility: nodes
                                          │
kg_ingest/assemble.py  (new block after build_npcs ~line 540; node-only, no rekey;
                         register the new ids in dedup_nodes(...) ~line 584)
                                          │
kg/nodes.json   (+ ~30–50 facility: nodes; byte-stable)
                                          │
data/verify_facilities.py            (structural, hard-fail)
data/verify_facility_coverage.py     (coverage, report-not-fail)
```

## 3. Locked decisions (brainstorm outcomes)

- **D1 — Scope = facility taxonomy only.** Of the three pieces "objects/resources" splits into
  (processing facilities / farming patches / gather sites), build the well-sourced,
  schema-ready, geometry-free one first. Gather sites are blocked on a yield source-hunt
  (`Bucket:Mine` is empty) + the deferred chunk geometry; farming patches and gather sites are
  later slices.
- **D2 — Pure-roster, zero edges.** Facilities are *capabilities*, so they do not `located_in`
  (placement = deferred chunk geometry, deferred exactly like currency was for shops), and
  `requires_facility` has nothing to attach from (only 2 recipe nodes exist, neither uses a
  facility). The slice emits **nodes only**. Its value is the normalized taxonomy.
- **D3 — Roster rule = cross-reference filter + curated overrides (hybrid).** See §7.
- **D4 — Node content = skill-tagged + provenance.** `data = { skills?, recipe_count,
  source_url, source_token }`. `skills` is **derived, optional, possibly empty** — a facility
  that serves no skill-granting recipe (e.g. Armour stand = repair service, Sawmill = plank
  service) keeps its node with **no** `skills` field. Never fabricate a skill.
- **D5 — `members` omitted in v1.** No clean *per-facility* members signal exists in
  `Bucket:Recipe` (a furnace serves both f2p and p2p recipes); inferring it would be a guess.
  Deferred to when `{{Infobox Scenery}}` lands.
- **D6 — Raw snapshot scoped to facility fields.** Commit only the `Bucket:Recipe` projection
  this slice needs (recipe identity, `uses_facility`, `skill`), not the full ~7k-row bucket.
  The future recipe layer can fetch the full bucket separately.

## 4. Sources & the new brick

### 4a. `Bucket:Recipe.uses_facility` (the source)

`Bucket:Recipe` is a live wiki bucket (~7k rows). The relevant fields per row:
- `uses_facility` — a free-text wikilink string (e.g. `[[Anvil]]`), the facility used.
- `skill` — the skill the recipe trains (drives `skills` aggregation; may be empty).
- recipe identity (page/name) — for provenance + the `recipe_count` evidence tally.

Verified live distinct `uses_facility` counts (sample, from the source scan): Anvil 200,
Cooking range 161, Funeral Pyre 81, Furnace 76, Shield easel 48, Pluming stand 48, Brewery 40,
Ectofuntus 37, Gilded altar 35, Chaos altar 35, Armour stand 29, Fire 26, Spinning wheel 11,
Sawmill 10, Blast Furnace 8, Barbarian anvil 12, Singing bowl 15, plus the runecrafting altars.

**Known contamination** (handled by §7): `uses_facility` mixes true facilities with
NPCs-as-facility (`Thormac`, `Patchy`, `Sbott`, `Apothecary`, `Fossegrimen`) and shops
(`Soul Wars Reward Shop`, `Fancy Clothes Store`, `Dom Onion's Reward Shop`).

### 4b. NEW fetch brick — `data/fetch_recipe_facilities.py` → `data/raw/recipe_facility_bucket.json`

Mirrors `data/fetch_storeline.py` / `data/fetch_shop_infoboxes.py`:
- Queries `Bucket:Recipe` via the wiki API, selecting `uses_facility`, `skill`, and recipe
  identity. UA = `GildedTome-research/1.0 (aalvarez0295@gmail.com)`, throttled, batched.
- Writes a **sorted, `_provenance`-stamped** snapshot (`indent=1`, `dict(sorted(...))`):
  `{ "_provenance": {domain, source: "OSRS Wiki ... API", license: "CC BY-NC-SA 3.0", ...},
  "rows": [ {recipe, uses_facility, skill}, ... ] }` — the committed reproducible source.
- Source rows with an empty `uses_facility` are dropped at fetch time (irrelevant to this layer).

## 5. Data model (what lands in the graph)

Per surviving, normalized facility name:

```
Node:
  id    = "facility:" + slugify(canonical_name)      # e.g. facility:anvil, facility:blast-furnace
  kind  = facility
  name  = canonical_name                              # the normalized display name, e.g. "Anvil"
  data  = {
            "skills":       ["Smithing", ...],        # OPTIONAL: sorted distinct non-empty recipe skills; omit if empty
            "recipe_count": 200,                       # evidence: # of snapshot rows resolving to this facility
            "source_url":   "https://oldschool.runescape.wiki/...",   # the Bucket:Recipe / facility page
            "source_token": "Bucket:Recipe.uses_facility=[[Anvil]]"   # VERBATIM grounding token
          }
```

- **Slug collision guard** (as shops/npcs): if two canonical names slug-collide, the second
  gets `facility:<slug>-2`, etc. Deterministic, sorted, first-wins.
- **Edges:** none.

## 6. Schema changes (additive only)

Two small additive touches — no re-ingest:

1. **`src/osrs_planner/engine/kg/model.py`** — add one `NodeKind` member after `SHOP`:
   ```python
   FACILITY = "facility"   # processing station (anvil/furnace/altar/range); requires_facility target
   ```
   This is the hard load-time gate (`json_store` coerces every node via `NodeKind(...)`).
   **No new `EdgeType`** — zero edges this slice.
2. **`kg/schema.json`** — the `facility` node_kind is already *reserved*; flip it `status: live`
   and populate `data_keys` additively:
   ```json
   "facility": { "status": "live", "key_prefix": "facility:<slug>", "id_basis": "slug",
     "data_keys": ["skills", "recipe_count", "source_url", "source_token"],
     "notes": "anvil/furnace/altar/range processing station; requires_facility target." }
   ```
   `validate_kg.check_schema` enforces the closed vocab + (for edges) domain/range; a live
   `facility` kind with these `data_keys` passes cleanly. No edge_kinds change.

## 7. Roster rule & overrides (D3 detail)

A normalized `uses_facility` value's fate is decided precision-first:

1. **Override rung (highest precedence)** — `data/facility_overrides.json` (owner-authored,
   source-noted), two lists:
   - `force_facility`: values to emit as facilities even if they collide with an NPC/shop name
     (a real facility whose name happens to match one).
   - `force_exclude`: values to suppress (a false positive the auto rung admitted).
   Each entry carries `{value, reason, source_url}` for the editorial trail (mirrors
   `data/map/world_parenting.json`).
2. **Auto rung (cross-reference filter)** — a value becomes a `facility:` node iff its
   normalized form matches **neither** an existing `npc:` name **nor** a `shop:` name
   (town/case-normalized, reusing the committed npc + shop rosters). A match → **deferred**,
   bucketed `service-via-npc` or `service-via-shop` (those are service providers, modeled later
   as the reserved `service` edge — not facilities).
3. **Ambiguous residual** — anything the rungs can't cleanly resolve is **disclosed** in the
   coverage verifier's review queue, never silently dropped or fabricated.

**Normalization:** strip the `[[...]]` wikilink to its target, trim, collapse whitespace,
canonicalize case for matching (reuse `world.parse_infobox_links` / `world._norm`). The
canonical display `name` is the cleaned target text; `slugify` produces the id.

## 8. Verification & never-fabricate

- **`data/verify_facilities.py`** (structural, **hard-fail exit 1**) — every facility node's
  name traces to a real distinct `uses_facility` value in `recipe_facility_bucket.json`; every
  `skills` entry traces to ≥1 real snapshot row (that facility × that skill); every override is
  honored and carries a `source_url`/`reason`. Reuses the builder's pure helpers (import from
  `kg_ingest.builders.facilities`), not a re-derivation.
- **`data/verify_facility_coverage.py`** (coverage, **report-not-fail exit 0**) — denominator =
  distinct normalized `uses_facility` values in the snapshot. Reports: `facilities N / total`,
  `service-via-npc M`, `service-via-shop K`, `override-forced J`, `override-excluded`,
  `ambiguous R` (review queue). `--refresh` re-queries `Bucket:Recipe` live for drift.
- **Never fabricate:** unresolved/ambiguous values are reported, never invented into facilities;
  skill-less facilities get no skill; `members` is omitted, not guessed.

## 9. Testing & competency questions

- **Builder unit tests** (`tests/kg_ingest/test_facilities_builder.py`): normalization
  (`[[Anvil]]` → `facility:anvil`), the cross-reference filter (a `uses_facility` matching an
  npc name is deferred; matching nothing is admitted), override force-include/exclude, skill
  aggregation (distinct + sorted), skill-less facility keeps node with no `skills`, slug
  collision guard, determinism (same input → identical nodes).
- **Assemble/byte-stability** (`tests/kg_ingest/test_facilities_in_graph.py`): `assemble`
  emits the facility nodes, re-run is byte-identical, `validate_kg` green, the new `NodeKind`
  loads.
- **Fetch-shape test** (`tests/data/test_fetch_recipe_facilities.py`, mirrors
  `test_fetch_shop_infoboxes.py`): snapshot shape + provenance, offline-parseable.
- **Competency questions** (`kg/competency_questions.json` + runner), answerable from THIS
  slice's data alone (roster + skill tags — no `requires_facility` implied): (a) "Which
  facilities serve the Smithing skill?" → facility nodes whose `skills` contains `Smithing`
  (`facility:anvil`, `facility:furnace`, …); (b) "Is `Thormac` a facility?" → no — deferred as
  `service-via-npc` (proves the cross-reference filter). These keep the taxonomy honest and
  queryable without overclaiming an edge the slice doesn't build.

## 10. Scope / non-goals (explicit deferrals)

- **`requires_facility` edges** — needs the recipe roster (only 2 recipes today). Deferred to
  the recipe layer; this slice ships the *targets*.
- **`located_in` placement** — facilities are capabilities; physical-scenery placement needs
  the deferred chunk geometry. Deferred.
- **`members`** — no clean per-facility source (D5). Deferred to `{{Infobox Scenery}}`.
- **`same_entity` bridge** facility ↔ scenery/npc — scenery doesn't exist yet. Deferred.
- **Gather sites & farming patches** — separate objects/resources slices.
- **NPC/shop service providers** (`Thormac`, reward shops) — deferred-and-disclosed here;
  modeled later via the reserved `service` edge.

## 11. Open micro-items (settle in implementation)

- Exact `Bucket:Recipe` field names for `uses_facility` / `skill` (confirm against the live
  schema during the fetch brick; adjust the snapshot projection accordingly).
- Snapshot filename: `recipe_facility_bucket.json` (bucket-sourced convention) vs the
  `wiki_*` infobox convention — going with `*_bucket.json` since the source is a Bucket.
- Whether a single recipe row can carry multiple `uses_facility` wikilinks (split on `]] [[`
  if so); confirm and handle in normalization.
- `recipe_count` semantics when an override force-includes a value with 0 backing rows (carry
  0 + the override's `source_url`; verifier treats overrides as grounded).
```

