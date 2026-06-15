# Data correctness & the advisor layer — research (scratch — NOT a decision)

> Working notes for the eventual `feat/goal-tracker` (and the ingest/QA bricks). **Non-binding**;
> nothing here is locked. Companions: [`knowledge-graph.md`](knowledge-graph.md) (direction +
> sourcing + licensing) and [`kg-schema-v1.md`](kg-schema-v1.md) (the node/edge schema this
> validates *into* and the engine reads *out of*). Real decisions move into a plan/ADR per brick.

---

## The through-line: determinism-first, LLMs only at the boundaries

One principle unifies both topics below. The **correctness-critical spine** — reconciled data
extraction *plus* the graph engine — is **deterministic and LLM-free**. LLMs sit only at the two
fuzzy human/text boundaries: normalizing messy source text on the way *in*, and narrating
personalized guidance on the way *out*. Both are **grounded** (validated against / computed by the
deterministic core), never free-recall.

```
        Tier-3 normalize             DETERMINISTIC CORE              Consumption layer
Wiki/cache ──LLM(fuzzy)──▶  KG (facts, validated) + account state ──▶ engine ──LLM(fuzzy)──▶ user
                            └────────── correctness-critical, LLM-free ──────────┘
```

Why: an LLM in a correctness path is a *source* of error (hallucination), not a reducer of one.
Use it only where the input is genuinely unstructured/subjective AND its output can be checked.

---

# Part A — Factual data validation (getting correct data IN)

## Structural validity ≠ factual correctness

The schema's QA invariants (acyclic REQUIRES, FK integrity, well-formed condition trees, provenance
present — see `kg-schema-v1.md` §QA) only validate **structure**. A KG can be perfectly valid and
perfectly *wrong* about the game (e.g. Scurrius listed at the wrong combat level, a quest granting an
access it doesn't). Factual correctness is a separate, harder, data-*trust* problem. This note is
about that second problem.

## Extraction tiers — determinism first, LLM last

Most OSRS data we need is **already structured**, so we *query* it, not crawl-and-read it.

| Tier | Data | Tool | LLM? |
|---|---|---|---|
| 1 | Monsters, items, drops, quest reqs (IDs, levels, slots, drop lines) | OSRS Wiki **Bucket** API (`action=bucket`) + **game cache** (OpenRS2 / RuneLite dumps), **reconciled** against each other | **No** |
| 2 | `/Strategies` "Recommended equipment" tables (slot × ranked items) | Deterministic wikitext/HTML table parser (`mwparserfromhell` / BeautifulSoup) | **No** |
| 3 | Freeform footnote **conditions** ("only with full Void") → the `condition` tree; pure-prose facts | LLM **normalizer** with structured output, behind validation | **Yes, narrowly** |

> **Recon update (2026-06-14, live-verified — workflow `wiki-data-recon`).** The determinism-first
> thesis HOLDS, but two specifics were busted: **(1) the wiki no longer runs Cargo** — it migrated to
> Weird Gloop's in-house **Bucket** extension (`action=bucket`, Lua chain
> `bucket('name').select(...).where(...).run()`; namespace `Bucket:`, schema browser `Special:Bucket`).
> Any `action=cargoquery` connector fails 100%. **(2) Tier-3/LLM scope is wider than assumed** (below).
> Verified buckets: **`infobox_monster`** (3.2k rows; `combat_level`, stats, bonuses),
> **`infobox_item`** (16k), **`infobox_bonuses`** (`equipment_slot` + all bonuses),
> **`dropsline`** (38k; `drop_json`), **`recommended_equipment`**, **`item_id`/`npc_id`/`object_id`**.
> Quirks: ids come back as **string arrays** (`item_id:["377"]`); Bucket **omits null/false fields**;
> operators are `= != > < >= <=` + `limit/offset/orderBy` on **top-level columns only** (no LIKE/regex/JSON-subkey).
>
> **Pipeline reshapes:** drops are structured but **not relationally queryable** (opaque `drop_json`) →
> build monster→drops via **fetch-all + client-side group-by**; pull **/Strategies gear from RAW WIKITEXT**,
> not the Bucket mirror (the mirror loses `{{efn}}` footnote text + the `>` priority chains); **quest
> requirements are mostly prose** — only skill+level reqs have a structured fast-path
> (`<span class="scp" data-skill data-level>`), so prereq-quests / items / conditional logic move to **Tier 3**.

