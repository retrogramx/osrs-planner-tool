# Entity-Graph Ontology v2 — LOCKED CONTRACT

> **Status:** LOCKED (2026-06-25). Supersedes `2026-06-24-entity-graph-ontology-v1.md`. This is the
> contract every later step (cache node-import, wiki edge-curation, the repo realignment) builds against.
> **Evidence base:** 3 nuance-survey passes (`research/osrs-ontology-nuance-catalog{,-pass2,-pass3}.md`),
> the Going Meta learnings (`research/goingmeta-kg-learnings.md`), the cache-source verification
> (`research/osrs-cache-data-sources.md`), and 9 owner decisions (below). The 14 modeling patterns and the
> full MUST/NICE gap list live in the nuance catalogs; this spec is the consolidated schema + the decisions.

---

## 0. The owner's 9 decisions (the forks)

| # | Decision | Choice |
|---|---|---|
| 1 | "Where" is **three** relations | `located_in` (containment tree) + `rule_zone` (overlapping typed overlay) + coordinate field (OSRS **chunks**) |
| 2 | Interactable kinds | `npc \| monster \| scenery` + a `role` attribute |
| 3 | Relationship edge shape | **reified** (data-carrying) edges for drops/sells/recipe/grants; shops two-way + currency-typed |
| 4 | Requirement kinds | hard `requires` **+** soft `recommended_for` (advisory, strength enum, never blocks) |
| 5 | Identity | **cache-ids** canonical + item page-identity with **variant** children |
| 6 | Aliases | typed `aliases` on nodes (wiki-redirect-sourced) + a search-resolution layer for ambiguous terms |
| 7 | `gate_type` on hard requires | open verb set: `access\|damage\|kill` (combat) + `make\|craft\|…` via the recipe's requires/consumes |
| 8 | Context axes | define `game_mode`, real-time clock, `difficulty_config` **now** (reserve slots), populate later |
| 9 | Competency-questions CI gate | **on from day one** |

---

## 1. Design principles

1. **Schema-as-committed-data.** A single `kg/schema.json` (node kinds + edge kinds with `domain/range` +
   atom vocab) is the source of truth — it drives the builders, the LLM-extraction prompt, and a generic
   `validate_kg` domain/range invariant. *(Going Meta keystone.)*
2. **Link-don't-merge / additive.** The entity layer extends the existing graph; nothing is destructively
   rewritten. `same_entity` bridges new↔existing nodes. Byte-stable assemble + golden tests stay green.
3. **Three source layers** *(not two)*: **cache** = node existence + ids + intrinsic attrs · **Infobox/Bucket**
   = attributes + editorial · **Module/Bucket-relational** = versioned edges (drops/shops/reqs). Ingestion is
   driven by the wiki's own tables (§9).
4. **Cache trivializes nodes; wiki+curation does edges.** Bulk-import nodes from the cache (OpenRS2 + RuneLite
   decoder); author edges/conditionals from the wiki. The Varrock pilot is the **edge-authoring template**.
5. **Source-grounded, validator-gated, byte-stable, provenance-bearing.** Unchanged moat. LLM proposes *shape*;
   every *fact* clears the wiki-citation gate. Two fabrication gates: schema-membership + source-grounding.
6. **Existence vs facts vs DERIVED in separate files.** Asserted nodes/edges first; computed/inferred edges in a
   clearly-marked `kg/inferred.json`, never hand-claimed as wiki fact.

---

## 2. Node kinds

**Live now** (have data today or in the imminent build): `place`, `npc`, `monster`, `scenery`, `shop`, `item`
(+variants), `currency`, `skill`, `quest`, `diary`, `combat_achievement`, `minigame`, `goal`, `transport_system`,
`activity`, `faction`, `task_category`, `facility`, `counter`, `drop_table`, `recipe`, `equipment_bonuses` (facet),
`item_set`, `set_effect`, `farming_patch` (place×type instance), `subquest`.

**Reserved-slot now, populate later** (decision 8 + NICE): `game_mode`, `leaderboard`, `random_event`,
`difficulty_config` (+`invocation_toggle`), `transport_tier`, `mechanic`/`boss_phase`, `spell`, `prayer`,
`music_track`, `hotspot`/`buildable_object`/`room`, `equipment_group`, `money_making_method`, `varbit`,
`deity`/`relic`/`emote`/`book`.

