# Entity-Graph Ontology v1 — Design Spec (REACT & REFINE)

> **Status:** DRAFT for owner review. This is the *contract* for evolving the Gilded Tome KG
> from a thin requirement+reward graph into a richly-typed **entity web** (the owner's
> Misthalin▸Varrock▸Zaff model). It defines node kinds, edge kinds, the conditional model,
> identity, the committed schema artifact, validation, and a migration + pilot plan.
> **Not** an implementation plan and **not** a mass-ingest order — it is the thing we agree on
> *before* code. Design input: `research/goingmeta-kg-learnings.md`.

---

## 0. The one-paragraph version

Promote the schema from "implicit in each builder" to a single committed **`kg/schema.json`** that
declares every node kind and every edge kind *with its legal `(source.kind → target.kind)` pairs*.
Add three node kinds (**state, npc, shop**) and activate three edge types your model already reserves
(**located_in, drops, gated_by**) plus two new ones (**operates, sells**). **Reuse `region` as the
"Location" level** and **link, don't merge** — the existing quest/diary/drop graph is never re-ingested.
Diary/quest-gated rewards become **typed edges carrying a condition-group** (your existing AND/OR/NOT
atom tree), not free text. Prove it on one end-to-end **Misthalin pilot slice**, gated by committed
**competency questions**, before fanning out.

---

## 1. Design principles (from Going Meta + our existing discipline)

1. **Schema-as-contract.** One committed machine-readable `kg/schema.json` is the single source of
   truth; builders, the LLM-extraction prompt, and `validate_kg.py` all derive from it. *(GM S5/S28/S32)*
2. **Link, don't merge.** New entity-layer nodes attach to existing nodes with a typed `same_entity`
   edge; existing nodes are never destructively rewritten. Byte-stability + golden tests stay green. *(GM S36/S14)*
3. **Existence vs facts vs derived, in separate files.** Existence/identity nodes first; facts accrete
   onto the same stable id later; computed/inferred edges live in a clearly-marked separate file, never
   hand-claimed as wiki fact. *(GM S4)*
4. **Source-grounded, validator-gated, byte-stable, provenance-bearing.** Unchanged — our existing moat.
   The LLM proposes *shape*; every *fact* still clears the wiki-citation verifier.
5. **The schema constrains shape; the wiki gates facts.** Two independent fabrication gates:
   schema-membership (no invented kinds/edges) + source-grounding (no invented values).

---

## 2. The type system

### 2.1 Existing node kinds (14 — keep, now governed by the schema)

`skill · item · monster · quest · diary · combat_achievement · minigame · clog_slot · activity ·
region · access · gear_loadout · account_type · goal`

### 2.2 New node kinds (3)

| kind | id pattern | what it is | key `data` |
|---|---|---|---|
| `state` | `state:<slug>` | A kingdom / political region (top of the geography spine). | `polity` (e.g. "human", "elf", "dwarf"), aliases |
| `npc` | `npc:<slug>` | A **non-combat** interactive character (shopkeeper, quest-giver, banker). | `role`, `location_ref` (for id disambiguation) |
| `shop` | `shop:<slug>` | A store/stall with a stock list. | `shop_type`, `currency` |

### 2.3 Fork A — reconciling new kinds with existing ones (RECOMMENDATION)

