# World Skeleton — Design (IN PROGRESS)

> **Status:** DESIGN — **brainstorm PAUSED 2026-06-27 for a terminal switch.** Decisions locked below; 3 points are
> interpreted from the owner's "I want to make sure we get everything" steer and need an explicit confirm on resume,
> then the normal user-review gate → writing-plans. Branch: off `main` (slices 1-7 merged). The next connective slice.

## Resume checklist (for the continuing session)
1. Re-read this file + the two source artifacts: `data/map/OSRS Ontology.md` (the owner's SHAPE sketch — incomplete, NOT
   trusted as data) and the current graph's place hierarchy (16 places; `build_map`/`varrock.json` from slice 6).
2. Confirm the 3 "get everything" interpretations in §3 with the owner (ownership move · continent/ocean level ·
   exhaustiveness bound for THIS slice).
3. Finalize this spec, run the spec self-review, get owner review, then invoke `superpowers:writing-plans`.

## 0. Why this slice
The graph's geography stops at `gielinor → misthalin → varrock` (slice 6 skipped the continent/ocean level). This slice
builds the **top-down world backbone** the owner sketched — World ▸ Continents/Oceans ▸ Kingdoms ▸ Capitals — so every
future town hangs off a shared, source-grounded skeleton (and the eventual all-shops scale-up has places to attach to).