Key shapes:
- **`place`** — recursive; `place_type ∈ {world, continent, ocean, island, kingdom, city, town, settlement,
  district, dungeon, floor, …}`; `aliases[]`; geometry = a **chunk-set** (decision 1).
- **`scenery`** — interactable objects (rocks/altars/anvils/doors/trees/transport-stations); cache `object_id`.
- **`npc` / `monster`** — non-combat vs attackable; both carry a `role` (decision 2): `slayer_master \| tutor \|
  protect_target \| banker \| shopkeeper \| ruler \| quest_giver \| …`.
- **`item`** — **page-identity + variant children** (decision 5): each variant is a cache `item_id` with its own
  stats/value; bridged to the page by `same_entity`; reified edges target the **variant**.
- **`currency`** — coins is just one (`tokkul`, commendation/slayer points, marks, tickets). Prices reference a `currency_ref`.
- **`drop_table`** / **`recipe`** — reified (§4): tables/rolls/membership; recipe = {materials+tools+facility+skill+xp→output}.

---

## 3. Edge kinds

| edge | domain → range | cond_group? | notes |
|---|---|---|---|
| `located_in` | place/npc/monster/scenery/shop → place | no | containment **tree** (decision 1) |
| `rule_applies_in` | rule_zone → place/chunk-set | no | overlapping typed overlay (multicombat/pvp/no_teleport/safe), world-spanning |
| `operates` | npc → shop | no | reciprocal with shop.operator |
| `sells` | shop → item-variant | **yes** | reified: `{price, currency, stock, restock}` + optional gate |
| `accepts`/`buys_back` | shop → item-variant | yes | the buy-side (two-way shops, decision 3) |
| `drops`/`has_table`/`contains` | monster/activity/scenery → drop_table → item-variant | yes | reified `{rate, rolls, drop_type, version}` |
| `consumes` | recipe → item-variant | no | destroyed, quantity (resource gate, decision 7) |
| `produces` | recipe → item-variant | yes | guarded output |
| `requires` | any → (cond_group) | **yes** | **hard** gate; carries `gate_type` (decision 7) |
| `recommended_for` | any → (cond_group) | **yes** | **soft** advisory; `strength ∈ {required_for_survival, strongly_recommended, optional}`; never blocks (decision 4) |
| `gives_access`/`served_by`/`connects_to` | transport_system/scenery → place | yes | transport; system-gate ∧ edge-gate composed |
| `scales_with` | difficulty_config → encounter stat-block + drop_table | n/a | typed difficulty input (decision 8 / pass-3) |
| `grants` | quest/diary/goal/activity → item/currency/None | yes | reified reward payload |
| `progress_towards` | any → goal | no | counters |
| `supersedes` | item→item, goal→goal | no | upgrade ladders |
| `same_entity` | any → existing node | no | identity bridge; `data.basis` |
| `has_bonuses` | item-variant → equipment_bonuses | no | the gear/BIS substrate |
| `member_of` | item → item_set/equipment_group | no | sets |
| `has_part` | quest → subquest | no | composite quests |
| `aligned_with` | monster/item → faction | no | killcount + soothing |
| `counts_toward` | kill/action → counter | no | counters feed |
| `immune_to`/`counters` | monster ↔ damage-type/gear | no | negative relations |
| `does_not_stack_with` | effect ↔ effect | symmetric | negative |
| `realizable_via` | currency → bridge item | no | iron-realizable exit tracing |
| `assigns` | slayer_master/rumour-npc → task_category | weighted | task systems |
| `teaches` | npc → skill | no | tutors |
| `spawns_at` | item → place/chunk | no | free ground spawns (3rd item channel) |
| `service` | npc/facility → effect | cost+cond | repair/toll/lost-item |
| `requires_facility` | activity/recipe → facility | no | anvil/furnace/altar/range |
| `instance_of` | farming_patch/variant → type | no | place×type instances |
| `effect` | item/diary → skill/activity/place/monster | `applies_when` | context-scoped effects |

**Edge-payload principle (cross-cutting):** drops/sells/produces/grants are **attribute-bearing reified relations**
(rate+rolls | price+currency+stock | qty+xp+ticks | parameterized payout) carrying an optional `cond_group` **and a
version discriminator** — mirroring the wiki's Bucket-table rows. Getting this shape right is the #1 re-ingest guard.

---

## 4. Condition system (the engine spine — reused everywhere)

