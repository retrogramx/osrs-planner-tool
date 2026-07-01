# CLAUDE.md — Gilded Tome (OSRS planner on a knowledge graph)

A public, account-type-aware Old School RuneScape **profile + goal/route planner** built on a committed
**knowledge graph**. Evolved from earlier domain "bricks" (quests, diaries, drops, cost/income, account
ingestion) toward a **richly-typed entity graph of all of Gielinor**.

## ⭐ Current direction — v2 ontology + item-facet + location spine + FOUR bottom-up layers (shops · NPC operators · facilities · recipes incl. all-makeable) all MERGED; next = recipe-id STABILITY, then the remaining objects/resources halves.
- **`kg/schema.json`** is the ontology AS DATA (single source of truth; closed vocab + `legacy_*` sections) — the
  contract `validate_kg.py` enforces. Prose spec: `docs/superpowers/specs/2026-06-25-entity-graph-ontology-v2.md`.
- **Done & on `main`:** (PR #16) schema-as-data + the **item-facet layer** (item nodes/variants `same_entity`, charge
  `recipe`s, `degrades_to`, `repairs`, equipment `has_bonuses`); (PR #17) the **connective Varrock spine** (`place`/`npc`/
  `shop` + `located_in`/`operates`/`sells`) + source-grounded Storeline shop stock; (PR #19) the **world skeleton** — a
  comprehensive LOCATION GRAPH (16→726 place nodes built from the wiki TYPE-CATEGORY union via `build_world`, + a committed
  coverage verifier); (PR #20) the **re-homing pass** — every place attached to its parent (190 unparented → **11** disclosed
  floor) via a precision-first 5-rung `parent_for` signal stack (`override→category→name-suffix→infobox→FLAG`,
  content-places-as-parents) + an `is_excluded` noise filter + a new infobox-`location` brick + 24 owner-reviewed
  `world.json` backbone places + `world_parenting.json` overrides + a committed-graph acyclicity gate (`_resolve_reachable`,
  enforced in `verify_world` AND `validate_kg`); (PR #21) the **all-shops layer** — every `Bucket:Storeline` shop (568
  derived + 15 Varrock) as a `shop:` node parented `located_in` the skeleton via a new shop-infobox brick
  (`fetch_shop_infoboxes.py`; `shop_type` from the infobox **`icon`**, NOT categories — the fine "X shops" categories
  don't exist on the wiki), item-only `sells` (currency deferred — §Conventions), `verify_shops` + `verify_shop_coverage`;
  (PR #23) the **NPC operator layer** — every shop operator (~423, from the shop brick's `owner` field) as an `npc:` node
  parented via a new npc-infobox brick (`fetch_npc_infoboxes.py`; the brick is the NPC filter — no `{{Infobox NPC}}` →
  not a node), with `operates` edges (closing the shop layer's deferred operators) — and the 14 multi-location shops
  RESOLVED via operators (the 13 Slayer-Rewards masters each `located_in` its place; `role` unset, `operates`-edge-only,
  NO role node), `verify_npcs` + `verify_npc_coverage`;
  (PR #24) the **facility taxonomy layer** (objects/resources slice 1) — 255 `facility:` nodes from `Bucket:recipe.uses_facility`,
  skill-tagged from `uses_skill`, ZERO edges (pure roster; capabilities don't place), via an infobox-presence filter
  (Scenery/Construction→facility; NPC/Shop→defer) + redirect-aware canonical dedup + owner `facility_overrides.json`;
  (PR #25 + all-makeable ff `e60818e`) the **recipe layer** — **4548 reified `recipe:` nodes** from `Bucket:recipe`:
  `consumes`(material/tool)/`produces`/**`requires_facility`**(→ the facilities)/`requires`(skill_level), xp per-skill dict,
  per-method-row. Slice 1 = 6 core production skills; **slice 2 (all-makeable) = output-based** (every resolvable-output row,
  incl. **1832 no-skill combinations** — no `requires`/no `xp`), `verify_recipes` + `verify_recipe_coverage`.
  Graph = **15114 nodes / 30136 edges** (item roster ~5900 via auto-import). Foundation audited GREEN (8/8 bricks reproduce from `data/raw/`).
- **← NOW: recipe-id STABILITY** (its own slice — spec/plan TBD). Recipe ids aren't stable addresses: the slug scheme
  disambiguates only when-needed, so adding rows silently re-keys built recipes (19 re-slugged at the all-makeable merge),
  and **~816/4548 (17.9%) recipe ids are order-dependent `-k` collision guards** (Bucket row-order dependent; byte-stable
  only given the committed snapshot). Fix = an intrinsic content-addressed slug + a `validate_kg` stability invariant across
  both layers (brainstorm the mechanism: content-hash vs frozen readable-map). **Then the remaining objects/resources halves:**
  gather sites (blocked on a yield source-hunt — `Bucket:Mine` empty — + chunk geometry) · farming patches (own slice) ·
  transport (nodes + `gives_access`) · placed facilities (banks/altars/GE `located_in`). (Broader NON-operator NPCs — skill
  tutors, slayer-masters-as-a-role, bankers, quest-givers — are DEFERRED: not category-sourceable on the wiki, need their
  own source-hunt.)
  Each from its OWN structured wiki source + its own coverage verifier; each layer's `located_in` is a completeness
  CROSS-CHECK on the skeleton — and reuses the skeleton's `parent_for` machinery (`world_parenting.json` is the
  owner-override escape hatch). Roadmap: `docs/superpowers/specs/2026-06-27-world-skeleton-design.md` §7.
- Evidence base (don't re-derive — read): `research/osrs-ontology-nuance-catalog{,-pass2,-pass3}.md`,
  `research/goingmeta-kg-learnings.md`. Deferred whole-repo cleanup: `docs/superpowers/plans/2026-06-24-repo-realignment-note.md`.

## Architecture (deterministic data pipeline)
`data/*.json` (source-grounded data) → `kg_ingest/builders/*.py` (per-domain builders) → `kg_ingest/assemble.py`
→ committed **`kg/{nodes,edges,condition_groups}.json`** (the graph).
- **Graph model:** `src/osrs_planner/engine/kg/` — `model.py` (NodeKind/EdgeType/AtomType + ConditionAtom/Group),
  `store.py`/`json_store.py` (KGStore).
- **Evaluator (the spine):** `src/osrs_planner/engine/` — `conditions.py` (`atom_satisfied`/`evaluate`),
  `state.py` (AccountState), `kleene.py` (three-valued `Tri`), `engine.py`, `cards.py`. Evaluates a `requires`
  cond_group (AND/OR/NOT) against AccountState → met/blocked/unknown; reused for quests, diaries, transport, shops,
  recipes, combat, difficulty. The entity-graph build reuses this — don't reinvent it.
- **Validators (structural/graph invariants):** `data/validate_kg.py`, `data/validate_*.py`.
- **Verifiers (source-grounding gates):** `data/verify_*.py` — check every datum against the wiki snapshot:
  item_families, charge_recipes, degrade_paths, repair_paths, equipment_bonuses, diary_rewards, quest_rewards, map,
  storeline, world, and **world_coverage** (the completeness gate — `have N/total` per IN-category, `--refresh` for
  live drift). Structural violations hard-fail; resolution/coverage residuals are REPORTED (exit 0).
- **Foundation reproducibility:** every brick commits its raw canonical snapshot (`data/raw/`) + a deterministic
  parser, so the committed JSON is re-derivable; `data/audit_quest_requirements.py` is the reproduce+freshness pattern.
- **Account mirror:** `src/osrs_planner/` (hiscores, profile, account detect).

## Commands (always use the venv)
```
./venv/bin/python -m kg_ingest.assemble                          # rebuild kg/*.json — MUST be byte-stable (re-run = identical bytes)
./venv/bin/python data/validate_kg.py                            # graph invariants
./venv/bin/python data/verify_diary_rewards.py                   # a source-grounding gate (pattern for others)
./venv/bin/python -m pytest -q --continue-on-collection-errors   # tests (the 4 tests/drop_rates/ collection errors are pre-existing & unrelated)
```

## Non-negotiable disciplines
- **Never fabricate.** Every datum traces to the OSRS wiki — cite `source_url` + a **verbatim** `source_token`. A
  rule isn't enforced until a committed validator checks the data; fix at the class level, disclose residuals.
- **Byte-stable assemble** + committed validators + golden tests stay green. Verify before claiming done (run it).
- **Source data from the wiki's STRUCTURED layer, not prose:** Bucket/Cargo tables + `Module:` data. Quest/diary
  requirement atoms come from `Module:Questreq/data`, NOT the prose "Requirements" blurb. Record drops **flat**
  (Option-A) — never fabricate the loot mechanism (RDT/GDT vs direct vs on-task).
- **Schema-as-data + link-don't-merge:** the entity layer is additive; bridge new↔existing nodes with `same_entity`.
  Schema changes are additive (new kind/edge/atom), **never a re-ingest**.
- **Planner never auto-blocks / never auto-picks:** hard `requires` vs soft `recommended_for`; surface routes as
  choices (efficiency-vs-fun). Output is objective/terse, data-first.
- **Editorial review by the owner is a hard human gate** for facts a validator can't check.

## Build sequence — where we are
1. ✅ **`kg/schema.json`** (ontology-as-data) + schema-driven domain/range invariant + severity tiers
   (VIOLATION/WARNING/INFO) in `validate_kg.py`.
2. ✅ **Item-facet layer** (slices 1–5, all item-`src` edges): variants/`same_entity`, charge `recipe`s, `degrades_to`,
   `repairs`, `has_bonuses`. Built Wiki-Bucket-first (NOT cache); each slice TDD'd via subagent-driven-development with a
   per-task review + opus whole-branch review + a source-grounding verifier + a competency question.
3. ✅ **Connective spine + location skeleton** (slices 6–8): `place`/`npc`/`shop` + `located_in`/`operates`/`sells` on
   the Varrock worked example (PR #17, `data/map/varrock.json`); then the **world skeleton** (PR #19) — a comprehensive
   location graph from the wiki TYPE-CATEGORY union (`build_world` + owner-reviewed `data/map/world.json` backbone + a
   coverage verifier). New place_types `sea` + `point_of_interest`; `members` flag; two-level typing (`place_type` coarse,
   `content_kind` advisory). Account-wide unlocks ride as conditional edge-modifiers gated by diary/quest completion.
   Then **re-homing** (PR #20): `parent_for` signal stack + `world_parenting.json` + acyclicity gate, residual → 11.
4. **The bottom-up layers** — shops ✅ (PR #21, `build_shops`) · NPC operators ✅ (PR #23, `build_npcs` +
   `fetch_npc_infoboxes.py`; operates + multi-location resolution) · facility taxonomy ✅ (PR #24, `build_facilities`,
   pure roster) · recipes ✅ (PR #25 core skills + all-makeable ff `e60818e`, `build_recipe_roster`, 4548 nodes wiring
   `requires_facility` → the facilities). ← **NOW: recipe-id STABILITY** (intrinsic content-addressed slug + a
   `validate_kg` invariant; ~816 recipe ids are order-dependent — its own slice). **Then still open:** gather sites
   (blocked — yield source-hunt + chunk geometry) · farming patches · transport (`gives_access`) · placed facilities
   (banks/altars/GE `located_in`), each `located_in` the skeleton + its own structured source + coverage verifier.
5. **Then (deferred):** full item-roster scale-up · wield-requirements (`requires` cond_group) · intrinsic attrs
   (value/alch/weight/tradeable) · facility-recharge + the `service` edge (repair fee) · chunk geometry · governance
   edges + `faction` nodes · cache-id node-import · aliases.
- The competency-questions gate (`kg/competency_questions.json` + its test runner) stays live throughout.

## Conventions
- Python via `./venv/bin/python` (3.14). Data = committed JSON. Node ids are prefixed: `item:<id>` (wiki-Bucket
  item_id, variant-aware), `equipment_bonuses:<item_id>`, `recipe:<slug>`, `quest:<slug>`, `diary:<region>:<tier>`,
  `place:<slug>`, `npc:<id>`, `shop:<slug>`.
- **Per-`src`-class edges share ONE seeded rekey:** each edge owner-class (item-`src`: `same_entity`/`degrades_to`/
  `repairs`/`has_bonuses`; place/npc/shop-`src`: `located_in`/`operates`/`sells`/`same_entity`) is re-keyed in
  `assemble.py` via `rekey(…, edge_index_seed=<prior per-owner counts>)` — disjoint per-owner ranges; a global
  edge-id-uniqueness assert is the backstop. When an owner SPANS builders (build_world → build_map → build_storeline),
  each later rekey SEEDS from prior counts. Builder-local edge-id bands are disjoint (item 0x10..0xD0; place-`src`:
  build_world 0xB0 / build_map 0xE0 / build_storeline 0xF0).
- **Edge-id id-space (`stable_edge_id`/`stable_group_id`):** `SPAN = 1<<48`, `GROUP_OFFSET = 1<<49`, `EDGE_OFFSET = 1<<50`
  — disjoint group/edge domains, both < 2^53 (JS-safe). sha1-mod-`SPAN` collisions are negligible at any realistic graph
  size; `rekey` still fail-fasts on one (the committed-graph edge-id-uniqueness assert proves the live graph is clean).
  ALL edges (incl. shops) go through the one seeded `rekey` — the old `SPAN=2M` ceiling + the PR #21 shop sequential band
  were retired by widening `SPAN` (a one-time renumber; spec `docs/superpowers/specs/2026-06-29-edge-id-span-widen-design.md`).
- **`items_equipment.json` selection trap:** that dataset has MULTIPLE records per item_id (stat-variants + `(beta)`
  page dupes); select canonical page + `stat_variant_index 0`, EXCEPT demote an all-zero index-0 record so a non-zero
  ACTIVE variant wins (`_all_zero_stats` in `select_bonus_record`; the Crystal-shield inactive-form case, refined in PR
  #21). The slice-5 "errors" were a selection bug, not bad data. **Gotcha: wiring a layer that references many items
  AUTO-IMPORTS them, which can surface latent bugs in OTHER bricks** (shops → equipment_bonuses; fix the root brick).
- Use subagent-driven-development for multi-task implementation; adversarially verify findings before merging.
- **Re-homing/parenting gotcha:** adding a parenting SIGNAL (or new parent place) can silently re-parent ALREADY-homed
  nodes, not just the unparented — **diff the `located_in` edges before/after, not just the residual count** (caught two
  precedence bugs this way in PR #20). `parent_for` = precision-first rungs with backbone-preference PER RUNG (a content
  category beats a backbone infobox). The committed place graph must stay acyclic & single-rooted at `place:gielinor`
  (now a `validate_kg` hard-fail, not just `verify_world`).
- **Status: item-facet + connective Varrock + world skeleton + re-homing + all-shops + NPC-operators + facility-taxonomy +
  recipes (core + all-makeable) layers + the edge-id SPAN widen MERGED to `main` (PRs #16/#17/#19/#20/#21/#22/#23/#24/#25 +
  all-makeable ff `e60818e`); graph 15114 nodes / 30136 edges. Residuals (disclosed, report-not-fail): world-skeleton
  parenting = 11; shops = 357 parented / 14 multi-loc / 197 FLAG (50+103+44); NPC operators = 357 located_in / 19 multi-loc /
  47 location-unresolved + 6 Varrock-overlap (build_map owns them); recipes = coverage 660 distinct unresolvable outputs /
  834 rows skipped (Construction/Sailing scenery → future scenery layer), 77 unresolved materials, 82 unresolved facilities
  (mostly operator NPCs, not facilities). Known deviation: 19 slice-1 recipe ids re-slugged at the all-makeable merge
  (payloads preserved) — recipe-id STABILITY is the NOW slice (~816 order-dependent ids). The 44 shop + 47 npc
  location-unresolved OVERLAP = the place-layer backfill to-do (missing skeleton places + name-norm).** New work branches off `main`.
- Licensing seam (non-commercial project): wiki text = CC BY-NC-SA; cache content = Jagex IP; decoder tooling = BSD/ISC.
```
