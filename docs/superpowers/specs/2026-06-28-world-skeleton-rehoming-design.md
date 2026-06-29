# World Skeleton — Re-homing the Unparented — Design

> **Status:** DESIGN (finalized 2026-06-28). Branch: `feat/world-rehoming` (off `main`, world skeleton PR #19 merged).
> Closes the world-skeleton's flagged residual: **190 unparented content places** (`located_in == place:gielinor`,
> not legitimate root children). The owner-approved ambition is the **full campaign** — drive the residual toward zero
> through *reproducible signals*, owner-reviewed only where judgment is genuinely required. Supersedes micro-item §8 of
> `2026-06-27-world-skeleton-design.md` ("improve parenting via the infobox `location` field") and discharges owner-review
> gate #3 ("unparented re-homing + residual noise").

## 0. Why this slice
Every bottom-up layer's `located_in` is a completeness **cross-check** against the skeleton (world-skeleton spec §7b). A
skeleton with 190 places dangling off the root weakens that cross-check and carries non-place noise (index/list pages,
discontinued holiday content) that the leaf layers would have to ignore. Re-homing strengthens the foundation **before**
we attach shops / NPCs / objects / transport / facilities on top of it.

## 1. Evidence (measured against the committed graph, 2026-06-28)
The 190 break down — measured, not guessed (the owner's evidence-first discipline):

| Bucket | Count | Mechanism |
|---|---|---|
| **Noise → filter OUT** | **15** (14 of the 190) | `^List of …` titles + titles equal to an IN-category name (`Guilds`/`Minigames`/`Raids` index pages) + `Discontinued content` ∪ `Locations that do not appear in-game` (e.g. `Duel Arena`, removed from the game) |
| **Re-homed by content/name parenting** | **52** | logic-only, no new data — let *ingested* places be parents, not just backbone |
| **Residual → infobox `location` + owner override** | **124** | quest-only category hints / settlements the wiki never region-tags |
| **Cycles produced in practice** | **0** | …but the reachability guard is still required as a forward invariant |

(14 + 52 + 124 = 190; the 15th noise page was already parented, not in the residual. The re-homed count is 52 rather than
~64 *because* removing the bogus `Minigames`/`Guilds`/`Raids` index-parents correctly forces ~12 places to FLAG instead
of attaching to a fake parent — better flagged than fake-parented.)

Root cause of the residual, confirmed: today `parent_for` (rung 1, category-match) resolves a category **only against
backbone places**, so a dungeon whose region was itself *ingested* (e.g. an island in the `Islands` category, not the
owner backbone) can never attach. And the wiki frequently does **not** category-tag a settlement with its region (e.g.
`Draynor Village`'s categories are `[Content released in 2001, Draynor Village, Settlements]` — no `Misthalin`), so
category heuristics structurally cannot fix the settlement tier — that is the infobox `location` field's job.

## 2. Locked decisions (owner-approved during brainstorm, 2026-06-28)
| # | Decision | Choice |
|---|---|---|
| 1 | Ambition | **Full campaign** — all signals below, in one slice; residual driven toward ~0; one new data source (infobox). |
| 2 | Noise rule | **Exclude** (a) `^List of …` titles, (b) titles **equal to an IN-category name** (`Guilds`/`Minigames`/`Raids` — the self-referential category-index pages), (c) members of `Discontinued content` ∪ `Locations that do not appear in-game` — **15 pages**. None are real reachable places. **One shared predicate** used by the builder *and* both verifiers (so coverage stays honest). Exact list is owner-reviewed (gate #3). |
| 3 | Signal priority | **Precision-first:** owner-override → category-match (backbone+content) → name-suffix → infobox `location` → FLAG. A place name in the page's categories is more specific than the infobox's often region-level link; infobox fills the gap categories cannot. |
| 4 | Acyclicity | A **reachability resolve** in the build (demote any node not reaching `place:gielinor` back to FLAG) **plus** a new structural hard-fail in `verify_world.py`. Re-homing turns the graph from a guaranteed-DAG (backbone-only parents) into one that needs an explicit acyclicity gate. |
| 5 | New data | A new reproducible brick: a committed **infobox-`location` snapshot** + its own fetcher + a deterministic parser (the foundation-reproducibility discipline). |
| 6 | Editorial tail | An owner-authored `data/map/world_parenting.json` override (source-grounded) for what the automated signals can't resolve + targeted `world.json` backbone additions for genuinely-absent real places. Both owner-reviewed. |
| 7 | Discipline | **Never fabricate.** Every re-homing traces to a wiki signal (a category, the infobox value, or an owner override citing `source_url` + verbatim `source_token`). An unresolved place stays **FLAGGED, not guessed** (report-not-fail). |

## 3. The signal stack — `parent_for` (5 rungs, first hit wins)
`parent_for(title, page_categories, name_index, infobox, overrides) → (parent_id, signal)` where `signal ∈
{override, category, name-suffix, infobox, FLAG}`:

1. **Owner override** — `overrides[slug]["parent"]` if present. Editorial escape hatch.
2. **Category-match (backbone + content)** — a place-*node* whose name is among `page_categories`. **Change:**
   `name_index` is rebuilt to include the **ingested content places**, not only the backbone (this is the +52). A node
   never parents to itself; a noise-excluded node is never a parent. **`name_index` resolution (collision/tie-break):**
   each normalized place name maps to **one** node id — **backbone beats content** on a name collision; within the
   backbone the existing *deepest-backbone-wins* ordering is preserved; remaining ties broken by id sort (deterministic).
   (Content-place depth is *not* statically known at index-build time — it depends on the parenting being computed — so
   the index uses this static precedence rather than a depth comparison across classes.)
3. **Name-suffix** — `title` minus a type suffix (`X Dungeon|Cave|Mine|Lair|…` → `X`) matched via `name_index`.
4. **Infobox `location`** — extract `[[Target|…]]` link targets from the page's infobox `location` wikitext (§5),
   normalize, resolve each via `name_index`; if several resolve, take the one `name_index` ranks most specific, else the
   **first in wikitext order** (deterministic).
5. **FLAG** → `("place:gielinor", "FLAG")` — unresolved, report-not-fail.

**Build becomes multi-pass.** Because a content place may parent to *another* content place, `build_world` can no longer
emit node+edge in one loop. Pass 1: emit all nodes (backbone + filtered content) and build the complete `name_index`.
Pass 2: compute each place's `(parent, signal)` via rungs 1–4 over the full index. Pass 3: the reachability resolve
(§3.1). Pass 4: emit `located_in`/`same_entity` edges. Node/edge **identity and ordering stay deterministic** (titles
iterated in sorted order, as today), preserving byte-stability and the `0xB0` edge band.

### 3.1 Reachability resolve (acyclicity by construction)
After every place has a candidate parent, build the parent digraph and, for each non-backbone place, walk parent-pointers
to the root. Any place that hits a cycle or a dangling pointer before reaching `place:gielinor` is **demoted to FLAG**
(re-parented to the root, signal `FLAG`). Deterministic; guarantees a single root and no cycles regardless of future
ingest. (Measured today: 0 demotions — but the guard is a forward invariant, not decoration.)

## 4. Noise filter — `is_excluded(title, categories)` (the shared OUT predicate)
```
IN_NAMES := {category name for each IN type-category}   # Raids, Dungeons, Minigames, Guilds, …
is_excluded(title, cats) := title.lower().startswith("list of ")
                            or title in IN_NAMES                       # self-referential index page
                            or (cats & {"Discontinued content", "Locations that do not appear in-game"})
```
- **Builder:** an excluded page emits **no node** (skipped before classify, like an OUT category) and is therefore never
  eligible as a parent (closes the `bounty-hunter → place:minigames` fake-parent path).
- **`verify_world_coverage.py`:** excluded members are subtracted from each category's denominator and reported on a
  dedicated `OUT (noise): N` line — **never** counted as "missing". Keeps `have N/total` honest (e.g. `Dungeons 177/177`
  stays 177/177 after `List of dungeons` leaves).
- One definition, imported by both — the IN/OUT filter remains "the one editorial definition of what is a place" (world-
  skeleton spec §3.1), now with an explicit OUT clause.

## 5. New reproducible brick — the infobox `location` snapshot
- **`data/fetch_world_infoboxes.py`** — for every title in `wiki_location_categories.json`, fetch the page's infobox
  `location` parameter via the MediaWiki API (`action=query&prop=revisions&rvprop=content` or the parsed-infobox
  endpoint), paginated. Mirrors `fetch_world_locations.py`; **`--refresh`** re-pulls to flag drift. The exact infobox
  parameter name is **confirmed at fetch time** (micro-item: some location pages use `{{Infobox Location}}` with a
  `location`/`map`/`members` field set — the fetcher records the raw `location` wikitext verbatim).
- **Committed raw `data/raw/wiki_location_infoboxes.json`** — `{title: {location: "<verbatim wikitext>", source_url}}`
  + a `_provenance` block (matching the existing snapshot's shape).
- **Deterministic parser** (in `kg_ingest/builders/world.py`): `parse_infobox_links(wikitext) → [normalized names]` —
  regex-extract `[[Target|alias]]` / `[[Target]]`, strip the alias, `_norm`. Rung 4 resolves the deepest hit.

## 6. Editorial artifacts (owner-review gates)
- **`data/map/world_parenting.json`** — owner-authored override for the post-infobox tail:
  `{ "<place:slug>": { "parent": "<place:id>", "source_url": "...", "source_token": "<verbatim>" } }`. Drafted
  wiki-grounded by the implementer, **owner-reviewed** (gate). Report-not-fail if a slug isn't in the graph (editorial,
  may pre-stage). Each entry is source-grounded exactly like every other datum.
- **`world.json` backbone additions** — only where a real region/town is **genuinely absent as a node** (the simulation
  found ~13 distinct hint-names that already exist as unparented nodes vs. a smaller set genuinely missing, e.g.
  `Brimhaven`). Owner-reviewed top-level shape, like the original backbone.
- The visual collapsible tree (`world_skeleton.html`, built during the world-skeleton brainstorm) remains the sign-off
  medium for the residual pass.

## 7. Components & changes
- **`kg_ingest/builders/world.py`** — `name_index` includes content places; `parent_for` becomes the 5-rung stack
  returning `(parent, signal)`; `is_excluded` OUT predicate; `parse_infobox_links`; the reachability resolve; load
  `world_parenting.json` + `wiki_location_infoboxes.json`. Place-`src` edge band (`0xB0`) and the seeded rekey are
  **unchanged** (re-homing only changes edge `dst`, not edge identity/count). The `extra_seen` contract with `build_map`
  is preserved.
- **`data/fetch_world_infoboxes.py`** — new fetcher (above).
- **`data/raw/wiki_location_infoboxes.json`**, **`data/map/world_parenting.json`** — new committed data.
- **`data/verify_world.py`** — ADD reachability hard-fail (every place reaches `place:gielinor`); keep report-not-fail
  residual; print a **per-signal breakdown** (`re-homed by override/category/name-suffix/infobox`) and a
  `re-homed X/190 · residual Y` line.
- **`data/verify_world_coverage.py`** — exclude the noise set from denominators; add the `OUT (noise): N` line.
- **`kg_ingest/assemble.py`** — pass the two new inputs to `build_world`; re-assemble. **Byte-stable** (re-run =
  identical bytes). **Node count drops by 15** (noise removed). **Edge delta:** the 15 noise nodes' `located_in` edges
  are removed (−15); every *re-homed* edge keeps its identity (id = `hash(pid#edge#located_in)`, independent of `dst`) —
  only its `dst` changes. So `located_in` edge count drops by 15; `same_entity` edges are unaffected (only backbone
  emits them, and no backbone place is noise).
- **`kg/competency_questions.json`** — add e.g. *"What region is Draynor Village in?"* / *"What contains the Dwarven
  Mine?"* (now resolve to a real place, not the root).

## 8. Validation & success criteria
- `assemble` **byte-stable**; `validate_kg` / `validate_cost` / `verify_world` / `verify_world_coverage` exit 0
  (structural hard-fails pass; residual report-not-fail).
- **TDD** (each a failing test first):
  - content-place parenting re-homes a known case (e.g. `place:ardougne-sewers-mine` → `place:ardougne`, where the
    parent is an *ingested* content place, not backbone);
  - the reachability resolve **demotes** an injected cycle to FLAG (unit) and `verify_world` **hard-fails** on an
    injected cycle in the committed graph (gate);
  - a noise page (`List of dungeons`) emits no node and is **not** counted as a coverage miss;
  - `parse_infobox_links` extracts the right targets; rung 4 parents a settlement with no region category;
  - override beats category/name/infobox; an override to a missing slug reports-not-fails.
- Golden + slice-1..7 + world-skeleton tests stay green. The 4 `tests/drop_rates/` collection errors are pre-existing &
  unrelated.
- The per-signal report **proves** the re-homing: `re-homed X/190 · residual Y` with the residual fully listed (the
  to-do), and each re-homed place attributable to a named signal.

## 9. Build sequence
1. **TDD `is_excluded` + noise filter** → builder skips 15; coverage denominator excludes them. (No new data dep.)
2. **TDD content-place parenting** → `name_index` over all nodes; `parent_for` rungs 1–3 + signal return. (+52.)
3. **TDD reachability resolve** → demote-to-FLAG; `verify_world` hard-fail + per-signal report.
4. **Fetch + commit** `wiki_location_infoboxes.json`; **TDD `parse_infobox_links`** + rung 4. (Drives the 124 down.)
5. **Draft `world_parenting.json`** (wiki-grounded) for the tail + **backbone additions** → **owner-review gate**.
6. **Re-assemble (byte-stable)**, competency questions, whole-branch review, PR.

## 10. Out of scope (unchanged from the world-skeleton roadmap §7)
The bottom-up attaching layers themselves (shops scale-up · NPCs · objects/resources · transport + `gives_access` ·
facilities) · chunk/coordinate geometry · governance EDGES + `faction` nodes · monsters/`drops`. This slice only
re-homes the existing place set and adds the parenting machinery they will all reuse.

## 11. Open micro-items (settle in implementation)
- Confirm the infobox parameter name(s) carrying the parent (`location` vs `map`/region fields) at fetch time; record the
  raw value verbatim regardless.
- A few flagged places may warrant a new coarse `place_type` (e.g. `mountain` for Mount Karuulm) vs mapping to `region` —
  defer unless an override needs it.
- `content_kind` stays advisory (the world-skeleton "slayer dungeon over-tag" lesson) — re-homing doesn't touch typing.