One `requires`/`recommended_for` edge carries a `cond_group` = an AND/OR/NOT tree of **condition-atoms**. The same
mechanism gates quests, diaries, transport, shops, recipes, combat, and difficulty.

**Atoms:** `skill_level`, `combat_level`, `quest` (3-state + **step**), `achievement_diary`, `combat_achievement`,
`item`, `equipped` (≠ owned), `kill_count`, `quest_points`, `aggregate_count`, `account_type`, `slayer_assignment`,
`wilderness_level` (coordinate threshold), `teleblocked` (transient), `all_of` (quantified over a set), `difficulty_state`/`raid_level`.

**Modifiers / tags on atoms (decisions 4, 7, 8):**
- **scope/lifetime** `{permanent | session_transient | location_scoped | time_window}` — *the single highest-leverage
  tag*; prevents false "you can do X permanently" claims (on-task, killcount, teleblock, random-event clocks).
- **subject** `{self | team_sum | team_each | party_size}` — group content.
- **boostable** `{not_boostable | boost_at_acquire | boost_at_use}`.
- **gate_type** on hard `requires` (decision 7): `access | damage | kill` (combat) · `make | craft | smith | cook |
  build | …` (production, structured by recipe `requires`=capability vs `consumes`=resource). Open verb set.
- **game_mode** scope (decision 8): atoms can gate on `game_mode == X` like `account_type`.

**Hard vs soft (decision 4):** `requires` blocks (drives met/blocked); `recommended_for` never blocks (advisory,
strength-tagged). Both use the *full* atom vocabulary — so recommended *combat stats / skill levels* for bosses,
raids, and quest boss-fights (e.g. DS2) are first-class.

---

## 5. The "where" model (decision 1)

Three distinct relations — never conflated:
1. **Containment** — `located_in`, a clean tree (`world ▸ kingdom ▸ city ▸ district ▸ scenery`).
2. **Rule-zones** — `rule_applies_in`, **overlapping** typed overlays, **world-spanning** (multicombat is *not*
   Wilderness-only — it has instances all over: GWD, boss rooms, Castle Wars…). Each instance = a chunk-set.
3. **Coordinates** — **OSRS chunks / chunk-sections** as the unit (matches Region Locker + the cache region grid);
   continuous fields like `wilderness_level` derive from chunk position.

**Worked example (Wilderness teleport-out)** — exercises all three + the atom tags:
`can_teleport_out(method) = wilderness_level ≤ method.max_wildy_level AND NOT teleblocked`
(standard teleports ≤20; glory/seed-pod ≤30; `teleblocked` is a `session_transient` status). Exact per-method levels
are wiki-grounded at ingest.

---

## 6. Identity & aliases (decisions 5, 6)

- **Primary key = cache id** (`item:1383`, `npc:6610`, `scenery:<object_id>`); name-slug kept as an alias. The
  universal join key across cache import / Hiscores / bank export.
- **Item variants** — page-identity + variant children (each cache id), `same_entity`-bridged; reified edges target
  the variant. Prevents over-merge (lost per-variant stats) and over-split (lost "all glory").
- **Aliases** — typed `aliases[] {abbreviation | nickname | former_name}`, **bulk-sourced from wiki redirects**
  (+ a small curated shorthand list). Ambiguous metonyms (`Bandos` = god | boss | room | armour) are **not** forced
  1:1 — resolved at a **search/resolution layer** (alias → ranked candidates by intent); phrase intent ("kill Bandos"
  → the boss) lives in the goal-tracker input parsing. *(The Going Meta "Jaguar Problem".)*

---

## 7. Shared-mechanic & difficulty patterns

- **Shared-mechanic systems** (transport, repair, lyre charges…): one system node owns the base `requires` once;
  each `gives_access`/`served_by`/`connects_to` edge overlays its own gate. Effective req = system-gate ∧ edge-gate.
  Tier-as-capability (canoe reach, spirit-tree count) = a `transport_tier` sub-entity.
- **Difficulty (decision 8 / pass-3)** — a **typed `difficulty_input`** (`binary_flag | scalar_toggle_sum |
  accumulating_draft | floor_index | party_size`, `elected?`) `--scales_with-->` {encounter stat-block/mechanic-set,
  difficulty-CONDITIONAL drop_table atoms (re-rate | unlock-new-rows | route-via-score)}. Variant bosses (Phosani's,
  Corrupted Gauntlet) = sibling nodes sharing a requires-subtree, not a toggle. No new evaluation primitive.

