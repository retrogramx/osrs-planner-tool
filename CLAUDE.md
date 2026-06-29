# CLAUDE.md — Gilded Tome (OSRS planner on a knowledge graph)

A public, account-type-aware Old School RuneScape **profile + goal/route planner** built on a committed
**knowledge graph**. Evolved from earlier domain "bricks" (quests, diaries, drops, cost/income, account
ingestion) toward a **richly-typed entity graph of all of Gielinor**.

## ⭐ Current direction — v2 ontology + item-facet + the connective/location spine all MERGED; next = the bottom-up layers.
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
  enforced in `verify_world` AND `validate_kg`). Graph = **1603 nodes / 1943 edges**. Foundation audited GREEN (8/8 bricks reproduce from `data/raw/`).
- **← NOW: the bottom-up layers (what attaches to the location skeleton).** The in-game `Map_icon` legend is the
  authoritative roadmap: shops (all-shops Storeline scale-up) · NPCs/tutors · objects/resources (training spots) ·
  transport (nodes + `gives_access`, built together) · facilities (banks/altars/GE). Each from its OWN structured wiki
  source + its own coverage verifier; each layer's `located_in` is a completeness CROSS-CHECK on the skeleton — and reuses
  the skeleton's `parent_for` parenting machinery (`world_parenting.json` is the owner-override escape hatch). Roadmap:
  `docs/superpowers/specs/2026-06-27-world-skeleton-design.md` §7.
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
4. ← **NOW: the bottom-up layers** — shops (all-shops scale-up) · NPCs · objects/resources · transport (`gives_access`) ·
   facilities, each `located_in` the skeleton + its own structured source + coverage verifier.
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
- **`items_equipment.json` selection trap:** that dataset has MULTIPLE records per item_id (stat-variants + `(beta)`
  page dupes); always select canonical page + `stat_variant_index 0` (see `select_bonus_record`). The slice-5 "errors"
  were a selection bug, not bad data.
- Use subagent-driven-development for multi-task implementation; adversarially verify findings before merging.
- **Re-homing/parenting gotcha:** adding a parenting SIGNAL (or new parent place) can silently re-parent ALREADY-homed
  nodes, not just the unparented — **diff the `located_in` edges before/after, not just the residual count** (caught two
  precedence bugs this way in PR #20). `parent_for` = precision-first rungs with backbone-preference PER RUNG (a content
  category beats a backbone infobox). The committed place graph must stay acyclic & single-rooted at `place:gielinor`
  (now a `validate_kg` hard-fail, not just `verify_world`).
- **Status: item-facet + connective Varrock + world skeleton + re-homing MERGED to `main` (PRs #16/#17/#19/#20); graph
  1603 nodes / 1943 edges; world-skeleton parenting residual = 11 (disclosed floor, report-not-fail).** New work branches off `main`.
- Licensing seam (non-commercial project): wiki text = CC BY-NC-SA; cache content = Jagex IP; decoder tooling = BSD/ISC.
```
