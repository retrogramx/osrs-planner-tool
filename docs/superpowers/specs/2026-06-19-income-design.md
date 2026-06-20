# Money-Making / Income Layer — Design (v1)

**Status:** design approved 2026-06-19; spec under review → implementation plan next.
**Brick:** `feat/income`. Builds on the merged goal-engine (PR #5), knowledge graph (PR #6), and cost overlay (PR #7).
**Companions:** `research/currency-model.md`, `research/wiki-source-catalog.md`, engine↔advisor contract (`docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`, §8/§13.3), cost overlay design (`docs/superpowers/specs/2026-06-19-cost-currency-design.md`).

---

## 1. Purpose & scope

The income layer is the **twin of the cost overlay**: where cost answers *"what does a goal cost and how do I acquire it cheapest, per account type,"* income answers **"how does this account EARN the gold?"** It is the §8 money-making method layer — the method layer for the *gold* currency, symmetric with XP-training methods.

**v1 delivers (the "Option 1" deliverable):** a standalone, account-aware **ranked method layer** — given an account, return money-making methods **ranked by gp/hr**, **filtered to what the account can do now** (future ones gated, not hidden), with **correct per-account-type income realization** (main = GE; ironman/uim = coins + High-Alch, *including the multi-step processing chain*). The public entry is `suggest_methods(state, …) → IncomeCard`.

**v1 is built Option-2-ready:** a later "shortfall-driven expansion" (a goal's gold cost minus the player's current gold → methods sized to cover the gap) is an *additive* layer — `suggest_methods` carries a wired-but-unused `current_gold` param, and the IncomeCard is structurally matched to the CostCard, so the hand-off needs no redesign.

**v1 does NOT:** drive off a goal's gold cost or the player's bank balance (Option 2 / bank ingest — deferred); rank by effort/time (xp/hr deferred); source the *bulk* recipe/service dataset (v1 hand-curates the exemplar processing chains); parse the iron dataset's prose gold figures; handle non-coin-currency income. All are designed-for but deferred (§9).

### Guiding principles (locked)
- **Engine = structure, income = overlay.** One-way dependency; the KG stays income-free.
- **Never auto-pick.** The card lists *all* viable methods, ranked; selection stays with the player/advisor ([[player-motivation-efficiency-fun]]).
- **Account-type realization is the load-bearing idea.** The wiki's gp/hr assumes a GE sale (a *main* number); an ironman realizes via High-Alch + coins, never the GE. This is **data**, not a runtime guess.
- **Never fabricate a rate.** When gp/hr is unknown/unpriceable, say so (`gp_hr_status = unknown`) — no invented number. Where v1 can't model a chain, it discloses rather than under/over-counts.
- **Absence ≠ zero.** An item requirement the account state can't confirm is UNKNOWN, not false.
- **Data correctness via committed validator + golden set** ([[feedback-data-validator-pattern]]).

---

## 2. Architecture

A new package `src/osrs_planner/income/`, sibling to `engine/` and `cost/`. `income` imports from `engine` (`AccountState`, `account_family`, the condition-evaluator) and reuses `cost.prices.PriceProvider`; **nothing imports `income`**, and the KG stays income-free. Same one-way boundary held by the engine and cost.

```
src/osrs_planner/income/
  methods.py    MethodRecord (frozen pydantic) + loaders normalizing the two
                datasets into one shape + the in-memory method index.
  realize.py    realize_income(method, family, provider, recipe_index) -> (gp_hr, gp_hr_status)
                — the per-family valuation walk (main=GE; iron=coins+High-Alch incl.
                the multi-step tan->craft->alch processing chain). Inverse of cost's price walk.
                recipe_index = data/recipes.json reverse-indexed (drop -> what it can become),
                built at load alongside the method index.
  filter.py     can-do-now / future-gated evaluation via the engine's requirement-evaluator.
  cards.py      IncomeCard + Method (pydantic output) + rank_by_gp_hr (descending).
  overlay.py    suggest_methods(state, provider, index, current_gold=None) -> IncomeCard.
```

- **Reuses verbatim:** `cost.prices.PriceProvider` (incl. `high_alch`), `engine.state.account_family`, the engine's condition-evaluator (single source of truth for "does this account meet this requirement"), the never-auto-pick card discipline, and the `validate_cost.py` validator pattern.
- **Why:** the structural twin of cost; the eventual shortfall hand-off lines up two matched cards.

---

## 3. Data model

One normalized **`MethodRecord`** (frozen pydantic) unifying both source datasets:

| field | source / meaning |
|---|---|
| `id`, `name`, `category`, `members` | both datasets (`id` = `method:<slug>`) |
| `audience`, `requires_ge`, `iron_eligible`, `realization_channel` | the iron-gate vocabulary (already on records) |
| `outputs[]` / `inputs[]` | structured `{item_id\|coins, qty_per_hour, is_coins}` — drives the runtime realization |
| `requirements` | `{skills:{skill:level}, quests:[…], items:[…]}` — **native** in the iron dataset; **parsed from `skill_requirements_html`** for the main dataset (a reproducible builder step) |
| `stage` | early/mid/late — a **soft hint only** (iron dataset; `None` for main). The requirement check, not this tag, decides doability |
| `tags` | `intensity`/afk, `risk`, `wilderness`, members — decision context |
| `processing_dependent` | bool — flags methods whose iron income needs a processing chain not yet covered (so v1 marks them honestly instead of under-counting) |
| `source` + `url` + `accessed_at` | attribution (the §8 opinion-edge requirement) |

**Sourcing:** the **377 structured methods in `data/money_making.json`** are the spine (realized per family at runtime); the **iron-native methods in `data/ironman_money_making.json`** (e.g. world-hop wines) fold in for coverage the main guide lacks, contributing their structured requirements + stage. gp/hr is **computed at query time** from `outputs × PriceProvider` (like cost prices at runtime) — *not* trusted from the stale stored value. **Earner vs sink** is computed (net of outputs − inputs); sinks (Managing Miscellania) are **flagged, not hidden, never ranked as income**.

---

## 4. Income realization (`realize.py`) — the per-family valuation walk

`realize_income(method, family, provider, recipes) -> (gp_hr, gp_hr_status)` — computed at query time, **coins-only**:

- **Value each output for the family.** Coins → face value (both). **main** → GE price × qty/hr (`provider.ge_price`). **ironman/uim** → the **best realization in coins**: `max(` High-Alch of the raw drop, **process-then-realize** `)`, where process-then-realize **walks the multi-step chain** for the drop (e.g. green dragonhide → **tan** [Tanner service fee] → leather → **craft** [Crafting level] → d'hide body → **High-Alch 4,680**), **subtracting internal costs** (tan fee, secondary inputs like thread) and **gated by the account's skills**. Non-gold drops (bones → Prayer) don't count as income.
- This is the **inverse of cost's recursive `price_routes`**: cost sums input costs *down* an acquisition chain; income walks a drop *up* a processing chain. It reuses `PriceProvider` and `data/recipes.json` **reverse-indexed** (drop → what it can become), plus a small **service-cost** datum (tanning).
- **minus method-level input cost** (e.g. nature runes for alching). v1 keeps iron input-handling simple and honest. **Clarification (post-review):** the iron-gate only excludes methods *flagged* `requires_ge` (GE-arbitrage); an iron-eligible combat method (e.g. green dragons) still carries consumable inputs (antifire, darts) that v1 values at the **GE price for every family**, including irons. This is the **SAFE direction** — charging an iron the GE price for a supply it actually gathers cheaper/free can only *lower* reported income, never inflate it — and is disclosed inline at `realize._coin_cost_of_input`. Per-family input acquisition (gather-time / iron shop) is a v2 follow-up; "already excluded" refers to GE-arbitrage methods, not to every GE-priced input.
- **`gp_hr_status`:** `known` when priced; **`unknown`** when an output can't be priced, a rate is null, or a `processing_dependent` chain isn't yet covered — *never an invented number*.

### Processing scope (v1 vs v2)
- **v1 builds the realization framework** (the multi-step tan→craft→alch walk with internal-cost subtraction + skill-gating + best-realization choice) AND **hand-curates the exemplar chains its golden set needs** (green dragons: the tanning fee + leather→body recipe + Crafting level) — so green dragons shows the *right* iron number and the machinery is proven.
- **v2** = **bulk recipe/service data sourcing** (all d'hide / bars / cooking / tanning fees, etc.) + broader coverage. Until a chain is covered, its method is `processing_dependent=true` and its iron `gp_hr_status=unknown` (disclosed, not under-counted).

---

## 5. The can-do-now filter (`filter.py`)

Per method, evaluate its **structured** requirements against `AccountState` via the **engine's condition-evaluator** (single source of truth — inherits boostable skills, quest 3-state, absence ≠ zero):

- **The requirement check is authoritative; the dataset `stage` tag is a soft hint only.**
- **Level/quest gates** resolve on real Hiscores data **now**. **Item gates** (e.g. Dragon hunter lance) are **UNKNOWN until the bank ingest** (not on the Hiscores) — shown "ownership unverified," never falsely doable (absence ≠ zero).
- Each method → `doable_now` · `future_gated(missing=[…])` · `unverified(items=[…])`. Future-gated methods are **shown and labeled, never hidden, never auto-pickable**.
- The main dataset's `skill_requirements_html` is **parsed into structured `{skills,quests,items}`** in a reproducible builder step so both datasets feed the same check.
- **Seam left open (deferred):** a gated *item* requirement can later expand through the KG/cost graph → "needs a Dragon hunter lance — a 95-Slayer Hydra drop, a late-game unlock."

---

## 6. Ranking + the `IncomeCard` (`cards.py`)

```
Method { id, name, category, members, gp_hr (coins-only, per family), gp_hr_status,
         realization_channel, requirements_status {met, missing[], unverified[]},
         tags {intensity/afk, risk, wilderness, stage_hint}, net_sign (earner|sink),
         outputs_summary, source + url + accessed_at }
IncomeCard { account_family, methods: [Method],
             rankings: { by_gp_hr: [indices…] }, notes }
```
- **`rank_by_gp_hr`** sorts **descending**; `unknown`-rate methods and **sinks** sort last (sinks flagged, never in the earner ranking) — mirrors cost's "unavailable last."
- **doable-now ranked above future-gated**; both present, both labeled.
- **Coins-only ranking** (same Tokkul-trap discipline — a method paying only a non-coin currency carries its amount but isn't gp-ranked).
- **Never names a single "best"** — lists all, ranks, lets the player/advisor choose.

---

## 7. The entry point + the Option-2 seam (`overlay.py`)

```
suggest_methods(state, provider, index, current_gold=None) -> IncomeCard
```
- "Given this account, here are the money-makers, ranked, realized for your type, filtered to what you can do now (+ future-gated)." A standalone query — no goal/target dependency.
- **`current_gold` is wired but unused in v1** — the Option-2 seam. Later, `shortfall = goal_gold_cost − current_gold` (from the cost overlay + bank balance) just *sizes* this same ranked list ("~N hours of method X covers it"), with no redesign.

---

## 8. Validation & proof

### 8.1 `data/validate_income.py` (committed validator, iron-gate tradition)
- Gate coherence: a `requires_ge` method is `iron_eligible=false` / main-only.
- Every output / input / requirement / recipe item id resolves in `item_dictionary.json`; quest refs resolve.
- `gp_hr` (where stored) ≥ 0 or null; realization-chain recipe refs resolve.
- KG stays income-free (no income/gp/method tokens leak into `kg/*.json`).
- Envelope consistency (`_provenance.record_count == len(records)`, `_excluded` is a list).
- The HTML-requirements parse is a reproducible builder step.

### 8.2 Golden income-set (hand-verified, over real data + `SnapshotPriceProvider`, values read at runtime)
1. **green dragons** — main (GE-realized) vs ironman (the **tan → craft → alch** multi-step realization) produce *different, correct* gp/hr; the iron number reflects the processing chain (the exemplar proving the framework).
2. a **main-only** method is **absent** from an ironman card. *(Implementation note: the spec's original exemplar "cleaning grimy ranarr" is not in the committed datasets, so the golden test asserts the same property with a constructed `requires_ge=True` main-only stand-in, "Grinding chocolate bars". The invariant proven — main-only present on the main card, absent from the iron card — is unchanged.)*
3. **future-gating** — rune dragons gated without Dragon Slayer II; a lance variant **unverified** without bank data.
4. a **sink** (Managing Miscellania) is **flagged, not ranked**.
5. **never-auto-pick** (no single "best"); a null-rate method shows `gp_hr_status = unknown`.

---

## 9. Deferred / skeleton (wired, empty — by design)

- **Option 2** (shortfall-driven expansion) + the cost-overlay hand-off — `current_gold` param wired.
- **Item-ownership / bank balance** (RuneLite ingest) — item gates stay UNKNOWN until then (absence ≠ zero).
- **Bulk recipe/service data** (all d'hide/bars/cooking/tanning fees) — v1 hand-curates the exemplar chains; v2 sources coverage.
- The iron dataset's **prose** gold figures (46/49) — not parsed; iron numbers come from the recompute over structured outputs; prose-only iron-native methods stay advisory.
- **Effort/time (xp/hr)**, **non-coin-currency income**, and write-back to `currencies.earn_rate_per_hour`.
- Richer **gated-item expansion** through the KG/cost graph (the lance "late-game unlock" labeling).
- `bosses_pvm.json` income (74 records, recompute-needed) and full `{gold, xp, resources}` multi-output accounting (v1 ranks on gold; xp/resources shown as context).

---

## 10. Success criteria

1. `suggest_methods(state, provider, index)` returns an `IncomeCard` listing the account's viable methods, ranked by gp/hr (descending), for the golden-set scenarios.
2. **Account-type realization holds on real data:** green dragons yields a different, correct gp/hr for a main (GE) vs an ironman (coins + High-Alch via the tan→craft→alch chain).
3. Main-only (GE-arbitrage) methods are absent from ironman cards; sinks are flagged, not ranked.
4. The can-do-now filter gates future methods (labeled, not hidden); item gates are UNKNOWN until bank data; never auto-picks.
5. `gp_hr_status=unknown` is surfaced honestly (no invented rate) for uncovered/processing-dependent methods.
6. `data/validate_income.py` exits 0; the KG stays income-free; `engine` does not import `income`; the full suite stays green.

---

## 11. Open questions / risks

- **Recipe/service data for the exemplar:** v1 must hand-curate the green-dragons chain accurately (tan fee, hides-per-body, Crafting level) — these are real OSRS figures to source from the wiki, not from memory. The plan should pin them from the wiki + the committed item data.
- **Requirements HTML parsing:** the main dataset's `skill_requirements_html` must parse robustly into `{skills,quests,items}`; coverage gaps should fail loud or mark the method `unverified`, never silently pass a method the account can't do.
- **iron_realizable_value (the stale field):** v1 recomputes from outputs and does NOT trust the existing `iron_realizable_value`; the recompute closes the tracked iron-income task. Disclose any residual coverage gaps (processing-dependent methods).
- **Two datasets, overlap:** methods appearing in both (green dragons, Wintertodt) must dedupe into one `MethodRecord` keyed by activity; the plan defines the merge rule (prefer structured iron requirements; realize per family at runtime).