- **`region` IS the "Location" level.** The 61 existing `region` nodes (Varrock, Burgh de Rott, Nardah,
  Ardougne Monastery…) already model places. We declare `region` as the Location kind in the schema and
  build the hierarchy on it — **no rename, no duplicate `location:` nodes, no re-ingest.** `state` sits
  above it; `npc`/`shop` below.
  - *Note:* the diary **areas** (`ardougne`, `falador`…) are NOT region nodes — they're `data.region`
    on `diary:<area>:<tier>` nodes. So "diary area" and "Kingdom/State" are orthogonal axes; no conflict.
    (Varrock-diary lives in Misthalin; Falador-diary in Asgarnia — captured by `located_in` on the
    region the diary's tasks occupy, not by the diary id.)
- **`monster` and `npc` stay distinct kinds**, grouped under a `character` *category* in the schema
  (`monster` = attackable / has a drop table; `npc` = non-combat). An entity that is both (attackable
  shopkeeper) is rare; handle with `same_entity` when it arises. Non-destructive — `monster` is untouched.
- **`same_entity` is reserved for genuine cross-layer identity bridges**, which become rare precisely
  because we reuse `region`. (Where it earns its place: an `npc` that is also a quest-giver already
  modeled elsewhere, or future de-dup of a place that exists under two ids.)

> **Open decision A1:** OK to reuse `region` as Location (recommended) vs introduce a distinct `location`
> kind + `same_entity` bridges (more nodes, more faithful to "link don't merge" but creates place dups)?

---

## 3. Edge kinds (the relationship vocabulary)

### 3.1 Existing edge types (8) — keep; the schema now declares their domain/range

| edge | domain → range (proposed) | carries `cond_group`? | notes |
|---|---|---|---|
| `requires` | any → (cond_group, dst optional) | yes | the hard-requirement DAG |
| `grants` | quest/diary/goal → item/None | no | rewards |
| `progress_towards` | any → goal | no | counters |
| `supersedes` | item→item, goal→goal | no | upgrade ladders |
| `effect` | item/diary → skill/activity/region/monster | no | the diary perk layer (260 edges) |
| `drops` *(reserved, unused)* | monster → item | no (rate in data) | **activate** for the drops brick |
| `located_in` *(reserved, unused)* | region→state, npc→region, shop→region, region→region | no | **activate** as the containment spine |
| `gated_by` *(reserved, unused)* | region/access → (cond_group) | yes | **activate** for access-gating |

### 3.2 New edge types (3)

| edge | domain → range | carries `cond_group`? | gloss |
|---|---|---|---|
| `operates` | npc → shop | no | the NPC runs the shop |
| `sells` | shop → item | **yes** | shop stocks the item; a `cond_group` makes it a *conditional* offer |
| `same_entity` | entity → existing node | no | identity bridge (link-don't-merge); `data.basis` = wiki fact |

> **Open decision A2:** is `operates` worth a distinct edge, or fold ownership into `located_in` +
> a `data.operator` ref on the shop? (I lean keep `operates` — it's a real, queryable relationship.)

---

## 4. The conditional-modifier model (Fork B) — the Zaff example, fully worked

A diary/quest-gated reward is a **typed edge carrying a `cond_group`** — the *same* AND/OR/NOT atom-tree
mechanism `requires` edges already use. No free-text literals; it stays queryable.

**Nodes** (the containment path):
```
state:misthalin              {kind:state, name:"Misthalin", data:{polity:"human"}}
region:varrock               (EXISTING — reused as Location)
npc:zaff                     {kind:npc,  name:"Zaff", data:{role:"shopkeeper", location_ref:"region:varrock"}}
shop:zaffs-superior-staffs   {kind:shop, name:"Zaff's Superior Staffs!"}
item:<battlestaff id>        (EXISTING)
```
**Edges** (the web):
```
located_in : region:varrock            → state:misthalin
located_in : npc:zaff                   → region:varrock
operates   : npc:zaff                   → shop:zaffs-superior-staffs
sells      : shop:zaffs-superior-staffs → item:<battlestaff>     data:{price: <base>, currency: coins}
sells      : shop:zaffs-superior-staffs → item:<noted battlestaff>
             cond_group = AND[ achievement_diary(varrock:hard) == completed ]
             data = { price: 7000, qty: 60, frequency: "daily", noted: true,
                      dispenser: "barrel, ground floor", resellable_profit: true,
                      source_token: "<verbatim wiki span>" }
```
- **Tier-scaling** (qty 15/30/60/120 for easy/med/hard/elite): **one gated `sells` edge per tier**,
  each `cond_group` referencing that tier's `achievement_diary` atom. Clean, queryable, and reuses the
  existing diary atoms — *this is how the diary brick's reward data re-points onto the entity graph.*
- **Fidelity dial (the actual Fork-B decision):** v1 captures `{item, price, qty, frequency, noted}`
  as typed `data` (queryable) and keeps the prose specifics ("the barrel on the ground floor") as a
  `dispenser`/`facet` string. We do **not** model the barrel as its own node in v1.

> **Open decision B1:** is `{price, qty, frequency, noted}`-as-typed-data + prose-facet the right
> fidelity, or do you want more/less? (The **competency questions** in §8 will test this empirically
> on the pilot — if a real question can't be answered, we enrich.)

---

## 5. Identity & ids

- **Prefix per kind** (existing convention extended): `state:`, `npc:`, `shop:` join `region:`, `item:<id>`, etc.
- **Deterministic id = slug of a canonical key.** For collision-prone names, the key includes the
  container: `npc:zaff` is fine, but two "Bob"s become `npc:bob-lumbridge` / `npc:bob-draynor`
  (slug of name + location). *(GM S25/S30 fingerprinting.)*
- **UNIQUE-id invariant** in `validate_kg.py` (it already checks duplicate node ids) is the JSON analog
  of a DB uniqueness constraint — extend it to the new kinds.
- **`same_entity` is grounded, never string-similarity** — `data.basis` cites the wiki fact. Reconciliation
  is **propose-don't-assert**: a validator pass reports *candidate* links (an "incomplete triangle") for
  human/owner confirmation; it never auto-asserts. *(GM S14/S36.)*

---

## 6. `kg/schema.json` — the committed contract (the keystone)

A single committed file, the source of truth that everything derives from:
```jsonc
{
  "version": "1.0.0",
  "node_kinds": {
    "shop": { "category": "place", "id_prefix": "shop:", "data_fields": {"shop_type":"string?","currency":"string?"}, "gloss": "A store with a stock list." },
    "npc":  { "category": "character", "id_prefix": "npc:", "data_fields": {"role":"string?","location_ref":"id?"}, "gloss": "A non-combat interactive character." },
    "state":{ "category": "place", "id_prefix": "state:", "data_fields": {"polity":"string?"}, "gloss": "A kingdom / political region." }
    // … every existing kind too
  },
  "edge_kinds": {
    "sells":      { "domain": ["shop"], "range": ["item"], "cond_group": "optional", "gloss": "Shop stocks item; cond_group ⇒ conditional offer." },
    "operates":   { "domain": ["npc"],  "range": ["shop"], "cond_group": "no" },
    "located_in": { "domain": ["region","npc","shop"], "range": ["region","state"], "cond_group": "no" },
    "drops":      { "domain": ["monster"], "range": ["item"], "cond_group": "no" },
    "same_entity":{ "domain": ["*"], "range": ["*"], "cond_group": "no", "requires_data": ["basis"] }
    // … requires/grants/effect/supersedes/progress_towards/gated_by
  }
}
```
It drives three consumers (regenerated from this one file so they can never drift):
1. **Builders / `assemble.py`** — read it to know the legal vocabulary.
2. **The LLM-extraction prompt** — a tested Python renderer emits the schema as a natural-language
   "vocabulary card" so wiki prose collapses onto known kinds ("Zaff" → `npc`). *(GM S29/S41.)*
3. **`validate_kg.py`** — a generic **domain/range invariant**: every edge's `src.kind ∈ domain` and
   `dst.kind ∈ range` for its type, else fail. (The JSON analog of OWL `rdfs:domain`/`rdfs:range` —
   *enforced*, which Neo4j itself doesn't do.) *(GM S3/S5.)*

---

## 7. Validation upgrades

- **Domain/range pass** (above) — new, generic, schema-driven.
- **Severity tiers** — `VIOLATION` (fail build) / `WARNING` (lands tracked) / `INFO`. Lets partial entity
  ingestion proceed: an `npc` with no containing `region`, or an ungrounded `sells` cond, **warns** rather
  than blocks. *(GM S3/S11.)*
- **Closed-shape rules** — allowed `data` keys per kind (catches silent field drift).
- **Structural-coverage metrics** — no orphan `shop`/`npc`; provenance-coverage %; containment depth
  (flag a `region` wired straight to an `item`, skipping npc/shop); typed-edge-vs-`data`-blob ratio
  (if facts land as opaque JSON, we built a record store, not a graph). *(GM S42.)*

---

## 8. Competency questions — the empirical acceptance gate

Commit `kg/competency_questions.json` (`question · expected-answer-shape · the query`), run in CI like
golden tests. Seed set for the pilot (must all answer on the Misthalin slice):
1. "What does Zaff sell?" → `sells` out of `shop:zaffs-superior-staffs`.
2. "Where is Zaff?" → `located_in` chain `npc:zaff → region → state`.
3. "After Varrock **Hard**, where/at-what-price can I buy noted battlestaves, how many, how often?"
   → the gated `sells` edge's `data`. **(the Fork-B literalness test)**
4. "What items get cheaper anywhere in Misthalin with a diary?" → traverse `located_in*` ∩ gated `sells`.
5. "What's contained in Misthalin?" → transitive `located_in` closure.

If a question can't be answered, the model isn't rich enough — discovered on the pilot, before mass ingest.

---

## 9. Migration — what changes vs stays (no re-ingest)

| Existing | Fate |
|---|---|
| quests, skills, items, goals, diaries (nodes + requires/grants/progress_towards) | **unchanged** |
| 61 `region` nodes | **kept**, now also the Location level; gain `located_in` edges upward to `state` |
| 15 `monster` nodes | **unchanged**; gain `drops` edges when the drops brick wires in |
| diary `effect` edges (260) | **kept as-is** for now; *over time* the NPC/shop-class effects re-point onto the richer `sells`/entity targets — incrementally, not a big-bang rewrite |
| `validate_kg.py` | **extended** (domain/range + severity), not rewritten |
| `assemble.py` byte-stability | **preserved** |

The entity layer is **purely additive** in v1. Nothing built in rounds 1–9 is invalidated.

---

## 10. The Misthalin pilot (first end-to-end proof)

Build exactly ONE slice through every new mechanism:
`state:misthalin ▸ region:varrock ▸ npc:zaff ▸ shop:zaffs-superior-staffs ▸ item:battlestaff` + the four
tier-gated `sells` edges (the Varrock-diary discount). Then: domain/range validator green, the §8
competency questions answer, byte-stable, run the extraction N× to measure identity stability *(GM S41)*
before any second location. Bounded, reviewable, and it exercises the entire ontology.

---

## 11. Scope & sequencing (Fork C: bounded-first)

1. `kg/schema.json` + the domain/range invariant + the 3 node kinds + `operates`/`sells`/`same_entity`. *(design+code, small)*
2. The schema→NL renderer (tested) for extraction prompts.
3. The **Misthalin pilot** end-to-end + competency questions. ← *prove it here*
4. Severity tiers in the validator.
5. Only then: a second location, then a kingdom, then fan out — each grounded + gated as today.
**Deferred until they earn their place:** schema versioning by audited delta (GM S19), the design-decisions
graph (GM S46), inferred/transitive-closure file (GM S4), full multi-source LLM extraction at scale.

---

## 12. Open decisions for the owner (please react)

- **A1.** Reuse `region` as Location (recommended) vs a distinct `location` kind + `same_entity` bridges?
- **A2.** Keep `operates` as its own edge (recommended) vs fold into `located_in` + a `data.operator`?
- **B1.** Conditional fidelity: `{price,qty,frequency,noted}`-as-typed-data + prose facet (recommended),
  or richer (model the dispenser/barrel, currency variants) / lighter?
- **C1.** `npc` vs `monster`: keep distinct (recommended) vs one `character` kind with `attackable` flag?
- **D1.** Pilot choice: Misthalin▸Varrock▸Zaff (recommended, it reuses your worked example) vs a different slice?
- **E1.** Do you want the **competency-questions CI gate** in from day one (recommended), or added after the pilot?
