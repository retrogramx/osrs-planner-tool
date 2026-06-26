# CLAUDE.md — Gilded Tome (OSRS planner on a knowledge graph)

A public, account-type-aware Old School RuneScape **profile + goal/route planner** built on a committed
**knowledge graph**. Evolved from earlier domain "bricks" (quests, diaries, drops, cost/income, account
ingestion) toward a **richly-typed entity graph of all of Gielinor**.

## ⭐ Current direction — v2 ontology LOCKED; item-facet layer BUILT & MERGED; next = the connective vertical.
- **`kg/schema.json`** is the ontology AS DATA (single source of truth; closed vocab + `legacy_*` sections) — the
  contract `validate_kg.py` enforces. Prose spec: `docs/superpowers/specs/2026-06-25-entity-graph-ontology-v2.md`.
- **Done & on `main` (PR #16):** schema-as-data + the **item-facet layer** — item nodes/variants (`same_entity`),
  charge recipes (`recipe`/`consumes`/`produces`), degradation (`degrades_to`), repair (`repairs`), equipment bonuses
  (`equipment_bonuses`/`has_bonuses`). Graph = **658 nodes / 953 edges**. Foundation data audited GREEN (8/8 bricks
  reproduce from committed `data/raw/` snapshots).
- **← NOW: the connective containment vertical.** The graph is a deep item *catalog* but lacks the relational spine —
  `located_in`/`contains`/`operates`/`sells`/`drops` are all still **reserved**. Build the owner's intended model
  (State ▸ Location ▸ NPC ▸ Shop ▸ Item) on the **Varrock worked example** (`data/map/varrock.json` is the template),
  so the planner can answer "where/how do I acquire X" — turning the catalog into a graph of Gielinor.
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
- **Verifiers (source-grounding gates):** `data/verify_*.py` (7: item_families, charge_recipes, degrade_paths,
  repair_paths, equipment_bonuses, diary_rewards, quest_rewards) — check every datum against the wiki snapshot.
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
3. ← **NOW: the connective containment vertical** — `place`/`npc`/`shop` nodes + `located_in`/`contains`/`operates`/
   `sells`(/`drops`) edges, on the Varrock worked example (`data/map/varrock.json`). Account-wide unlocks ride as
   conditional edge-modifiers gated by diary/quest completion (NOT by wearing a regional item).
4. **Then (deferred):** full item-roster scale-up · wield-requirements (`requires` cond_group) · intrinsic attrs
   (value/alch/weight/tradeable) · facility-recharge + the `service` edge (repair fee) · cache-id node-import · aliases.
- The competency-questions gate (`kg/competency_questions.json` + its test runner) stays live throughout.

## Conventions
- Python via `./venv/bin/python` (3.14). Data = committed JSON. Node ids are prefixed: `item:<id>` (wiki-Bucket
  item_id, variant-aware), `equipment_bonuses:<item_id>`, `recipe:<slug>`, `quest:<slug>`, `diary:<region>:<tier>`;
  `place:<slug>`/`npc:<id>`/`shop:<slug>` are next (the containment vertical).
- **Item-`src` edges share ONE rekey:** every item-`src` edge family (`same_entity`+`degrades_to`+`repairs`+
  `has_bonuses`, and future ones) is re-keyed together in `assemble.py` via `rekey(…, edge_index_seed=<prior per-owner
  item-src counts>)` — disjoint per-owner index ranges; a global edge-id-uniqueness assert is the backstop. New
  item-`src` edge from a new builder → seed from prior counts. Builder-local edge-id bands are disjoint (0x10..0xD0).
- **`items_equipment.json` selection trap:** that dataset has MULTIPLE records per item_id (stat-variants + `(beta)`
  page dupes); always select canonical page + `stat_variant_index 0` (see `select_bonus_record`). The slice-5 "errors"
  were a selection bug, not bad data.
- Use subagent-driven-development for multi-task implementation; adversarially verify findings before merging.
- **Status: v2 ontology + item-facet layer MERGED to `main` (PR #16).** New work branches off `main`.
- Licensing seam (non-commercial project): wiki text = CC BY-NC-SA; cache content = Jagex IP; decoder tooling = BSD/ISC.
```
