# Farming Patches Layer — objects/resources slice 2 — Design

> **Status:** approved (brainstorm 2026-07-10; hardened by an adversarial live-source + repo-code
> review 2026-07-11 that found 5 critical + 11 major defects in the first draft — all folded in below).
> The second slice of the bottom-up **objects/resources** layer (after facility taxonomy PR #24).
> Builds a source-grounded **`farming_patch:` node roster** attached to the place skeleton via
> `located_in`. Unlike the pure-roster facility layer, this slice **emits edges** (`located_in`) —
> so it follows the shop/NPC bottom-up template, not the zero-edge facility one.
>
> **Source-verified facts (live, 2026-07-10/11):**
> - **No `Bucket:farming*`, no `Module:Farming`** exists (the `Bucket:` namespace ns9592 = 47 buckets,
>   zero farm/patch/seed match). The structured source is a set of **transcluded wikitables**.
> - **`Category:Farming patches` = exactly 12 members** — the completeness anchor. Classification:
>   **9 real patch types** (Allotment, Flower, Herb, Bush, Hops, Tree, Fruit tree, Spirit tree,
>   **Coral** — a 2025-Sailing patch), **1 umbrella** (`Special patches`), **1 location page**
>   (`Coral Nurseries`, `{{Infobox Location}}` → dedupe to a `place:`, NOT a patch),
>   **1 NPC** (`Chet`, `{{Infobox NPC}}`, the coral gardener → `force_exclude`, keep as `gardener`).
> - **Herb & Flower have NO own `/Patches` subpage** — `Allotment patch/Patches` is the sole source for
>   all three, with a **per-row "Types" bullet cell** stating exactly which type(s) each site has
>   (4 guard forms: full combo / allotment+flower-no-herb / herb-only / flower-only). A blind
>   3-node-per-row expansion **fabricates ~10-15 nonexistent patches** (Kastori is flower-only;
>   Troll/Weiss/Harmony are herb-only) — the cardinal never-fabricate violation.
> - `Special patches/Patches` = **4 sub-tables with 3 distinct column schemas** (Special / Special-tree
>   [Sapling col] / Cactus [no Type col] / Activity [no Map]); a single generic parser silently drops
>   the whole **Cactus** type (2 real patches).
> - **`place:coral-nurseries` EXISTS** in the committed skeleton — coral resolves cleanly (it does not FLAG).
> - Shared place-resolution helpers (`build_place_name_index` + `resolve_shop_places` + `_norm`, imported
>   as `npcs.py` does) resolve **~57/68** location rows including all Varlamore/Sailing places.

## 1. Goal

Turn the OSRS farming-patch tables into a **normalized, deduped, place-attached roster** of
`farming_patch:<slug>` nodes — one per **(patch type × place)** instance ("the herb patch at
Catherby") — each tagged with its patch type + gardener + provenance, and wired `located_in` its
skeleton place. This realizes the long-`reserved` `farming_patch` node kind (P8 of the ontology
nuance catalog: the *place × type instance* that is the eventual carrier of per-site farming
modifiers) at its **roster altitude**, and gives the location skeleton a bottom-up completeness
cross-check from a new domain.

**Non-goal (this slice):** `instance_of` edges + a `patch_type` node kind (P8's type/instance split),
scoped diary-modifier edges, coordinates/chunk geometry, per-site patch `count`, the coordinate-less
activity + quest patch tail, gardener-as-`npc:` nodes. All deferred — see §10.

## 2. Architecture (fits the existing pipeline)

The shop/NPC bottom-up template — **two raw bricks** (the category-roster classifier + the
location-table wikitext) + a builder that resolves `located_in` against the committed skeleton:

```
data/fetch_farming_patches.py  →  data/raw/wiki_farming_patch_category.json  (Category:Farming patches + per-member infobox = the roster + classifier)
                                →  data/raw/wiki_farming_patch_tables.json    (raw wikitext of the /Patches subpages + inline coral table)
data/map/farming_overrides.json  (owner-authored force_exclude / place_overrides — the override rung)
                                          │
kg_ingest/builders/farming.py  ──build_farming_patches(category, tables, place_nodes, overrides)──>  farming_patch: nodes + located_in edges
                                          │
kg_ingest/assemble.py  (new block AFTER build_map ~line 524; place index from world_nodes+map_nodes
                        filtered to PLACE — the shops/npcs template; seeded rekey; register ids in dedup_nodes)
                                          │
kg/{nodes,edges}.json   (+ farming_patch: nodes + located_in edges; byte-stable)
                                          │
data/verify_farming_patches.py       (structural, hard-fail)
data/verify_farming_coverage.py      (coverage, report-not-fail — category cross-check + FLAG residual)
```

## 3. Locked decisions (brainstorm outcomes + review hardening)

- **D1 — Scope = grounded roster.** `farming_patch:` nodes + `located_in→place`; patch type,
  gardener, source as **data fields**. Defer the P8 `patch_type` node kind + `instance_of` edges,
  the scoped diary-modifier edges, and coordinate geometry. Mirrors the "roster/skeleton first,
  mechanics later" discipline every prior layer followed (facility roster before `requires_facility`
  edges; world skeleton before content mechanics).
- **D2 — Granularity = one node per (patch_type × place).** "The herb patch at Catherby" is one node;
  the allotment cluster beside it is another. **Verified safe:** an adversarial pass across every type
  table found **no place with two distinct same-type patches**, so the (type, place) key never merges
  genuinely-distinct patches. Only per-site patch *count* is collapsed (Grape/Vinery 12→1, allotment
  2→1, seaweed 2→1, coral 2→1) — a deferred field, disclosed by the coverage verifier so the loss is
  never mistaken for a data gap.
- **D3 — Completeness anchor = the CATEGORY, not the master page.** `Category:Farming patches` (12
  members) is the authoritative type roster; `Farming/Patch locations` is a *convenience* index (it
  omits the standalone coral pages + Chet). Enumerating the category forces conscious classification
  of every member (the owner-caught coral gap proved the master page non-authoritative — same lesson
  as the shop layer: a curated index is never a census).
- **D4 — Census = core 9 types + special crops + coral; defer the messy tail.** Ship the uniform-ish
  tables (the 9 types + the coord'd/tree/cactus special crops incl. **Cactus + Redwood**). **Defer**
  the heterogeneous coordinate-less **Activity** sub-table (Tithe Farm / Chambers of Xeric / Managing
  Miscellania) and the **5 quest-gated** patches to a fast follow-up, disclosed as a coverage residual.
  Exclude non-cultivable pseudo-rows (raw "Weeds"/"Grass"). ~85-90 nodes.
- **D5 — Coords DEFERRED.** The `{{Map}}` template has **6 real syntaxes** (positional / non-first-
  positional / `mtype=polygon` vertex-list with no single x,y / comma+SPACE / `x:N,y:N` colon /
  `x=N|y=N` named) plus **instanced maps** where a coord stored as a surface tile is silently *wrong*.
  Coords are not needed for the roster's job (type + place + gardener + `located_in`), so they are
  deferred to the chunk-geometry layer (which re-fetches anyway) rather than paying a 6-syntax parser
  + correctness traps here. **The parser must never store a coordinate this slice.**
- **D6 — Type emission is per-row, from the actual "Types" cell** — never a fixed expansion. The
  Allotment table's per-row `*[[…patch]]` bullet cell states which of {allotment, flower, herb} that
  site has; all 4 guard forms are handled. This is the fix for the fabrication-critical draft bug.
- **D7 — id identity = (patch_type, resolved place); id decoupled from prose.** See §5. `patch_type`
  runs through `ids.slugify` (dash-only — `fruit_tree`→`fruit-tree`, `spirit_tree`→`spirit-tree`; the
  graph has zero underscore slugs) and the place component comes from the **resolved place id**, not
  re-slugged raw wikilink prose. A **committed injectivity fail-fast** replaces the order-dependent
  `-k` fallback the shop/facility layers use — that fallback reintroduces exactly the id churn PR #26's
  recipe-id-stability layer exists to kill.
- **D8 — `patch_type` is a CLOSED vocab, finalized at implementation.** The **core 9** are locked:
  `{herb, allotment, flower, bush, hops, tree, fruit_tree, spirit_tree, coral}`. The **special-crop**
  members are **enumerated from the `Special patches/Patches` parse** (each crop row = a patch_type —
  cactus, redwood, calquat, celastrus, crystal, teak/hardwood, belladonna, hespori, anima, grape,
  mushroom, seaweed, … whatever the table actually lists), not a hand-fixed list this spec might get
  wrong. The union is **frozen once** (the committed vocab constant + a verifier check); extend only
  via a documented add. Locking it makes today's strings the future `instance_of` node slugs 1:1, so
  P8's type/instance split grafts on without a rename.

## 4. Sources & the new bricks

### 4a. `Category:Farming patches` (verified live — the roster anchor)

`action=query&list=categorymembers&cmtitle=Category:Farming_patches&cmtype=page` → 12 members
(§ header). Each member's page is fetched for its `{{Infobox X}}` to classify it: patch-type page
→ parse its table; `Special patches` → umbrella; `Coral Nurseries` (`Infobox Location`) → a place,
not a patch; `Chet` (`Infobox NPC`) → `force_exclude`.

### 4b. NEW brick — `data/fetch_farming_patches.py`

Mirrors `data/fetch_world_locations.py` (category API) + `data/fetch_npc_infoboxes.py` (revisions
API), UA `GildedTome-research/1.0 (aalvarez0295@gmail.com)`. Writes **two** sorted,
`_provenance`-stamped snapshots:
- **`data/raw/wiki_farming_patch_category.json`** — `{member → {infobox, classification, source_url}}`
  for the 12 category members (the completeness anchor + member classifier).
- **`data/raw/wiki_farming_patch_tables.json`** — the raw wikitext of each location table: the
  transcluded `/Patches` subpages (`Allotment patch/Patches` [holds allotment+flower+herb],
  `Bush patch/Patches`, `Hops patch/Patches`, `Tree patch/Patches`, `Fruit tree patch/Patches`,
  `Spirit Tree (Farming)/Patches` — note `Spirit tree/Patches` **redirects** here), and
  `Special patches/Patches`. Each table stored with `{page, source_url, wikitext}` so the parser is
  offline-reproducible and every node traces to a `(page, row-index)` pair.

### 4c. `data/map/farming_overrides.json` (owner-authored override rung)

```json
{ "force_exclude": [{value, reason, source_url}],
  "place_overrides": [{location, place_id, reason, source_url}] }
```
- **`force_exclude`** — `Chet` (NPC swept into the category), `Coral Nurseries` (the location page).
- **`place_overrides`** — the ~6 trivially-resolvable FLAGs the `_norm` index misses:
  `Varrock Castle→place:varrock`, `Falador Park→place:falador`,
  `Gnome Stronghold→place:gnome-stronghold` (a redirect target the resolver does not follow),
  `Tree Gnome maze→place:tree-gnome-village`, `Underwater→place:fossil-island`,
  `Draynor Manor→place:draynor-village`, `Ortus Farm→place:civitas-illa-fortis` (a full
  allotment/flower/herb Varlamore hub — override rather than backfill 3 FLAGs).
- Tolerant loader (missing file → empty), copying `_load_facility_overrides` (assemble.py:368-372).

## 5. Data model (what lands in the graph)

Per surviving (patch_type × place) instance:

```
Node:
  id    = "farming_patch:" + slugify(patch_type) + "-" + <place_slug>   # e.g. farming_patch:herb-catherby
  kind  = farming_patch
  name  = "<Patch type> patch (<Place>)"                                 # e.g. "Herb patch (Catherby)"
  slug  = id minus the "farming_patch:" prefix
  data  = {
            "patch_type":   "herb",                    # CLOSED vocab (D8); dash-slug form in the id, token form here
            "gardener":     "Dantaera",                # OPTIONAL: 0..n names parsed after "Gardener(s):"; omit if none
            "source_url":   "https://oldschool.runescape.wiki/w/Allotment_patch/Patches",
            "source_token": "North of [[Catherby]]"    # VERBATIM raw Location-cell text (NOT a fabricated composite)
          }
Edge (when the place resolves):
  type = located_in,  src = farming_patch:...,  dst = place:...,  cond_group = null,  data = {}
```

- **Identity = (patch_type, resolved place id).** `<place_slug>` = the **resolved** place node id's
  slug (`place_id.split(":",1)[1]`) — equals the extracted `[[Place]]` wikilink slug in the common
  case, and comes from a `place_override` for the ~6 escape-hatch cases. **Injectivity fail-fast:**
  `build_farming_patches` asserts the (patch_type, place)→id map is injective and raises on any
  collision (owner then disambiguates via override). **No `-k` order-dependent fallback** (D7).
- **Collapse happens INSIDE the builder.** The (patch_type, place) key emits **one byte-identical
  Node + one `located_in` edge per id** — because `assemble.py`'s `dedup_nodes` (159-172) is
  first-wins only for *byte-identical* nodes and **raises `ValueError` on any differing field**. The
  cross-table coral case (inline coral table vs the `Special patches` coral row — same place, coords
  differ by 1 tile) MUST be deduped in the builder by **(patch_type, place)** (not coords), else
  assemble crashes. A builder test covers the multi-source-same-id case explicitly.
- **FLAG (unresolved place):** emit the node with **no `located_in` edge** (id's place component =
  the extracted wikilink-target slug), disclosed by the coverage verifier — exactly the shop/npc
  pattern. (Re-homing a FLAG later can change its id — a disclosed residual, same class as the
  shop/npc `located_in` backfill to-do.)

## 6. Schema changes (additive only)

1. **`src/osrs_planner/engine/kg/model.py`** — add one `NodeKind` member after `FACILITY` (line 36):
   ```python
   FARMING_PATCH = "farming_patch"   # place x patch-type instance (P8); located_in a place
   ```
   This is the **hard requirement** (not the schema.json flip): `json_store.from_dir` coerces every
   node via `NodeKind(d["kind"])` (json_store.py:80) and `validate_kg` hard-fails `[vocab]`
   (validate_kg.py:303) on an undeclared kind. **No new `EdgeType`** (`located_in` already exists).
2. **`tests/engine/test_kg_model.py`** — add `"farming_patch"` to the exact-set-equality golden
   assert `test_node_kind_members_match_schema_taxonomy` (lines 14-22), **in the same change** (the
   test is an exact `==`, so it fails until updated).
3. **`kg/schema.json`** — `farming_patch` is already *reserved*; flip `status: live` + populate
   `data_keys` additively: `["patch_type", "gardener", "source_url", "source_token"]`. (Cosmetic —
   `check_schema` reads kinds by key regardless of status; the enum member above is what gates.)
4. **`kg/schema.json` `located_in.domain`** — additively add `farming_patch` (currently
   `[place, npc, monster, scenery, shop]`). `validate_kg` reads domain straight from the schema (no
   code edit); `farming_patch` is a pure leaf, so the acyclicity gate (`_resolve_reachable`, which
   traverses only `place:` ids) is unaffected.

## 7. Parser rules (the heart — every critical fix lives here)

Deterministic wikitable parse over `wiki_farming_patch_tables.json`. **Column-position parsing**
(NOT gardener-anchored — gardener-less single-type rows like Harmony/Kastori resolve, so a
gardener-anchored miss would be invisible).

- **Type emission (D6):** for each row, read the **"Types" bullet cell** and emit one (type, place)
  instance **per `*[[…patch]]` link actually present** — never a fixed expansion. Handles the 4
  Allotment guard forms. Herb & Flower ride the Allotment table (no own subpage).
- **`Special patches/Patches` (D4):** parse the 3 kept sub-tables by their distinct headers —
  Special (crop rows), Special-tree (Sapling column), **Cactus** (no Type column → type from the
  section header / `Map group=cactus`). **Skip** the 4th (Activity, no `{{Map}}`) sub-table — deferred.
- **Coral (D3/D4):** emit one `coral` node `located_in place:coral-nurseries`; **dedup** the inline
  `Coral nursery (patch)` table row against the `Special patches` coral row by (patch_type, place).
  Keep **Chet** as the `gardener` (he is `force_exclude`d only as a *node*).
- **Place resolution:** extract the `[[Place]]` wikilink from the Location cell; for **multi-link
  cells** resolve the **trailing anchor** (`[[Hemenster|North]] of [[Ardougne]]` → **Ardougne**, not
  the first link — first-wins would silently mis-home 3 patches with no FLAG). Reuse
  `build_place_name_index` + `_norm` + `resolve_shop_places`-style extraction from
  `kg_ingest/builders/shops.py` (imported exactly as `npcs.py` does), over a place index built from
  **`world_nodes + map_nodes`** filtered to `NodeKind.PLACE`. Unresolved after `place_overrides` →
  FLAG (no edge), disclosed.
- **Gardener:** parse **0..n** wikilinks after `Gardener(s):` (multi-gardener "X or Y", plural
  "Squirrels"), strip italics/notes; omit the key if none. Advisory (cosmetic).
- **`source_token`:** the **verbatim** raw Location-cell text; the `(page, row-index)` pair is the
  structured provenance the hard-fail verifier traces. Never a synthesized "Type — [[Place]]" composite.

## 8. Verification & never-fabricate

- **`data/verify_farming_patches.py`** (structural, **hard-fail exit 1**) — every `farming_patch`
  node's `source_token` traces to a real row in `wiki_farming_patch_tables.json` at its `(page,
  row-index)`; every `patch_type` is in the closed vocab (D8); every `gardener`/place is present in
  that row; every `located_in.dst` is a real committed `place:` node. Reuses the builder's pure
  helpers. No fabricated types, no invented placements.
- **`data/verify_farming_coverage.py`** (coverage, **report-not-fail exit 0**) — cross-checks the
  **12-member category**: every patch-*type* member yielded ≥1 node (the completeness probe); reports
  `parented N / FLAG R` (itemized unresolved list = the place-skeleton backfill to-do), the
  **deferred tail** (Activity + quest patches, explicitly listed so the gap is disclosed not hidden),
  and the **patch_count collapse** (Grape 12→1, etc., so it is not mistaken for data loss).
  `--refresh` re-queries the category + tables live.
- **Never fabricate:** a site's absent type is never emitted (D6); coords are never stored (D5);
  a FLAG is disclosed, never homed to `place:gielinor` from this bottom-up layer.

## 9. Testing & competency questions

- **Builder unit tests** (`tests/kg_ingest/test_farming_builder.py`): per-row type emission across
  all 4 Allotment guard forms (incl. herb-only, flower-only — the anti-fabrication cases); Cactus
  type derived from the special-patches header; coral (type,place) dedup + **multi-source-same-id**
  (differing gardener/source — must collapse to one byte-identical node, not crash); Chet
  `force_exclude` while retained as `gardener`; `Coral Nurseries` place-page excluded; multi-link
  trailing-anchor resolution; **id injectivity fail-fast**; `located_in` emission + FLAG (no edge);
  determinism.
- **Assemble/byte-stability** (`tests/kg_ingest/test_farming_in_graph.py`): `assemble` emits the
  nodes+edges, re-run **byte-identical**, `validate_kg` green, the new `NodeKind` loads,
  `farming_patch:herb-catherby` well-formed + `located_in place:catherby`, `verify_farming_patches`
  exits 0.
- **Model/schema tests**: the golden set-equality assert includes `farming_patch`; `data_keys` in
  sync; `located_in.domain` includes `farming_patch`.
- **Fetch-shape tests** (`tests/data/test_fetch_farming_patches.py`): both snapshots' shape +
  `_provenance`, offline-parseable, loaded via `importlib` (the `tests/data` package-shadow gotcha).
- **Competency questions** (answerable from THIS slice alone): (a) "Where are the herb patches?" →
  `farming_patch` nodes with `patch_type=herb` + their `located_in` places; (b) "Is `Chet` a farming
  patch?" → no — `force_exclude`d NPC, retained only as a `gardener` (proves the classifier).

## 10. Scope / non-goals (explicit deferrals — disclosed, not dropped)

- **Coordinates / chunk geometry** (D5) — 6 `{{Map}}` syntaxes + polygon + instanced maps; deferred
  to the chunk-geometry layer (which re-fetches). This slice stores no coordinate.
- **Activity + quest patch tail** (D4) — Tithe Farm / Chambers of Xeric / Managing Miscellania +
  the 5 quest-gated patches; disclosed coverage residual, fast follow-up.
- **`patch_type` node kind + `instance_of` edges** — P8's type/instance split. This slice ships the
  instances (roster) only; the string `patch_type` values (D8) become the future type-node slugs 1:1.
  **Tracked schema gap:** completion needs a new `patch_type` node kind + an `instance_of` **range**
  widen (current range `[place, item, facility]`, schema.json:154).
- **Scoped diary-modifier edges** — the P8 per-site bonuses (Catherby harvest-save %, Falador tree
  disease-immunity, Ardougne teleport) wired into the diary layer with a `scope` qualifier. Later slice.
- **Per-site patch `count`** — the physical-object multiplicity collapsed by D2; disclosed by the
  coverage verifier.
- **Gardener-as-`npc:` node** — broader non-operator NPCs are repo-wide deferred; gardener stays a field.
- **`same_entity` bridges** — coral patch ↔ `place:coral-nurseries`, spirit-tree patch ↔ the future
  transport node. Deferred (link-don't-merge, when the transport layer lands).

## 11. Open micro-items (settle in implementation)

- Pre-existing skeleton **duplicate** `place:gnome-stronghold` vs `place:tree-gnome-stronghold` (both
  named "Tree Gnome Stronghold") — the fruit_tree patch inherits an arbitrary first-wins pick;
  disclose (or fix the skeleton dup separately). **Not introduced by this layer.**
- Exact starter `farming_overrides.json` content — seed the ~6 `place_overrides` + 2 `force_exclude`
  above for owner confirmation; anything else stays a disclosed FLAG.
- Edge band `_EDGE_BAND = 0xE8000000` (verified free, cosmetic — `rekey` re-derives every edge id);
  the seeded `rekey` block is idiomatic but not load-bearing (`farming_patch:*` is a fresh edge-src
  owner namespace). Placed after `build_map` (assemble.py:524), copying the shops/npcs place-index +
  seed idiom (assemble.py:549/566).
- Redirect note: `Spirit tree/Patches` → `Spirit Tree (Farming)/Patches` (fetch the target);
  `Gnome Stronghold` is a redirect the `_norm` resolver does not follow (→ `place_override`).