## 1. Locked decisions (owner-approved 2026-06-27)
| # | Decision | Choice |
|---|---|---|
| 1 | Scope | **World skeleton ONLY.** All-shops Storeline scale-up is DEFERRED — it's blocked on a shop→location data source (the Storeline bucket has 581 shops + NO location field) and needs district-level places; its own future slice. |
| 2 | Data source | **I (the assistant) draft `data/map/world.json`** (same place-entry shape as `varrock.json`), grounding each place's facts (ruler→`ruled_by`, faction, `source_url`) against its **authoritative wiki page**. `OSRS Ontology.md` is used ONLY as the SHAPE/intent guide — **never copied as trusted data** (owner: "it's just an idea, a lot missing"). **Owner reviews/corrects** the draft (the editorial gate). |
| 3 | Principle | The **shape is editorial** (owner's hierarchy); the **per-place facts are wiki-grounded** (never-fabricate). Governance is best-effort (report-not-fail on unknowns). |

## 2. The design

### Hierarchy + integration (the nuanced part)
Insert the continent/ocean level under Gielinor:
```
place:gielinor (world)
├── place:mainland (continent)
│   ├── place:misthalin (kingdom) ─▶ place:varrock (city)   ← misthalin RE-PARENTED gielinor→mainland
│   ├── place:asgarnia (kingdom)  ─▶ place:falador (city)
│   ├── place:kandarin (kingdom)  ─▶ place:east-ardougne (city)
│   └── … Morytania, Kharidian Desert polities, Wilderness, Tirannwn, Fremennik Province …
├── place:zeah (continent) ─▶ Great Kourend ▸ Kingstown · Varlamore ▸ Civitas illa Fortis …
└── oceans (Northern, Ardent, …) ─▶ island city-states (Miscellania, Etceteria, Lunar Isle, Karamja settlements …)
```
**Two integration moves:**
- **(1) Ownership boundary:** `world.json` becomes the authoritative **backbone — Gielinor down to the city/capital
  level**. The existing `place:gielinor` / `place:misthalin` / `place:varrock` definitions **move from `varrock.json`
  into `world.json`**; `varrock.json` keeps only **within-city** detail (districts, pubs, NPCs, shops, which still
  `located_in place:varrock`). This sets the pattern for every future town: one shared `world.json` + per-town files.
- **(2) Re-parent:** `place:misthalin` `located_in` changes `gielinor` → `mainland`. Net graph effect: the same Varrock
  subtree, plus the inserted continent/ocean level + ~40 new places.

### `world.json` shape + governance
Each place entry: `{id, place_type, name, located_in, ruled_by?, faction?, source_url}` — identical to `varrock.json`'s
places. `place_type` ∈ the schema enum (`world/continent/ocean/island/kingdom/city/town/settlement/...`). Governance is
**data, best-effort** (slice-6 precedent): `Leader:` → `ruled_by` (an `npc:` ref or a plain string), "ruled by X" →
`faction`. `faction` NODES + governance EDGES stay deferred. Opportunistic `same_entity` bridges to the **61 legacy
`region:` nodes** where a place matches by slug (e.g. `place:falador → region:falador`, like slice-6
`place:varrock → region:varrock`).

### Components
- `kg_ingest/builders/world.py` — `build_world(world_data, region_ids) → (nodes, edges, groups={})`: place nodes +
  `located_in` + opportunistic `same_entity`. Edges are place-`src` → its OWN rekey (own band, disjoint from map's
  0xE0/0xD0 and storeline's 0xF0/0xC0 — e.g. edges `0x?` / groups n/a). No sells/operates here.
- `data/verify_world.py` — STRUCTURAL hard-fails: every `located_in` target is a place in the file; exactly ONE root
  (`gielinor`, `located_in: null`); no orphan (every non-root reaches the root); slug uniqueness; place_type ∈ enum.
  **REPORT (not fail):** places missing `ruled_by`/`faction` (best-effort governance); any `source_url` that 404s
  (optional live check, like the `--refresh` pattern).
- `kg_ingest/assemble.py` — wire `build_world` BEFORE the reference collection; `build_world` + `build_map` must
  coordinate so `place:varrock` (now in `world.json`) isn't defined twice (dedup_nodes handles identical defs, but the
  refactor moves the def to ONE place). place-`src` own rekey.
- `data/map/varrock.json` refactor — drop the 3 backbone place defs (gielinor/misthalin/varrock); the districts/pubs
  keep `located_in: place:varrock`. (Owner-reviewed edit.)

### Validation & success criteria
- `assemble` byte-stable; `validate_kg` / `validate_cost` / `verify_world` / `verify_map` / `verify_storeline` exit 0.
- The graph gains ~40-50 place nodes + their `located_in` chain; Varrock's subtree unchanged except the inserted
  continent level (varrock → misthalin → mainland → gielinor).
- Golden + slice-1..7 tests green. New TDD: `build_world` (the hierarchy from a fixture; the re-parent; same_entity
  bridge; single-root); `verify_world` (a dangling located_in fails; a missing ruler reports not fails).
- **+1 competency question:** *"What kingdom and continent is Varrock in?"* → `place:varrock` `located_in`-chain reaches
  `place:misthalin` (kingdom) → `place:mainland` (continent) → `place:gielinor`.

## 3. OPEN — confirm on resume (interpreted from "get everything")
1. **Ownership move** (§2.1): `world.json` owns Gielinor→city backbone (gielinor/misthalin/varrock MOVE out of
   `varrock.json`). Interpreted YES. Alternative: keep them in `varrock.json`, `world.json` only adds the rest (split
   ownership — messier). **Confirm.**
2. **Continent/ocean level** (§2.2): insert it + re-parent Misthalin. Interpreted YES (it's the owner's stated
   top-down vision). Alternative: kingdoms directly under Gielinor (skip continents). **Confirm.**
3. **Exhaustiveness bound for THIS slice:** "everything" = the COMPLETE top-down hierarchy now (all
   continents/oceans/kingdoms/capitals + the named settlements the wiki lists, ~40-60 places), with deeper passes for
   the long tail later — vs literally every minor location in one slice (hundreds, strains draft/review). Interpreted:
   complete-hierarchy-now + staged long-tail. **Confirm the exact bound** (and whether it's one slice or staged).

## 4. Out of scope (named)
All-shops Storeline scale-up (needs shop→location data) · chunk/coordinate geometry · governance EDGES + `faction`/
`deity` nodes · monsters/`drops` · transport/`gives_access` · per-town internal detail beyond Varrock (future per-town
files like `falador.json`).
