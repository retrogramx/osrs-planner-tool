# Knowledge-graph research notes (scratch — NOT a decision)

> Working notes for the eventual `feat/goal-tracker` plan. **Non-binding**; nothing here is
> locked. Captures data-sourcing + modeling ideas for the prerequisite/goal knowledge graph.
> Real decisions move into a plan/ADR when we build the brick.

## Direction (provisional)

- Model the goal/prereq layer as a **knowledge graph**: typed entities (nodes) + typed
  relationships (edges). The "dependency DAG" we've been describing is just the `REQUIRES`
  projection of this graph.
- Two edge classes mirror the **constraint-vs-opinion** split: **facts** (the neutral engine)
  vs **opinion** (the curated/recommended layer). Keep them cleanly separable — for modeling
  *and* licensing (see below).
- Implementation = a data **model**, not a graph DB. Nodes+edges as tables in SQLite→Postgres;
  traverse in Python (e.g. NetworkX). No Neo4j at this scale.

## Entities (nodes) — sources

Catalog to cover: `Skill`, `Quest`, `Item` (+equipment slot), `Monster/Boss`, `Region`,
`Diary(+tier)`, `CombatAchievement(+tier/task)`, `Minigame`, `Spellbook`, `Access/Unlock`,
`CollectionLogSlot`, `AccountType`.

- **RuneProfile `packages/runescape/src`** (`account-types`, `achievement-diaries`,
  `activities`, `collection-log`, `combat-achievements`, `hiscores`, `quests`, `skills`, `xp`)
  — useful as a **completeness CHECKLIST** for progression entities. Caveats: it's
  **TypeScript** (we're Python → re-implement, don't port), **unlicensed**/all-rights-reserved
  (study the shape, re-derive the data — per ADR-0003), and **nodes only, no edges** (no
  prereq/recommended data — that's our build, and our differentiator).
- Authoritative node data: **OSRS Wiki** (MediaWiki API + data Modules) and the **game cache**
  (item IDs/names/slots via OpenRS2 / RuneLite cache dumps — pure game-fact). TempleOSRS / WoM
  also expose item+boss catalogs.

## Edges

- **Facts (neutral engine, unencumbered):** `REQUIRES`, `UNLOCKS`, `DROPS`/`SOURCED_FROM`,
  `GRANTS`, `LOCATED_IN`, `GATED_BY`. The `REQUIRES` projection must stay **acyclic** —
  cycle detection = a QA invariant.
- **Opinion (curated layer):** `RECOMMENDED_FOR` (gear/consumables for a boss/activity), plus
  curated path orderings / edge weights.

## `recommended_for` — source: OSRS Wiki `/Strategies` "Recommended equipment" tables

(e.g. `Scurrius/Strategies#Equipment`.) Richer than it looks — capture **four dimensions**:

- **style** (melee/ranged/magic) × **level bracket** (mid/high) × **slot** × **ranked list**
  (most→least effective).
- **Conditions** via footnotes — e.g. "only with full Void", "best with full Inquisitor's",
  "with full blood moon". ⇒ `RECOMMENDED_FOR` edges need a `condition` field (same
  disjunction/conditional modeling as prereqs).
- **Consumables/inventory** (special-attack weapon, food, prayer/stat pots, runes, teleports,
  rune pouch) — a separate "recommended loadout" dimension, not slot-based.
- **Normalization idea:** mid/high tables are mostly *generic* and reused across bosses →
  model reusable **`GearLoadout`** nodes (`recommended_for` many bosses) instead of duplicating
  per boss.

## Licensing (IMPORTANT — my read, not legal advice)

- **OSRS Wiki content = CC BY-NC-SA 3.0** (Attribution + **NonCommercial** + **ShareAlike**).
- **Facts are not copyrightable** (which items exist, drops, level requirements) → re-derive
  freely, regardless of where observed.
- **Editorial content IS protected** under CC BY-NC-SA — the curated/**ranked**
  recommended-equipment tables and strategy prose are editorial selection/arrangement. Using
  them ⇒ **attribute + non-commercial + share-alike**.
- **RuneProfile = no license** (all-rights-reserved) → study, don't copy.
- **Convergence:** the fact-vs-opinion *modeling* line == the *licensing* line. The neutral
  engine is unencumbered; the opinion layer is where CC BY-NC-SA bites.
- **Implication (public/hosted/maybe-monetized):** keep the opinion layer's data **separable +
  swappable** so you can attribute the wiki, or replace it with self-authored recommendations,
  without touching the engine. NC is *likely fine* for a **free** tool (even if you pay to
  host); it bites if you ever **monetize**. SA means a wiki-derived recommended-gear dataset we
  publish would itself be CC BY-NC-SA.
- **RESOLUTION (2026-06-14):** Adrian will keep the tool **free / non-commercial** and is fine
  open-sourcing → clears **NC** and **SA**. Requirements: (1) stay non-commercial (no ads/sale/
  premium); (2) **attribute** the wiki (credit + link + license notice — *not* waived by being
  free); (3) keep wiki-derived data in a **separate file under CC BY-NC-SA** (SA's viral scope
  stops at that file — the **code stays MIT/Apache**, your choice). Facts stay unencumbered;
  RuneProfile stays study-don't-copy regardless. Respect wiki API etiquette (descriptive
  User-Agent, sane rate). ⇒ **Green light to use the wiki's recommended-gear data.** Minimum is
  narrower than full open-source: non-commercial + attribution + CC-BY-NC-SA on the derived data.

## Open questions (revisit in the `feat/goal-tracker` plan)

- Node/edge schema specifics (tables, IDs, how `condition` is represented).
- Data pipeline: scrape+normalize wiki tables → edges; keep current on game updates; QA
  invariants (acyclic `REQUIRES`, referential integrity, completeness).
- Opinion layer strategy: lean on wiki (attribute + non-commercial) vs author-own vs hybrid.
- How curated "paths / templates" are represented as data over the neutral graph.
