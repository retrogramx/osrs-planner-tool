<!-- Research input for the entity-graph ontology design pass.
Source: jbarrasa/goingmeta (Jesús Barrasa, Neo4j) — 46-session KG/ontology series.
Generated 2026-06-24 by mining the 15 most relevant sessions and mapping each onto
the Gilded Tome JSON+Python+committed-validator stack. NOT a directive — design input. -->

# Going Meta → Gilded Tome: Learnings → Actions Briefing

## TL;DR

The single biggest shift Going Meta argues for: **promote the schema from implicit/documented to a committed, machine-readable artifact that is the single source of truth driving extraction, assembly, AND validation** — author it ONCE before the new entity layer lands, and enforce edge-endpoint *kinds* (domain/range) as a hard invariant. For Gilded Tome that means a `kg/schema.json` declaring every node kind and every edge kind with its legal `(source.kind → target.kind)` pairs, consumed by `assemble.py`, fed to LLM extraction as the allowed-vocabulary prompt, and asserted by `validate_kg.py`. The second-biggest shift: when adding State/Location/NPC/Shop, **link, don't merge** — bridge to existing region/monster nodes with a typed `same_entity` edge so you never re-ingest the quest/diary/drop graph.

---

## Adopt now — shape the imminent ontology-design pass

### 1. Schema-as-contract: one committed `kg/schema.json` with domain/range (S5 / S28 / S29 / S32)

- **Principle:** Define node kinds + edge kinds (each with a `{domain_kinds, range_kinds}` whitelist and a one-line gloss) ONCE in a committed file; everything else derives from it.
- **Why here:** Today each domain has a bespoke hand-written builder. Adding State/Location/NPC/Shop the ad-hoc way = N more bespoke builders + silent drift. The owner's explicit "schema STABILITY / avoid re-ingest after churn" worry IS this problem.
- **Action:**
  - Write `kg/schema.json`: every node kind (with allowed `data` fields + types) and every edge kind as `{edge, domain_kinds, range_kinds, gloss}` — `contains: Location→Location|NPC`, `operates: NPC→Shop`, `sells: Shop→Item`, `drops: Monster→Item`, `gives_access: Diary→*`, plus existing `requires/grants/progress_towards/supersedes/effect`. **Reconcile region≈Location and monster≈NPC in this same file** so new kinds extend, not fork, the type system.
  - Extend `validate_kg.py` with one generic pass: every edge's `source.kind ∈ domain_kinds` and `target.kind ∈ range_kinds` for its type → fails CI otherwise. This is the JSON analog of OWL `rdfs:domain`/`rdfs:range`, enforced (which Neo4j itself doesn't even do).
  - The **conditional-modifier** ("Varrock Diary tier≥X ⇒ noted battlestaves @7000/day") stays a **typed edge carrying a condition-group** (your existing AND/OR/NOT atom tree), with its own domain/range row — NOT free-text literal. Keeps it queryable like `effect` edges.

### 2. Schema-as-prompt: render the schema to NL and feed it to the extractor (S29 / S41 / S25 / S30)

