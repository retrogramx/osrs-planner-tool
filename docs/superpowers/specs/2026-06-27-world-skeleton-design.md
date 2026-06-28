# World Skeleton — Design

> **Status:** DESIGN (finalized 2026-06-28; supersedes the in-progress draft). Branch: `feat/world-skeleton` (off
> `main`, slices 1-7 merged). The design was reached by extensive brainstorm exploration — 3 wiki-grounded LLM
> survey/audit workflows + a deterministic MediaWiki category-API reconcile — which produced a **754-place prototype
> that validated the method and the shape**. The implementation rebuilds the dataset cleanly from the structured source
> below (the prototype is not committed; it proved the approach).

## 0. Why this slice
The graph's geography stops at `gielinor → misthalin → varrock` (slice 6). This builds the **comprehensive location
graph of Gielinor** — every continent, ocean, sea, island, kingdom, region, city, town, settlement, **plus** the major
content sites (dungeons, raids, slayer dungeons, guilds, minigames, agility courses, hunter areas, castles, named
mines) — so the planner can answer "where is X / what's in region Y," and every future layer (shops, monsters/`drops`,
transport, activities) has a **place to attach to**.

## 1. Locked decisions (owner-approved during brainstorm, 2026-06-27/28)
| # | Decision | Choice |
|---|---|---|
| 1 | Scope | **Comprehensive location graph** (the place hierarchy + content sites). All-shops Storeline scale-up **DEFERRED** (needs shop→location data). Chunk/coordinate geometry **DEFERRED** (reserved schema keys; pairs with the leaf layers). |
| 2 | Data source | **The wiki's TYPE-CATEGORY UNION**, enumerated via the MediaWiki category API — exhaustive + clean. **NOT** prose-enumeration (incomplete) and **NOT** `Category:Locations` (1,708 pages — too broad: ~1,058 are scenery/NPCs/items/buildings; also *incomplete* — only 15 of 52 minigames are location-tagged). The owner's `OSRS Ontology.md` supplies the top-level **SHAPE** (continent/ocean/kingdom hierarchy + rulers) only — never trusted as data. |
| 3 | Granularity | An **explicit IN/OUT category filter** (§3) — the one editorial definition of "what is a place." |
| 4 | Completeness | A committed **coverage verifier** (§4): the build-time gate is **offline** — it asserts the graph faithfully covers every IN-category member in the *committed* snapshot (no silent drops from parenting/dedup), and reports `have N/total` per category. A `--refresh` mode re-queries the **live** API to catch game-update drift (snapshot vs wiki). This is the "complete once and for all" — completeness becomes a *tested invariant*. |
| 5 | Vocabulary | **Two-level typing**: `place_type` (coarse, queryable) + `content_kind` (fine, display). New `place_type`s (additive flips): **`sea`** + **`point_of_interest`**. |
| 6 | Governance | `ruled_by` / `faction` as **best-effort data, report-not-fail** (lots unknown). `faction` nodes + governance *edges* deferred. |
| 7 | Discipline | **Never fabricate** — every place grounded to a wiki page (`source_url`); an unresolved ruler or an unparented place is **FLAGGED, not guessed**. |

## 2. The data model

### 2.1 `place_type` vocabulary
Existing enum: `world/continent/ocean/island/kingdom/city/town/settlement/district/dungeon/floor/region`. **Add (additive
reserved→live):** `sea`, `point_of_interest`. `content_kind` (free string, display-only metadata) carries the fine type:
`guild · altar · minigame · agility course · castle · hunter area · mine · slayer dungeon · raid · boss lair · landmark
· cave · dungeon · sea · island · town …`. Rule of thumb: the graph **queries** on `place_type`; the UI **shows**
`content_kind`. (Lesson from the brainstorm: a party room / altar is a `point_of_interest`, *not* a `settlement`; and
`content_kind` is a *soft* best-effort hint — e.g. "slayer dungeon" vs "dungeon" — not an adversarially-verified fact.)

### 2.2 The hierarchy (and integration with slices 6)
```
place:gielinor (world)
├ Mainland / Zeah (continent)   ├ 9 Oceans (ocean) ─▶ seas ─▶ islands
│   └ kingdoms / regions ─▶ cities/towns/settlements ─▶ districts + dungeons + points_of_interest
```
- **Backbone ownership:** `world.json` owns Gielinor → city/region level. The existing `place:gielinor`/`misthalin`/
  `varrock` **move out of `varrock.json`** into the backbone; `place:misthalin` **re-parents** `gielinor → mainland`;
  `varrock.json` keeps only **within-city** detail (districts, pubs, NPCs, shops). Sets the per-town pattern.
- **Same_entity bridges:** opportunistic `place:<slug> → region:<slug>` to the 61 legacy `region:` nodes where a slug
  matches (slice-6 pattern), link-don't-merge.

### 2.3 Governance
`ruled_by` (an `npc:` ref or verbatim string) + `faction` (governing race/allegiance) on backbone places, best-effort,
`""` where the wiki names none (never guessed). Report-not-fail on gaps.

## 3. Data source — the structured ingest (the reproducible brick)

### 3.1 The IN/OUT granularity filter (the editorial definition of "a place")
**IN** (each an exhaustive, API-enumerable category — the union is the complete target):
- **Geographic backbone** (from the owner-shape + the wiki): continents, oceans, **seas**, islands, kingdoms, regions.
- **Content categories:** `Dungeons`, `Slayer dungeons`, `Caves`, `Raids`, `Minigames`, `Guilds`, `Agility courses`,
  `Hunter areas`, `Castles`, `Settlements`, and **named-major `Mines`** (owner-curated subset — the category has ~112,
  most granular).

