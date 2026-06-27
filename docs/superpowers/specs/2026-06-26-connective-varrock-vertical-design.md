# Connective Varrock Vertical (acquisition spine) — Slice 6

> **Status:** DESIGN (2026-06-26). The first **connective** slice — turns the deep item *catalog* into a *graph of
> Gielinor* by adding the containment/economic spine (`place`▸`npc`▸`shop`▸item). Branch: `feat/connective-varrock`
> (off `main`, which now holds the v2 item-facet layer, PR #16). Builds on the engine/evaluator + the item nodes.

## 0. Why this slice

The graph is a rich item catalog but has **no relational/spatial tissue** — `located_in`/`operates`/`sells` are all
reserved, so the planner cannot answer the most basic acquisition question ("where/how do I get item X"). This builds
the owner's intended containment model (**State ▸ Location ▸ NPC ▸ Shop ▸ Item**) on the **Varrock worked example**,
with diary/quest unlocks as **conditional edge-modifiers** (NOT flat `effect→region` anchors). The data is already
authored: `data/map/varrock.json` (a 60 KB "gold-standard pilot", owner-editorial-pending) + the field guide
`data/map/ontology-template-guide.md` + the world hierarchy `data/map/OSRS Ontology.md`.

## 1. Decisions (settled in brainstorming, 2026-06-26)

| # | Decision | Choice |
|---|---|---|
| 1 | Place kind | **`place`** (already live; chunk-ready — schema: "Geometry = a chunk-set. Supersedes the v1 region kind") — NOT legacy `region`. Bridge `place:varrock → region:varrock` via `same_entity` |
| 2 | Scope | **Acquisition spine, Varrock branch only:** Gielinor▸Misthalin▸Varrock▸districts (16 places) + 15 shops + their operator NPCs + `located_in`/`operates`/`sells` |
| 3 | Place facets | **containment** (`located_in`) + **governance** (`ruled_by`/`faction` as node *data*); **geometry** (`chunks`/`coordinate_fields`) reserved-but-empty (deferred) |
| 4 | Conditional gates | the 7 gated sells → a `cond_group` on the `sells` edge, reusing the existing `QUEST`/`ACHIEVEMENT_DIARY` atoms + the evaluator |
| 5 | Item resolution | builder resolves `item_name`→`item_id` against `item_dictionary` (canonical match; collision lesson); auto-imports resolved items; **flags** unresolvable (skip + disclose) |
| 6 | Pricing/currency | **deferred to the cost layer** — `price_each`/`qty`/`currency` NOT in the graph (price tokens trip `validate_cost`; consistent with the slice-4 repair-fee deferral) |
| 7 | Deferred | full world skeleton (`OSRS Ontology.md`) · chunk geometry · governance *edges* + `faction` nodes · non-operator npcs · monsters/`drops` · activities · transport/`gives_access` · shop pricing |

## 2. Model additions (flip reserved → live)

- **`model.py`**: add `NodeKind.NPC = "npc"`, `NodeKind.SHOP = "shop"`. (`PLACE` may already exist as a NodeKind — if
  not, add `NodeKind.PLACE = "place"` to match the live schema kind.) Add `EdgeType.LOCATED_IN = "located_in"`,
  `EdgeType.OPERATES = "operates"`, `EdgeType.SELLS = "sells"`. (`SAME_ENTITY` exists from slice 1.)
- **`kg/schema.json`**: flip `node_kinds.npc` + `node_kinds.shop` and `edge_kinds.located_in`/`operates`/`sells`
  from `reserved` → `live`. Their declared domain/range already fit: `located_in` (place/npc/monster/scenery/shop →
  place), `operates` (npc → shop), `sells` (shop → item, `cond=optional`). Update each `data_keys` to the actual shape
  (e.g. `shop.data_keys = ["operator", "aliases"]` — drop `currency`, deferred; `npc.data_keys = ["role", "aliases"]`).
  The `model enums ⊆ schema` invariant stays green.

## 3. The nodes & edges

**Nodes** (from `varrock.json`):
- `place:<slug>` (16) — `data = {place_type, ruled_by?, faction?}`. The Varrock branch (Gielinor▸Misthalin▸Varrock▸13
  districts).
- `npc:<slug>` (the shop **operators** only, ~15) — `data = {role, aliases?}`.
- `shop:<slug>` (15) — `data = {operator, shop_type, aliases?}`.

**Edges** (none are item-`src` — they get their own rekey, NOT the shared item-`src` rekey):
- `located_in`: `place→parent` (skip the world root), `npc→place`, `shop→place`.
- `operates`: `npc→shop` (from `npc.operates` / `shop.operator`; verifier checks reciprocity).
- `sells`: `shop→item:<resolved id>`, `data = {noted?, source_token}`, `cond_group` set for the 7 gated offers.
- `same_entity`: `place:varrock → region:varrock`, `place:grand-exchange → region:grand-exchange` (the places with a
  matching legacy `region` node — link-don't-merge; the legacy region nodes + diary flat-anchors are untouched).

## 4. Conditional gates → `cond_group` (reuse the evaluator)

The 7 gated sells (all in Zaff's Superior Staffs) carry a `condition = {type, ref, state}`. Map each to a
`ConditionGroup` (one atom, `Op.AND`) on the `sells` edge — the SAME mechanism quests/diaries use:
- `type: "quest"` → `ConditionAtom(atom_type=QUEST, subject=quest:<slug(ref)>, state=<in_progress|completed>)`
  (e.g. ref `"What Lies Below"` → `quest:what-lies-below`).
- `type: "achievement_diary"` → `ConditionAtom(atom_type=ACHIEVEMENT_DIARY, subject=diary:<region>:<tier>,
  state=completed)` — ref `"Varrock Diary - Hard"` → `diary:varrock:hard`. A tier-less ref (`"Varrock Diary"`, the
  "Additional battlestaves" offer) maps to the base tier per the data's intent (settle in the plan: most likely
  `diary:varrock:easy`, the minimum unlock — verifier-checked against existing diary nodes).
The verifier confirms every `ref` resolves to an existing quest/diary node; an unresolvable ref is a flagged violation.

## 5. The builder & assemble wiring

`kg_ingest/builders/map_varrock.py` (or `build_map`) — `build_map(map_data, item_resolver, region_ids) -> (nodes,
edges, groups)`:
- emits place/npc/shop nodes (npcs filtered to shop operators) + `located_in`/`operates`/`sells`/`same_entity` edges +
  the conditional `cond_group`s.
- **item resolution:** an `item_resolver(item_name) -> item_id | None` built from `item_dictionary` (exact/canonical
  name match; on ambiguity prefer the canonical/non-variant page; return None + collect a flag on no/ambiguous match).
  Resolved ids feed `sells` dsts; **a resolution report (resolved / unresolved counts + the unresolved names)** is the
  builder's headline output.
- builder-local edge band `0xE0000000`, group band `0xD0000000` (both verified free).

**`assemble.py`:** `build_map` runs **before reference collection** (its `sells` dsts feed `referenced_item_ids` so
`build_items` auto-imports the sold items, like degrade/repair). Its edges are place/npc/shop-`src` (NOT item-`src`),
so they re-key in their **own** `rekey` call (the `same_entity` it emits is place-`src`, so it cannot collide with
`build_items`' item-`src` `same_entity` — different owners). The map nodes are added to `dedup_nodes`. The global
edge-id-uniqueness assert covers them.

## 6. Data + verifier

- **`data/map/varrock.json`** — authored (owner-editorial-pending). This slice consumes it; owner editorial review of
  the connective facts is the human gate.
- **`data/verify_map.py`** — structural source-grounding gate (exits non-zero on violation): every `located_in` target
  is a place present in the file; every `shop.operator` is a present npc AND reciprocally in that npc's `operates`;
  every `sells.item_name` resolves in `item_dictionary` (**the resolution report** — unresolved names listed);
  every `condition` has a valid `type` (quest/achievement_diary) + a `ref` resolving to an existing quest/diary node +
  a `source_token`; slug uniqueness. Owner editorial review remains the gate for facts a check can't verify.

## 7. Validation & success criteria

- `validate_kg` exit 0 (`located_in`/`operates`/`sells`/`same_entity` VIOLATION-clean; cond_groups well-formed).
- `validate_cost` exit 0 (NO price/currency tokens in the graph — pricing deferred).
- `assemble` byte-stable; global edge-id assert passes.
- Golden + slice-1..5 tests green; `verify_map.py` exit 0 with a clean resolution report.
- New **TDD** tests: `build_map` (place/npc/shop nodes + located_in/operates/sells per the data; the Zaff→shop→
  battlestaff chain; the conditional cond_group on the gated sells); item resolution (a known name resolves; an
  unresolvable name is flagged, not silently dropped); the `place:varrock → region:varrock` same_entity bridge;
  all-edge-ids-unique with the new (non-item-`src`) families present.
- **+1 competency question:** *"Where can I buy a battlestaff, and what gates it?"* → `item:<battlestaff>` has an
  in-edge `sells` from `shop:zaffs-superior-staffs`, which `operates`←`npc:zaff` and `located_in`→`place:varrock`, and
  the gated offer carries a `cond_group` (What Lies Below). (`method: "sold_by"`, expect ≥1 selling shop.)
- Graph grows by ~16 places + ~15 shops + ~15 npcs + their edges + auto-imported sold items.

## 8. Out of scope — named follow-ups

1. **Full world skeleton** — parse `data/map/OSRS Ontology.md` → all continents/oceans/islands/kingdoms/city-states as
   `place` nodes (with `located_in` + `ruled_by`/`faction`). The geography backbone Varrock + future towns hang off.
2. **Chunk/coordinate geometry** — populate `place.data.chunks` / `coordinate_fields` (+ per-entity point-chunks) from
   chunk-picker-v2 / Region Locker; the v2 decision-1 coordinate "where" relation. (`place` already reserves the keys.)
3. **Governance edges + `faction` nodes** — promote `ruled_by`/`faction` data to `ruled_by`/`aligned_with` edges +
   `faction`/`deity` nodes.
4. **The rest of `varrock.json`** — non-operator npcs, monsters (+ link the existing `drops` layer), activities,
   transport/`gives_access`. Then other towns.
5. **Shop pricing/economy** — `price_each`/`qty`/`currency` → the cost layer (+ resolve the `validate_cost`-vs-
   `currency` question: currency-as-structural-attribute vs cost token).

## 9. Open micro-items (settle in implementation)

- The tier-less `"Varrock Diary"` condition ref → which diary tier (likely `diary:varrock:easy`); verifier-checked.
- Builder node/edge/group bands: nodes are id-keyed (no band); edges `0xE0`, groups `0xD0` — confirm disjoint.
- `NodeKind.PLACE` may already exist (place is live) — check before adding.
- Item resolver: how to disambiguate a name matching multiple `item_dictionary` pages (prefer the canonical page;
  flag true ambiguity) — reuse the slice-5 `select`-style canonical preference.