- **Tier 1 is where correctness is won.** The wiki is a Weird Gloop MediaWiki exposing the Action
  API, **Bucket** structured tables (`action=bucket` — *not* Cargo), and Lua `Module:` data. The game
  cache is authoritative for game-mechanical facts (item/npc **IDs, names, combat levels**) — note
  **equipment slot comes from the wiki** (`infobox_bonuses.equipment_slot`), *not* the cache. Pull
  both and **reconcile**: agree → high confidence; disagree → flag for review. Two independent
  sources agreeing is the cheapest path to ground truth.
- **Tier 3's LLM is a normalizer over already-extracted text, never a crawler.** Its output is
  *untrusted*: every item it names must resolve to a real `item:` node (the FK referential-integrity
  check catches hallucinations for free); every number is range-checked.
- **"Agent per entity" — yes as per-*type* deterministic extractors** (`MonsterExtractor`,
  `ItemExtractor`, `LoadoutExtractor`), **no as per-*instance* LLM agents.** Thousands of LLM agents
  crawling prose would be slow, costly, non-reproducible, and un-QA-able — the opposite of what a
  correctness pipeline needs.

## Validation strategy (layered)

1. **Two-source reconciliation** (Bucket ⊕ game cache) — the strongest signal, mostly free.
2. **Structural invariants as cheap *incorrectness*-catchers** — the existing 17 invariants don't
   *prove* correctness, but a hallucinated item fails an FK, combat level 9999 fails a range check,
   a quest with zero grants is suspicious. Huge error class caught for nearly nothing.
3. **Cross-entity consistency** — a loadout calls `item:11665` a "Void helm"? Check the cache: is
   item 11665 *actually* a Void helm? Independently-extracted data cross-referencing itself is a
   powerful free check.
4. **Golden-set + regression eval** — hand-verify ~50–100 core entities (Scurrius & co.), score
   every pipeline run for per-field precision/recall, fail CI on regression. (Pairs with the
   `core_set.yaml` already referenced in the schema's completeness checks.)
5. **LLM-as-judge for *faithfulness*, not truth** — for Tier-3 normalization: "does
   `OR(full-void, AND(70 Atk, 70 Str))` faithfully represent the footnote 'requires 70 Attack and
   Strength, or full Void'?" Judging equivalence is more robust than generating. The editorial gear
   *rankings* have no objective truth — the target there is faithful transcription of the wiki.
6. **Provenance + revision pinning → drift detection** — store the wiki `oldid` + accessed date.
   Re-query later; if a page's `oldid` moved, re-extract and **diff** — a changed value surfaces as
   a review item automatically. This is how the KG stays correct across game/wiki updates instead of
   silently rotting.

## The schema already supports this

- **`node.verify` / `edge.verify`** = "extracted but not yet reconciled against ground truth"
  (structural QA is value-independent, so a half-verified KG still ships).
- **`provenance.source_rev` (the wiki `oldid`)** = reproducible extraction + the drift-detection key.
- **Refresh = full rebuild + atomic swap** with id-stability invariant (I11) protecting account refs.

## Sourcing etiquette

Prefer the **Bucket / Action API over scraping** rendered HTML; descriptive User-Agent (with contact);
serialize requests + `maxlag`; cache aggressively; pin `oldid`. (The wiki publishes no hard rate-limit
number — `RuneScape:APIs`/`Meta:API_etiquette` 404 — so follow the generic MediaWiki etiquette.
Consistent with the CC BY-NC-SA attribution resolution in `knowledge-graph.md`.)

## Tooling note — don't conflate the LangChain stack

- **LangChain / LangGraph** = build/orchestrate LLM apps & agents (the thing that *would* run Tier-3
  extraction if we went agentic).
- **LangSmith** = observability + **evaluation** (tracing, golden datasets, evaluators incl.
  LLM-as-judge, regression tracking). This is the layer that *measures* extraction quality — the
  good fit for steps 4–5 above. It is **not** a crawler or an agent runtime.
- We likely don't need LangChain just to call the wiki API (that's plain HTTP). Reach for
  LangGraph only if the Tier-3 tail genuinely needs agentic orchestration — skip until the
  deterministic core proves insufficient.

---

# Part B — The advisor / consumption layer (getting guidance OUT)

This is the *other* end of the pipeline: take the validated KG + per-account state and turn it into
personalized "what's next" guidance. Same determinism-first principle applies.