**OUT:**
- The `Category:Locations` noise: **scenery, NPCs, items, monsters, buildings, granular sub-areas** (~1,058 pages).
- **All individual `Banks`** (a bank is a *facility/service* → a future service layer, not a place node).
- **Granular ore-rock mines**, holiday/event pages, category-index pages.

*(Verified during brainstorm: many guessed category names don't exist — it's `Settlements` not `Cities`/`Towns`; no
`Ports`/`Altars`/`Temples` categories. The ingest must use the confirmed names and treat absences as "covered by the
backbone or another category.")*

### 3.2 Enumeration (exhaustive + reproducible)
The MediaWiki category API (`action=query&list=categorymembers`, paginated) → exhaustive membership of each IN
category → union. **Committed raw snapshot** `data/raw/wiki_location_categories.json` + a **deterministic parser** (the
foundation-reproducibility discipline). The owner-shape (the ~50 backbone places + governance) is a small **owner-
authored** `data/map/world.json` (drafted wiki-grounded, owner-reviewed — like `varrock.json`).

### 3.3 Parenting (`located_in`) — grounded, with flagged residuals
For each ingested location, in order: **(1)** the *deepest* backbone/draft place whose name is among the page's
region/area categories; **(2)** fallback — the page name minus a type suffix (`X Dungeon` → `X`) matched to a place;
**(3)** the infobox `location` field; **(4)** else **FLAG as unparented** for the owner to re-home (report-not-fail —
never silently parent to the wrong place or to the root).

### 3.4 Typing
`place_type` + `content_kind` derived from the matched IN category (priority-ordered: raid → slayer dungeon → dungeon →
cave → minigame → guild → agility → hunter → castle → mine → island → settlement). Dungeon-family → `place_type=dungeon`;
guild/minigame/agility/castle/hunter/mine → `place_type=point_of_interest`; settlement/island/region as themselves.

## 4. Components
- **`data/fetch_world_locations.py`** — paginated category-API pull of the IN categories → committed snapshot
  (`data/raw/wiki_location_categories.json` + each page's region categories, for parentage). Mirrors
  `fetch_items_equipment.py`; `--refresh` re-pulls for drift.
- **`data/map/world.json`** — owner-authored backbone (continents/oceans/kingdoms/regions + governance + the
  `same_entity` bridges), drafted wiki-grounded, owner-reviewed.
- **`kg_ingest/builders/world.py`** — `build_world(world_backbone, location_snapshot, region_ids) → (nodes, edges,
  groups={})`: emits place nodes (backbone + filtered ingest) + `located_in` + `same_entity`. Place-`src` → its **own
  rekey** (band disjoint from map `0xE0` / storeline `0xF0`).
- **`data/verify_world.py`** — STRUCTURAL hard-fails: every `located_in` resolves; exactly one root (`gielinor`); no
  orphan; slug uniqueness; `place_type ∈ schema enum`. **REPORT (not fail):** unparented places, missing governance.
- **`data/verify_world_coverage.py`** — **THE COMPLETENESS GATE (offline).** Asserts the committed graph contains a node
  for every IN-category member in the committed snapshot (catches silent drops from parenting/dedup) and reports
  `have N/total` per category (e.g. `dungeons 177/177`), listing any residual. Exit 0 (report-not-fail); the residual is
  the to-do. **`--refresh`** re-queries the live API → flags snapshot-vs-wiki drift (new game content).
- **`kg_ingest/assemble.py`** — wire `build_world` BEFORE the reference collection; place-`src` own rekey; the
  `varrock.json` refactor (drop the 3 backbone places; re-parent). Byte-stable.
- **+ competency questions** — e.g. *"What's in Kandarin?"* / *"Where is the Catacombs of Kourend?"* / *"What kingdom &
  continent is Varrock in?"*

## 5. Owner-review gates (editorial — facts/judgment a validator can't make)
1. **The IN/OUT filter** — approved (§3.1).
2. **Major-mines curation** — owner picks the major named mines from the candidate list (the category is mostly granular).
3. **Unparented re-homing + residual noise** — owner pass on the flagged residuals (the verifier surfaces them).
4. **The top-level shape + governance** — owner editorial on the backbone (`world.json`).
The **visual collapsible tree** (the `world_skeleton.html` review tool built during brainstorm) is the sign-off medium.

## 6. Validation & success criteria
- `assemble` **byte-stable**; `validate_kg` / `validate_cost` / `verify_world` / `verify_world_coverage` exit 0.
- The coverage verifier **proves** comprehensive coverage (`have N/total` per IN category, residual listed).
- Golden + slice-1..7 tests green. New **TDD**: `build_world` (backbone + ingest parenting; the re-parent; same_entity;
  single-root); `verify_world` (a dangling `located_in` fails; an unparented place reports-not-fails); the coverage gate.
- Graph grows to the comprehensive location set (hundreds of place nodes); deltas recorded at build time.

## 7. Out of scope — named follow-ups
All-shops Storeline scale-up (needs shop→location) · chunk/coordinate geometry · governance EDGES + `faction`/`deity`
nodes · monsters/`drops` · transport/`gives_access` · a **service layer** (banks/shops/altars as facilities attached to
places) · per-town internal detail beyond Varrock.

## 8. Open micro-items (settle in implementation)
- Confirm each IN-category's exact wiki name + membership (some guessed names are empty — use `Settlements`, etc.).
- Improve parenting for the unparented residual via the infobox `location` field; a `mountain` `place_type` (or map to
  `region`) for Mount Quidamortem/Karuulm.
- Finalize the `content_kind` taxonomy; treat it as advisory (the "slayer dungeon" over-tag lesson) — source precise
  designations from categories where it's load-bearing later.
- The implementation **rebuilds** the dataset from the committed snapshot (reproducible) — it does NOT import the
  brainstorm prototype.