- **Principle:** Hand the LLM the closed vocabulary (kinds + edges + domain/range) as the extraction target so wiki prose collapses onto known kinds ("Zaff" → `NPC`, never free-text "shopkeeper"). A machine-generated NL paraphrase of the schema guides the LLM as well as formal OWL — the value is the controlled vocabulary, not the formalism (S41's empirical finding).
- **Why here:** This blocks fabricated *shape* (invented kinds/edges) — the complement to your existing source-grounding gate, which only blocks fabricated *values*.
- **Action:**
  - Write one Python renderer (`getNLOntology` analog) that emits `kg/schema.json` as a natural-language CARD, committed and **regenerated from the one source file** so prompt and validator can never drift. Add a test for the renderer (S29 shipped a real `cat`/`xtracat` renderer bug).
  - **Critical caveat (S29/S25/S30):** the LLM proposes SHAPE; it does NOT certify FACTS. Every extracted entity/edge still passes the existing `verify_*.py` wiki-citation gate. Do NOT let the LLM write to the graph — it produces `data/*.json` rows that flow through builders → `assemble.py`, preserving byte-stability and provenance.

### 3. LLM-as-one-time-modeler, code-as-loader (S25 / S30)

- **Principle:** Split hard between LLM (schema design + column→attribute mapping, from *metadata* not raw rows) and deterministic Python (all extraction/loading). The nesting of a typed extraction schema IS the containment hierarchy.
- **Why here:** Directly answers "avoid re-prompting over raw data after churn" and gives reproducible identity.
- **Action:**
  - Introduce a committed per-domain **SCHEMA+MAPPING artifact** (`{entities:[{kind, attributes:[{name, mappedTo:<wiki field>}]}], relationships:[{type, from, to}]}`) as the interface between curation and builders. Your `research/wiki-source-catalog.md` is already your "Croissant metadata" input.
  - **Deterministic identity = fingerprint/slug from a canonical key** (`npc:` + slug(name + location) so two "Bob"s don't collide) + a **UNIQUE-id invariant in `validate_kg.py`** (replaces Neo4j's UNIQUE constraint). This is the answer to identity/disambiguation across new kinds vs existing region/monster nodes.
  - Require a **verbatim wiki-source span on every leaf** (S30's `Excerpt.text`) so fabrication-resistance is structural and verifiers have a quote to check.

### 4. Link, don't merge — reconcile via a typed `same_entity` edge (S36 / S14)

- **Principle:** Keep each source structure intact; lay a separate, typed equivalence edge over the originals. Two axes stay distinct: **containment** (`contains/operates/sells`) vs **identity** (`same_entity`/`alias`).
- **Why here:** This is THE answer to "reconcile new kinds with existing region/monster nodes" WITHOUT re-doing quest/diary/drop ingestion — old nodes are never destructively rewritten, they just gain `same_entity` edges. Existing golden tests + byte-stable assemble stay green.
- **Action:**
  - Add `same_entity`/`denotes` edge kind (src = new entity-layer node, dst = existing node, with a `source/basis` field). Add `validate_kg.py` invariants: connects two existing ids, non-self-referential, no contradictory many-to-many bridge for one OSRS concept.
  - **Reconciliation as a query, propose-don't-assert (S14):** validator reports an "incomplete triangle" (e.g. NPC placed in a Location whose `same_entity` region disagrees with the monster's region) as a **CANDIDATE-link report**, never auto-asserted. Ground every `same_entity` in a wiki fact, never string-similarity.
  - OWL `sameAs` symmetry/transitivity is NOT free here — if you need "follow equivalence then inherit," write it explicitly in builders/engine, gated by an invariant.

### 5. Declarative, severity-tagged invariant registry (S3 / S11)

- **Principle:** Refactor `validate_kg.py`'s growing `if/errors.append` blocks into a NAMED, versionable rule registry; report violations as DATA `(rule_code, node_id, offending_value)`, not opaque strings; tag per-rule **severity** (VIOLATION / WARNING / INFO).
- **Why here:** As the entity layer grows, you need triage: an ungrounded conditional-modifier or an NPC with no containing Location should WARN (incomplete-but-known, lands while tracked), not hard-fail the build. Closed-shape rules (allowed `data` keys per kind) catch silent field drift — the stability safeguard.
- **Action:**
  - `kg/shapes.py` (or `shapes.json`): one shape per node-kind and edge-kind — required fields, id-pattern (`^shop:[a-z0-9-]+$`), enum membership over the **locked kind/edge vocabularies**, endpoint-class + cardinality (`sells: Shop→Item`; `contains` parent-cardinality = 1), closed allowed-key set, severity. Runner exits non-zero only on VIOLATION; reports WARNING/INFO.

### 6. Competency questions as the empirical acceptance gate (S42)

- **Principle:** Ontology quality = (A) structural smells (orphan-kind/connectivity, provenance coverage %, typed-edges-vs-data-blob ratio, containment depth) + (B) **functional fitness**: can the graph actually answer the domain's real questions? Functional is primary.
- **Why here:** Makes "how literal is the conditional edge?" an EMPIRICAL question. If the CQ "Where can an ironman buy battlestaves and at what price after Varrock Hard diary?" can't be answered by a query, the edge isn't modeled richly enough — you discover the gap on the pilot, before the full ingest.
- **Action:**
  - Commit `kg/competency_questions.json` (`question + expected-answer-shape + the actual query`), ~15 entity-layer questions including the Zaff/battlestaves conditional exemplar. Run them against the KG in CI like golden tests (the load-bearing part is the empirical run, NOT the LLM scorer).
  - Add structural-coverage assertions: no orphan Location/Shop/NPC; provenance-coverage % per kind; containment depth correct (flag a Location wired directly to an Item, skipping NPC/Shop); watch the typed-edge-vs-`node.data`-blob ratio (if entity facts land as opaque JSON, you built a record store, not a graph).

---

## Adopt later — construction + product phases

- **Edge-implied type inference + transitive closure (S4).** Once edges exist, infer/validate `kind` from edge participation (anything on the source of `operates`→Shop IS an NPC) — catches a region/monster node accidentally on a `contains` chain. Compute transitive `contains`/`gives_access` closure (the "what's in Misthalin", Ghommal's-hilt-style `boosts` chains that are "unsayable today") in the builders at assemble time into a **separate committed `kg/inferred.json`** (clearly marked derived, byte-stable, never hand-written/claimed as wiki fact). Keep asserted vs derived in separate files. Defer until the asserted base layer is stable.
- **Schema versioning by audited delta (S19).** Add `schema_version` to `kg/schema.json`; on each assemble, compute set-diff of `(schema, node-ids-by-kind, edge-type-counts)` vs the previously committed `kg/` snapshot and print/fail on added+removed — every schema bump ships as a reviewable, bounded blast-radius diff. Git is your "composite store" / version ledger. Becomes valuable once the schema starts actually churning.
- **Decisions graph — "the graph behind the graph" (S46).** Commit `kg/design_decisions.json` (one record per node/edge kind: `id, what, rationale, alternatives_rejected, grounding, supersedes, status`); invariant: every `node.kind`/`edge.type` in the KG references an existing non-superseded `decision_id`. Lifts your "Tokkul-trap fixed / RDT can't be tagged" tribal knowledge out of MEMORY.md/commit messages into queryable data. Keep rationale text a shape-sample under owner verification (consistent with the editorial-verification lesson). Bootstrap as the schema grows; don't reconstruct later.
- **Run extraction N times, measure identity consistency (S41).** Before scaling past the first slice, run the LLM extractor ~5–9× on the Varrock slice and quantify node/edge-identity stability against a fixed golden-ASK suite. Answers "bounded subset vs all of OSRS" empirically: prove the slice is stable, then fan out.

---

## Where Going Meta does NOT transfer

Every session is Neo4j/RDF/OWL/SPARQL/n10s/SHACL/Protege-native. **Adopt none of the stack** — you already have the better-fit analog:

| Going Meta tooling | Do NOT adopt | Your existing/JSON-stack analog |
|---|---|---|
| Neo4j + Cypher MERGE/UNWIND loaders | the DB | per-domain builders → `assemble.py` → committed `kg/*.json` (byte-stable; deterministic load Cypher only approximates) |
| OWL/Turtle ontology, Protege/WebProtege | RDF authoring | committed `kg/schema.json` (kinds + domain/range table) |
| SHACL shapes + `n10s.validation.shacl.validate` | a SHACL engine | `validate_kg.py` Python assertions / `shapes.py` registry — your committed validator IS your SHACL |
| `n10s.inference.*` / OWL reasoner | reasoner-inferred equivalence | explicit Python closure into `kg/inferred.json`; nothing auto-propagates |
| `apoc.trigger` live materialization | mutable triggers | deterministic batch rebuild — "re-run assemble" gives the same consistency without stored mutable state |
| `owl:sameAs` semantics | reasoner equivalence | a plain typed `same_entity` edge; symmetry/transitivity written explicitly if needed |
| composite multi-version DBs (S19) | n/a | prior committed `kg/` snapshots + git diff |
| `rdflib` `getNLOntology` / `g.serialize` | rdflib | small Python renderer (test it — S29's had a bug) |
| LLM writing Cypher/RDF directly to store | direct-to-graph | LLM emits `data/*.json` DRAFT → source-grounding verifier → builders |
| `cceval.py` LLM ontology scorer | LLM-opinion gate | store CQs as data, assert the engine answers them deterministically (like golden tests) |

Also do NOT trust the LLM's facts: S25/S28/S30 trust model output directly; Gilded Tome's no-fabrication discipline means the ontology constrains SHAPE only — every datum still clears the wiki-citation gate.

---

## Net new ideas for the roadmap (not already doing)

1. **`kg/schema.json` with an enforced edge domain/range whitelist** — a single machine-readable type system that drives builders, the LLM prompt, AND a new endpoint-kind invariant in `validate_kg.py`. We have validators but no committed schema-as-data; this is the keystone. *(S5/S28/S32)*
2. **`same_entity` reconciliation edge + "incomplete-triangle" CANDIDATE report** — link the new entity layer to existing region/monster nodes instead of merging, so we never re-ingest. New edge kind + propose-don't-assert validator pass. *(S36/S14)*
3. **Schema→NL renderer as the extraction prompt** — one tested Python function emitting the schema as an LLM-facing card, regenerated from the one source so prompt/validator can't drift. *(S29/S41)*
4. **Per-domain SCHEMA+MAPPING artifact + deterministic fingerprint-id + UNIQUE-id invariant** — LLM-proposes/code-loads split with reproducible identity from a canonical key tuple. *(S25/S30)*
5. **`kg/competency_questions.json` run as a CI gate** — make schema fitness (esp. the conditional-modifier's literalness) an empirical pass/fail on the Misthalin pilot before scaling. *(S42)*
6. **Severity tiers (VIOLATION/WARNING/INFO) in the validator** — let partial/known-incomplete entity ingestion (ungrounded conditional-modifier, NPC missing a Location) land tracked rather than block the build. *(S3/S11)*

**Recommended sequencing:** write `kg/schema.json` + domain/range invariant + `same_entity` edge → render schema to NL prompt → ingest the bounded **Misthalin → Varrock → Zaff → Zaff's Superior Staffs → battlestaves + Varrock-Diary conditional** slice end-to-end → gate it with competency questions, run extraction N× → only then fan out to a second location.
