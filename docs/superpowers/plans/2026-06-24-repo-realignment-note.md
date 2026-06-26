# Repo Realignment — Cleanup Note (deferred until the ontology is locked)

> **Trigger:** owner request (2026-06-24) — once the entity-graph ontology is locked, go back over
> the WHOLE repo file-by-file and realign it to the new direction: rewrite or delete anything
> outdated / not aligned with the "comprehensive Gielinor entity graph" goal.

## Decision: refactor-in-place, NOT greenfield (rationale)

Greenfield was considered and **rejected**:
- The core MACHINERY directly serves the new direction and is hard to rebuild: `data → builders →
  assemble → committed kg/*.json` pipeline, committed validators, byte-stable assemble, source-grounding
  verifiers, and the `requires`+condition-atom **engine** (which already powers the transport/requirement
  reasoning the entity graph needs).
- The new direction is **additive** (link-don't-merge): the entity layer extends the existing graph;
  quests/skills/items/diaries/drops migrate in as nodes. Not a replacement → not a rewrite.
- The DATA is the expensive part and it migrates — thousands of source-grounded, validated facts, with
  hard-won lessons encoded in the validators (Tokkul trap, RDT-can't-be-tagged, iron-gate leaks). Greenfield
  = re-ground everything + reintroduce caught bugs. Second-system trap: months to return to parity.
- Planning is NOT fully done (ontology unlocked) → greenfield now would be rewriting against a moving schema.

## What "cleanup" concretely means (when we get there)
1. **Prune curriculum-era cruft** — the hand-learning chapters / FastAPI/pydantic scaffolding that produced
   the original code but no longer serves Gilded Tome.
2. **Delete superseded approaches** — e.g. the diary effects' flat content-node anchors get re-pointed onto
   the entity graph (sells/located_in/etc.), not kept as-is; any dead scenarios/demos.
3. **Migrate each domain onto the ontology** — quests, skills, items, diaries, drops, cost/income, account
   ingestion → expressed against the committed `kg/schema.json`, bridged via `same_entity` where needed.
4. **Keep + extend** — the pipeline, validators (add domain/range + severity tiers), engine, account mirror.
5. **Adopt cache ids as canonical** (per [[project_kg_entity_hierarchy_model]] / research/osrs-cache-data-sources.md).

## Sequencing (do NOT start until these are done)
1. Nuance survey (wiki-schema mining + diverse-sample hunt) → pattern catalog + gap list.
2. Lock the ontology (A1–F1 + any new decisions the survey surfaces).
3. THEN: this repo-wide cleanup/migration + cache node-import + edge curation.

This note exists so the cleanup intent + the greenfield-rejected decision survive a fresh
clone/session. It is a reminder, not a plan to execute yet.