---

## 8. Validation (decision 9 + Going Meta)

- **Domain/range invariant** — generic, schema-driven: every edge's `src.kind ∈ domain` and `dst.kind ∈ range`.
- **Severity tiers** — `VIOLATION` (fail) / `WARNING` (lands tracked) / `INFO`. Partial entity ingestion warns,
  doesn't block.
- **Closed-shape rules** — allowed `data` keys per kind (catches field drift).
- **Competency-questions CI gate** — `kg/competency_questions.json` (question + query + expected shape), run like
  golden tests, **from day one**. Seeded with the Varrock/diary questions.
- **Structural-coverage metrics** — no orphan shop/npc/scenery; provenance-coverage %; containment depth; typed-edge
  vs `data`-blob ratio.
- **Hard guardrails (prior brick lessons):** never fabricate the loot MECHANISM (RDT/GDT) — record flat observable
  rates (Option-A); never parse atoms from the prose "Requirements" blurb — use `Module:Questreq/data`.

---

## 9. Wiki-as-schema mapping (ingestion driver)

| Wiki source | → node/edge |
|---|---|
| cache (OpenRS2 → RuneLite decoder) | node existence + ids + intrinsic attrs (item/npc/scenery/map) |
| Infobox Location / Bucket:Map | `place` (+ chunk geometry, facility flags, coordinate fields) |
| Infobox Monster / Bucket | `monster` (combat stats, weakness, immunities, slayer cat); `aligned_with`→faction |
| Infobox NPC | `npc` (+ role, shop link) |
| Infobox Shop + **Bucket:Storeline** | `shop` + reified `sells`/`accepts` (price, **currency**, stock, restock) |
| Infobox Item / Bucket (item_id ×N + version) | `item` page + **variants**; tradeable/value/alch/weight/buy_limit |
| **Infobox Bonuses / Bucket** | `equipment_bonuses` → `has_bonuses` |
| Infobox Scenery (object_id) + Bucket:Mine | `scenery`; gather-site bindings |
| **Bucket:Dropsline** (~38k) | reified `drops`/`contains` `{rate, rolls, drop_type, version}` |
| **Bucket:Recipe** (~7k) | `recipe` + `consumes`/`requires_facility`/`requires`(skill)/`produces` |
| Infobox Quest + Bucket + **Module:Questreq/data** | `quest` + `requires` DAG (3-state+step, ironman/boostable flags) + `has_part` |
| Module:Combat_Achievements | `combat_achievement` (+ tier points, `tested_on`→monster) |
| Infobox Diary | `diary` region container + tier nodes + `covers`→places |
| Bucket:item_id/npc_id/object_id | `same_entity` id-bridges (the wiki's own link-don't-merge) |
| Transportation/Canoe/Fairy_ring (templates) | `transport_system` + `transport_tier` + `connects_to` cond_groups |
| **wiki redirects** (MediaWiki API) | `aliases[]` (bulk) |

---

## 10. Migration & build sequence

**Migration (link-don't-merge, additive):** existing quests/skills/items/diaries/drops nodes stay; gain `located_in`
+ entity edges; the 261 diary effects re-point onto `sells`/entity targets incrementally. `validate_kg` extended (not
rewritten); byte-stability preserved. The deferred **repo realignment** (refactor-in-place, not greenfield —
`2026-06-24-repo-realignment-note.md`) executes after this lock.

**Build order:**
1. `kg/schema.json` (this spec as data) + the domain/range invariant + severity tiers.
2. Cache node-import (OpenRS2 + RuneLite decoder) → items(+variants)/npcs/scenery/places, cache-id keyed; alias bulk
   from wiki redirects.
3. Edge curation, wiki-table-driven (Storeline/Dropsline/Recipe/Questreq…), Varrock as the template; per-entity
   `source_url` resolver.
4. Competency-questions gate live throughout.

---

## 11. Open micro-items (non-blocking, settle in build)
- `scenery` vs `object` node label (lean `scenery` + `object_id`).
- Exact `place_type` enum + `rule_zone` type enum (extensible).
- `varbit_index` on completion atoms (account-mirror reconciliation) — NICE.
- Geometry fidelity beyond chunks (tile coords/plane) — NICE.

**This ontology is locked. Changes are additive (new kind/edge/atom) via link-don't-merge, never a re-ingest.**
