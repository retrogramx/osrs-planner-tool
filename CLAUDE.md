# CLAUDE.md — Gilded Tome (OSRS planner on a knowledge graph)

A public, account-type-aware Old School RuneScape **profile + goal/route planner** built on a committed
**knowledge graph**. Evolved from earlier domain "bricks" (quests, diaries, drops, cost/income, account
ingestion) toward a **richly-typed entity graph of all of Gielinor**.

## ⭐ Current direction — the ontology is LOCKED. Read these first.
- **`docs/superpowers/specs/2026-06-25-entity-graph-ontology-v2.md`** — the locked schema contract: node/edge/atom
  taxonomy, the 9 design decisions, the wiki→edge ingestion map, and the build sequence. Everything builds against this.
- Evidence base (don't re-derive — read): `research/osrs-ontology-nuance-catalog{,-pass2,-pass3}.md` (14 modeling
  patterns + MUST/NICE gaps), `research/goingmeta-kg-learnings.md`, `research/osrs-cache-data-sources.md`.
- Deferred whole-repo cleanup (refactor-in-place, NOT greenfield): `docs/superpowers/plans/2026-06-24-repo-realignment-note.md`.

## Architecture (deterministic data pipeline)
`data/*.json` (source-grounded data) → `kg_ingest/builders/*.py` (per-domain builders) → `kg_ingest/assemble.py`
→ committed **`kg/{nodes,edges,condition_groups}.json`** (the graph).
- **Engine:** `src/osrs_planner/engine/kg/` — `model.py` (NodeKind/EdgeType/AtomType), `store.py`/`json_store.py`,
  `conditions.py`. The `requires` + condition-atom (AND/OR/NOT) evaluator is the spine — reused for quests, diaries,
  transport, shops, recipes, combat, difficulty.
- **Validators (structural/graph invariants):** `data/validate_kg.py`, `data/validate_*.py`.
- **Verifiers (source-grounding gates):** `data/verify_*.py` — check every datum against the wiki snapshot.
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

## Next: build sequence (per v2 spec §10)
1. **`kg/schema.json`** (this spec as machine-readable data) + a generic **domain/range invariant** + **severity
   tiers** (VIOLATION/WARNING/INFO) in `validate_kg.py`. ← start here.
2. **Cache node-import:** OpenRS2 cache → RuneLite `net.runelite.cache` decoder → items(+variants)/npcs/scenery/
   places, **cache-id-keyed**; bulk `aliases` from wiki redirects.
3. **Edge curation**, wiki-table-driven (Storeline/Dropsline/Recipe/Questreq…); `data/map/varrock.json` is the
   edge-authoring template; per-entity `source_url` resolver.
4. **Competency-questions CI gate** (`kg/competency_questions.json`) live throughout.

## Conventions
- Python via `./venv/bin/python` (3.14). Data = committed JSON. Node ids are prefixed: `item:<cache_id>`,
  `npc:<id>`, `scenery:<object_id>`, `place:<slug>`, `quest:<slug>`, `diary:<region>:<tier>`.
- Use subagent-driven-development for multi-task implementation; adversarially verify findings before merging.
- Branch: the entity-graph work is on `feat/achievement-diaries` (diary brick complete; entity layer + cleanup pending).
- Licensing seam (non-commercial project): wiki text = CC BY-NC-SA; cache content = Jagex IP; decoder tooling = BSD/ISC.
```