## The line: the engine decides *what*, the LLM communicates *why/how*

**Don't let the LLM do the graph reasoning.** "Match next steps to where the account is" sounds like
an LLM job, but it's exactly what the KG was built to compute **deterministically**:

- *Is goal X unlocked?* → evaluate its scoped `requires` edges + condition trees against state
- *What's between them and the goal?* → `nx.descendants(requires_dag, goal)` (full prereq closure)
- *In what order?* → `topological_sort`
- *Cheapest single next action?* → the unmet-leaves walk ("train Strength to 70")
- *Account-type-aware* expansion → ironman: Fire cape → `activity:fight-caves`; main: a gp goal

That "matching" **is the engine** — correct, reproducible, unit-testable. An LLM doing it
reintroduces hallucination into the one answer that must be right.

## The failure mode that proves the line

Ask a raw LLM "what's my ironman's next step toward a Fire cape?" → it suggests *buying* one, because
"just buy it" is the statistically common answer. The engine **can't** make that mistake:
`account:ironman.can_ge = false`, so the expansion policy never enumerates the GE route.
Account-type-awareness is a **systematic rule**, not a fact to recall — and systematic rules are
exactly what LLMs get subtly, confidently wrong. Encode the rule once in the engine; the LLM never
re-derives it.

## Where the LLM earns its place

Given the engine hands it a **correct, account-aware candidate set**, the LLM does what the engine
can't:

1. **Natural-language interface (tool-use / grounding).** Parse intent → **call engine functions**
   (`is_unlocked`, `prereqs_for`, `expand_for_account`) as tools → phrase the result. A translator on
   both ends, never the reasoner in the middle. Its "knowledge" of what's unlocked comes *only* from
   the engine → correct by construction.
2. **Soft prioritization.** The engine returns *many* valid frontier steps; much ordering is also
   deterministic (EHP/EHB efficiency from WiseOldMan). The LLM handles the fuzzy residual — "I find
   Slayer boring," "I have 2 hours," "I'm a clue hunter" — by **reordering within** the engine's
   valid set. It may re-rank; it may never invent a step the engine didn't bless.
3. **Coaching narrative.** Turn a topological plan into motivating, contextual prose: *"You're 5
   Strength levels and a Fire cape away — here's the fastest order, and why ranged beats melee here."*
4. **Goal decomposition from vague intent.** "I want to do raids" → disambiguate (CoX/ToB/ToA?
   realistic entry gear?) into **concrete KG goals** the engine then plans over.

## Guardrail + eval

The LLM is **grounded in engine output, not free-recall.** Its correctness target is **faithfulness**:
does its prose contradict the engine's computed plan? did it name a step/item the engine didn't
return? → again a LangSmith-shaped eval (LLM-as-judge "does this agree with the deterministic plan?"
+ a groundedness check that every entity mentioned resolves to a node the engine surfaced).

## Why this is the moat

RuneProfile mirrors *state* (no brain); RuneLite's Goal Tracker is *shallow* (no reasoning). A
deterministic engine that's correct *and* an LLM advisor that's fluent and grounded is **both**
trustworthy and conversational — the combination neither competitor has.

---

## Open questions / next threads

- **Prototype the determinism-first claim on Scurrius**: pull combat level / slot / drops from the **Bucket** API (`action=bucket`)
  *and* the game cache, reconcile, and show the freeform footnote as the one Tier-3 field. Small
  proof before writing the real pipeline. (largely DONE — implemented against Bucket in data-pipeline-v1.md §10).
- **Verify the wiki's actual structured surface**: which **Bucket** tables + API endpoints expose
  monster/item/drop/quest data; what `/Strategies` tables look like in raw wikitext. (Reconnaissance,
  not memory.) (ANSWERED by the recon update above — verified buckets: infobox_monster/item/bonuses, dropsline, recommended_equipment, item_id/npc_id/object_id).
- **Define the golden set** (`qa/core_set.yaml` from the schema) — initial members + verified values.
- **Define the engine's tool-use surface** for the advisor: `is_unlocked`, `prereqs_for`,
  `next_steps`, `expand_for_account`, `recommendations_for` — the function contract the LLM calls.
- **Pick the eval harness**: full LangSmith vs a lighter pytest + metrics table for the golden-set
  regression. Decide when (if ever) LangGraph orchestration is warranted for Tier 3.
- **Drift-detection cadence**: nightly re-query vs on-demand; how `oldid` diffs become review items.
