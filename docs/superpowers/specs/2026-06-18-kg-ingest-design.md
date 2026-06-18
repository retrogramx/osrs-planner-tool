# feat/kg-ingest — design

**Status:** Design (brainstormed 2026-06-18). Next: implementation plan (writing-plans) → subagent-driven build.

**Goal:** Build the data pipeline that turns the merged `data/*.json` datasets into the real knowledge graph
(`node` / `edge` / `condition_group` / `condition_atom` per `research/kg-schema-v1.md`) that the goal-engine's
`KGStore` loads — so the engine answers **real accounts** instead of a hand-authored fixture.

**Architecture (one line):** per-domain **builders** transform the structured `data/*.json` into committed,
inspectable `kg/*.json`; a thin **`JsonKGStore`** loads that into the existing engine; a **`validate_kg.py`**
guard enforces graph invariants — mirroring the existing `data/` committed-builder + `validate_iron_gate.py`
pattern.

---

## 1. Scope

**This is a thin vertical slice** — the smallest pipeline that makes the engine produce correct
`is_unlocked` / `prereqs_for` / `next_steps` answers on real data.

**In scope (v1):**
- **The full quest graph, type-aware.** `data/quests.json` holds 213 records = **177 `quest` + 28 `miniquest`
  + 8 `diary`** (it's a *requirements* feed — `Module:Questreq/data` — so it bundles all three). Ingest **respects
  `node_type`**: quests + miniquests become gate nodes; **RFD subquests stay granular** (11 RFD entries: parent +
  10 subquests, each with its own reqs); the **8 stray `diary` records are routed to diary handling** (and flagged
  by the validator as mis-filed). Each quest/miniquest → a node + its `prereqs`/`skill_reqs` as condition trees.
- **A 6-goal v1 set** (see §3) covering the distinct acquisition patterns; the remaining goals are deferred to a
  quick mechanical follow-up.
- **Committed KG output** (`kg/nodes.json`, `kg/edges.json`, `kg/condition_groups.json`) + a `JsonKGStore`
  loader + `validate_kg.py`.
- **One small engine addition:** account-**family-aware** `account_type` evaluation (see §6.4).

**Out of scope (deferred, explicitly):**
- The **currency / acquisition-cost dimension** (`research/currency-model.md`) — the next brick.
- The **full 4,298-item catalog** — only goal-relevant items are ingested in v1.
- **SQL / Postgres persistence** — v1 ships JSON + `InMemoryKGStore`-shaped loading; SQL arrives with hosting.
- **`expand_for_account`** (buy-vs-gather acquisition), `compare_goals`, `suggest_goals`, mutations, the **advisor**.
- **GE-price caching**, boost-source database (the boost *suggestion* — see §6.5).
- A **`clog_slot` condition atom** — the collection-log dimension (see §3, Castle Wars clogs).

---

## 2. Input data (already structured — ingest is a transform, not extraction)

Each `data/*.json` is `{_provenance, records, _excluded}`. The records carry parsed requirement structures:

- **`quests.json`** (213): `{name, node_type, prereqs:[{quest, stage}], skill_reqs:[{skill, level, boostable, ironman}]}`.
- **`items_equipment.json`** (4,298): `{item_id, item, slot, members, requirements:{skills, quests}, tradeable,
  ge_value, high_alch, ...}`.
- **`achievement_diaries.json`**, **`combat_achievements.json`**, **`minigames.json`** (93),
  **`unlocks_transport.json`** (107), **`bosses_pvm.json`**, **`collection_log.json`** — domain requirement
  structures used as needed for the goal set.

Because requirements are already parsed into fields (not raw wiki text), the builders are **deterministic
transforms**. The hard part is modeling decisions (§6), not parsing.

---

## 3. The goal set

The v1 KG = the full quest graph + the nodes/edges/conditions for the **6-goal v1 set**. Exact requirements are
**wiki-verified at build time** (per the project's sourcing rule) and encoded from the datasets where present.

**v1 goal set (6 — chosen to cover the distinct acquisition patterns):**

| Goal | Pattern it proves |
|---|---|
| **Dragon scimitar** | tradeable buy — GE (main) vs NPC-shop (iron) **divergence** |
| **Barrows gloves** | untradeable reward-shop + the deep **Recipe for Disaster** chain (**convergence**) |
| **Fairy rings** | **in-progress** quest gate (access unlock) |
| **TzHaar-ket-om (obby maul)** | Tokkul currency + tradeable **divergence** + a pure-build wield gate (60 Str) |
| **Full Infinity** | **multi-piece gear set** (`gear_loadout`) |
| **Voidwaker** | **multi-component assembly** (own 3 boss-drop pieces → combine) |

**Deferred to a quick follow-up (mechanical once the v1 patterns work):** Twisted bow (raid unique),
Toxic staff of the dead (combine + Zulrah), Master wand (MTA Pizazz currency), Abyssal whip (tradeable Slayer
drop), Quest cape (requires all quests — a whole-graph stress test), Karamja gloves (achievement-diary reward),
Rune scimitar (early-game low-req), Fighter torso (Honour-point currency), Mage Arena 2 cape (activity reward).

**Documented gap (deferred future feature, NOT modeled in v1):**
- **Castle Wars clogs / collection-log goals** — these need a **`clog_slot` condition atom**, which is not in the
  locked atom vocabulary (`clog_slot` is a `NodeKind` only). v1 does **not** attempt them; the spec records that
  the collection-log feature requires a new atom — its own future feature (with the completionist lens).

---

## 4. Architecture & components (Approach A)

```
data/*.json (committed, structured)
   │
   ▼   kg_ingest/builders/        per-domain deterministic transforms
        ├─ build_quests()         quests → quest nodes + requires-edges + condition trees
        ├─ build_goals()          the §3 goal items/access/minigame/gear-set nodes + their conditions
        └─ build_supporting()     skill / item / access / monster / minigame nodes referenced by atoms
   │
   ▼   kg_ingest/assemble.py      merge builder output, assign stable ids, dedup nodes
        └─ writes  kg/nodes.json · kg/edges.json · kg/condition_groups.json   (committed, diffable)
   │
   ├─▶ src/osrs_planner/engine/kg/json_store.py : JsonKGStore(KGStore)
   │     loads kg/*.json into engine Node/Edge/ConditionGroup/ConditionAtom; same interface InMemoryKGStore uses
   │
   └─▶ data/validate_kg.py        invariant gate (run in CI / pre-merge, like validate_iron_gate.py)
```

**Component responsibilities (each independently testable):**
- **Builders** (`kg_ingest/builders/*.py`) — pure functions: `(domain records) → (nodes, edges, condition_groups)`.
  One per source domain; `build_quests()` first.
- **Assembler** (`kg_ingest/assemble.py`) — merges builder outputs, enforces stable IDs (§6.6), dedups shared
  nodes (a skill referenced by many quests = one node), writes the three `kg/*.json` files.
- **`JsonKGStore`** (`engine/kg/json_store.py`) — the *only* engine code added: implements the existing `KGStore`
  interface by deserializing `kg/*.json` into the engine's dataclasses. Engine logic untouched.
- **`validate_kg.py`** — the guard (§7).

---

## 5. Output format (`kg/*.json`)

Serialized forms of the engine's existing types (so `JsonKGStore` is a thin deserializer):

```jsonc
// kg/nodes.json
[ { "id": "quest:dragon-slayer-i", "kind": "quest", "name": "Dragon Slayer I",
    "slug": "dragon-slayer-i", "data": {} }, ... ]

// kg/condition_groups.json   (children: int sub-group id | inline atom object — per engine D2)
[ { "id": 4012, "op": "and", "parent": null,
    "children": [
      { "atom_type": "skill_level", "ref_node": "skill:agility", "threshold": 25,
        "data": { "boostable": true } },
      4013   // sub-group id
    ] }, ... ]

// kg/edges.json
[ { "id": 7001, "type": "requires", "src": "quest:monkey-madness-i", "dst": null,
    "cond_group": 4012 }, ... ]
```

IDs for groups/edges are integers assigned by the assembler (stable across rebuilds via a deterministic scheme:
hash of the owning node id + a domain offset — documented in the plan so rebuilds don't churn).

---

## 6. Modeling decisions

### 6.1 Quest → KG mapping
Each quest = one `quest` node. Its requirements = one `requires` edge (`dst=null`) whose `cond_group` is an
`AND` of:
- one `quest` atom per `prereqs` entry — `ref_node = quest:<slug>`, `data.state` from the prereq `stage`
  (`completed`; `in_progress`/`started` mapped to the locked 3-state enum), and
- one `skill_level` atom per `skill_reqs` entry — `ref_node = skill:<slug>`, `threshold = level`,
  `data.boostable` carried (§6.5), and account-family-conditional wrapping when `ironman: true` (§6.3).

### 6.2 Item / access / gear-set goals
- A wieldable item = an `item` node; "wielding it" = an `AND` of an `item` possession atom + the item's
  `requirements` (skill_level / quest atoms from `items_equipment.requirements`).
- A **gear set** (full Infinity) = a `gear_loadout` node whose composition `cond_group` is the `AND`/`OR` of its
  piece `item` atoms — reusing the engine's existing `gear_loadout` mechanic.
- **Multi-component assembly** (Voidwaker, Toxic staff of the dead) = the assembled `item` node requires an
  `AND` of its component `item` possession atoms. (Acquiring each component — drop vs GE — is the deferred cost
  layer; the *requirement* "own the components" models cleanly now.)
- **An "all quests" goal** (Quest cape) = a node whose `requires` cond_group is an `AND` of `quest` atoms
  (`state=completed`) over the full quest list — generated by the builder from the quest set, not hand-listed.

### 6.3 The `ironman` flag → account-family-conditional requirement
A requirement flagged `ironman: true` applies only to accounts that must self-source. Model it as:
> `OR( NOT(account_type == "ironman"),  <the requirement> )`

- A **main** → `NOT(account_type=="ironman")` is TRUE → the `OR` is satisfied → the requirement is **invisible**
  to mains (honors the "never explain a main's restrictions to them" rule).
- An **iron-family** account → reduces to the real requirement.

This reuses existing atoms + `OR`/`NOT` operators. `account_type == "ironman"` here is a **family** test (§6.4).

### 6.4 Account families (the one engine addition)
The `account_type` atom is currently a literal `state.mode == value`. v1 makes it **family-aware** so the §6.3
wrapper covers **all** iron variants:
- Add `account_family(mode) -> str` to `engine/state.py` mapping specific modes to the contract's families:
  `main`; `ironman` (standard ironman + **HCIM, GIM, HCGIM** ride here); `uim` (Ultimate).
- The `account_type` atom: when its target value is a **family name** (`main`/`ironman`/`uim`), it matches via
  `account_family(state.mode)`; when the target is a **specific mode**, it matches `mode` exactly. (Both forms
  supported; the §6.3 wrapper uses the family form.)
- This is the only change to engine logic; it is small, localized to the `account_type` branch + a state helper,
  and justified by multi-account-type being a core product pillar (ADR-0004). All existing engine tests stay green.

**Deferred edge cases (noted, not handled in v1):** GIM intra-group trading (a group-mate could supply an item),
and UIM's no-bank constraint (affects item *storage/strategy*, not whether a requirement is met).

### 6.5 The `boostable` flag (carry + surface)
Every `skill_level` atom carries `data.boostable` from the source. The engine's verdict stays strict (you must
currently meet the level → otherwise a blocker), but the blocker is **annotated `boostable`** so a later advisor
can suggest "drink/eat a boost instead of grinding." The **boost-source database + the suggestion** are the
deferred advisor feature; v1 only **preserves and surfaces the flag** (no re-ingest needed later).

### 6.6 IDs
Stable, slug/id-based per `research/kg-schema-v1.md`: `quest:<slug>`, `skill:<slug>`, `item:<item_id>`,
`access:<slug>`, `npc:<id>`, `gear_loadout:<slug>`, `minigame:<slug>`, `diary:<region>:<tier>`. Group/edge ids are
deterministic integers (§5).

### 6.7 `quest_points`
Remains a scalar the account supplies (`state.qp`); v1 does **not** auto-derive QP from completed quests
(a derived-atom feature, deferred). Quest-point gates (e.g. Dragon Slayer I = 32 QP) are `quest_points` atoms.

---

## 7. Validation (`data/validate_kg.py`)
Fails loudly (non-zero exit) on any violation, run pre-merge like `validate_iron_gate.py`:
1. **Acyclic** — the projected requires-graph has no cycles (engine `find_cycles()` returns empty) [invariant I1].
2. **Referential integrity** — every atom `ref_node` resolves to a node in `kg/nodes.json`; every edge `src`/`dst`
   (non-null) resolves; every `cond_group` referenced by an edge or a sub-group child exists.
3. **Vocabulary** — every `atom_type` is in the locked enum; every node `kind` is a valid `NodeKind`; every
   `op` ∈ {and, or, not}; `not` groups have exactly one child.
4. **No orphans** — no condition group unreferenced by any edge or parent; no duplicate node ids.
5. **Loadability** — `JsonKGStore` loads the committed `kg/*.json` without error.
6. **Completeness / freshness** — reconcile the ingested quest set against the live official quest list
   (count + names) and **flag any genuinely-missing quest** (so we can distinguish an intentional source
   exclusion — e.g. the novelty quest "Scrambled!", absent from `Module:Questreq/data` — from real data drift).
   Records the source `accessed` date so staleness is visible.

---

## 8. Testing
- **Golden-set acceptance (the "it works on real data" proof):** the scenarios hand-verified this session
  (scimitar locked→unlocked, fairy chain → ALREADY_SATISFIED, Barrows-gloves deep plan, obby-maul, etc.) are
  re-run against the **real ingested KG** via `JsonKGStore`; the engine must produce the **same** verdicts.
- **Builder unit tests:** a quest with `prereqs` + `skill_reqs` + an `ironman: true` flag → correct nodes/edge/
  condition tree (incl. the §6.3 family-conditional wrapper); a gear-set goal → correct `gear_loadout` composition;
  a multi-component item → correct component `AND`.
- **`JsonKGStore` round-trip:** build → load → the loaded store equals the in-memory builder output.
- **Engine regression:** the full existing engine suite (173 tests) stays green after the §6.4 family-aware change.
- **`validate_kg.py` passes** on the committed `kg/*.json`.

---

## 9. File structure
| File | Responsibility |
|---|---|
| `kg_ingest/builders/quests.py` | quests → nodes/edges/condition trees |
| `kg_ingest/builders/goals.py` | the §3 goal items/access/gear-sets/minigames + conditions |
| `kg_ingest/builders/supporting.py` | skill/item/monster/minigame/diary nodes referenced by atoms |
| `kg_ingest/assemble.py` | merge + stable ids + dedup → write `kg/*.json` |
| `kg/nodes.json`, `kg/edges.json`, `kg/condition_groups.json` | committed KG output |
| `src/osrs_planner/engine/kg/json_store.py` | `JsonKGStore(KGStore)` loader |
| `src/osrs_planner/engine/state.py` (edit) | `account_family(mode)` helper |
| `src/osrs_planner/engine/conditions.py` (edit) | family-aware `account_type` atom |
| `data/validate_kg.py` | invariant guard |
| `tests/kg_ingest/` | builder unit tests, golden-set, round-trip |

---

## 10. Success criteria (definition of done)
1. `kg/*.json` is built from `data/*.json` and committed; `validate_kg.py` passes.
2. `JsonKGStore` loads it and the engine answers `is_unlocked`/`prereqs_for`/`next_steps` for the §3 goals on
   **real account states**.
3. The golden-set scenarios reproduce the hand-verified verdicts on the real KG.
4. Account-family-aware iron requirements work for main / ironman / HCIM / GIM / HCGIM / UIM.
5. The full quest set (177 quests + 28 miniquests, type-aware; the 8 stray `diary` records routed out) loads,
   is acyclic, and the completeness/freshness check passes.
6. The existing 173 engine tests stay green.

---

## 11. Out of scope → follow-up bricks (recap)
Currency/cost dimension + `expand_for_account` (the next brick, designed in `research/currency-model.md`) ·
full item catalog · SQL/Postgres · the advisor + boost-source DB · the `clog_slot` atom (collection-log) ·
GE-price cache · GIM group-trade & UIM no-bank refinements.
