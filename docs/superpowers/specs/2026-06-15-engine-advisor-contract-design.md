# Engine ↔ Advisor Contract — Design Spec ("Step 3")

- **Date:** 2026-06-15
- **Status:** Draft for review (brainstorming output → spec; not yet a binding plan)
- **Companions:** [`research/kg-schema-v1.md`](../../../research/kg-schema-v1.md), [`research/data-correctness-and-advisor.md`](../../../research/data-correctness-and-advisor.md) (Part B = advisor intent), [`research/scale-gaps.md`](../../../research/scale-gaps.md), [`decisions/2026-06-13-0003-three-layer-architecture.md`](../../../decisions/2026-06-13-0003-three-layer-architecture.md), [`decisions/2026-06-13-0004-public-multi-account.md`](../../../decisions/2026-06-13-0004-public-multi-account.md)
- **Provenance:** Locked via brainstorming dialogue, then adversarially stress-tested (47 agents, 7 dimensions, 39 findings verified, 32 survived). This spec folds in the survivors.

---

## 0. Plain-English summary (read this first)

Gilded Tome has two "brains": a deterministic **Engine** (the careful librarian — reads the knowledge graph + your account, never guesses) and an LLM **Advisor** (the friendly guide — explains the WHY/HOW, but only ever repeats what the Engine handed it). This spec defines the **contract** between them: exactly what the Advisor (and the website) can ask the Engine, and exactly what comes back.

The stress-test confirmed the architecture is sound and that **none of the fixes touch the already-merged data schema** — they're all additive. The five things this spec pins down:

1. **A standard answer envelope** — every function returns `Ok` / `Empty` / `Problem`, so nothing crashes or guesses when a thing is missing, ambiguous, or impossible.
2. **"Can't-tell" instead of guessing** — when account data is unobservable, the Engine answers `indeterminate` (not a false "locked"), and the Advisor hedges.
3. **A sharper honesty system** — the runtime check now also catches wrong order, wrong numbers, wrong reasons, omitted required steps, and AND/OR confusion.
4. **Goal-tracker plumbing that's safe** — read/untrack/undo functions, idempotent writes, and a two-writer rule so a Hiscores sync never wipes manually-set facts.
5. **A real, vetted, credited method slot** — "how to do each step" is grounded opinion-layer data with attribution, only offered when the account can actually do it.

---

## 1. Purpose & scope

**Purpose.** Define the API surface between the deterministic Engine and its two consumers — the LLM Advisor and the FastAPI web app — such that the Advisor is *structurally* grounded (it can only speak about what the Engine returned) and the web app renders from the same shapes.

**In scope:** the function surface, the result/data shapes, the grounding & faithfulness mechanism, the method seam, mutation/state semantics *as contract guarantees*, the error contract, and the projection to LLM tool-schemas + HTTP.

**Out of scope (deferred bricks, but constrained here):** the per-account STATE layer's DDL implementation (`feat/goal-tracker`), the full method-content authoring, the G4 cost model authoring beyond the flagship set, and the ingest pipeline. Where this contract imposes binding constraints on a deferred brick, it says so explicitly (§9, §13).

---

## 2. Architecture recap

Three layers (ADR-0003): **ingest → static game-data KG → per-account SQLite STATE.**

- **Engine** = deterministic `networkx` traversal over the KG + a single account-state snapshot. No LLM. Source of truth is a **typed Python API**.
- **Advisor** = LLM. Its tools *are* the Engine functions (projected to JSON tool-schemas). It narrates Engine output; it never free-recalls OSRS facts.
- **Web app** = second consumer. The same Engine functions project to FastAPI HTTP endpoints; the UI renders the same cards.

> Determinism-first: the correctness-critical spine is LLM-free. LLMs touch only the two fuzzy boundaries — Tier-3 normalization on ingest (out of scope here) and advisor narration out (grounded, §7).

---

## 3. The function surface

The "mix" granularity: a few powerful calls + a few light lookups. **Every function returns `Result[T]` (§4).**

### 3.1 Reads
| Function | Returns (inside `Ok`) | Purpose |
|---|---|---|
| `is_unlocked(account, node)` | `UnlockCard` (status + blockers) | Can they do/access this yet? |
| `prereqs_for(account, node)` | `PlanCard` (ordered steps) | The full plan: everything needed, done/not, ordered. |
| `next_steps(account, node)` | `PlanCard` (frontier subset) | The immediately-doable items toward a goal. |
| `expand_for_account(account, node)` | `PlanCard` w/ `Expansion` leaves | Account-type-aware expansion (buy vs gather/make). |
| `compare_goals(account, node_a, node_b)` | `CompareCard` | Shared vs divergent prereq sets (top-3 user intent). |
| `unlocked_since(account, prev_state)` | `ChangeCard` | "What did I just unlock?" (two-state read). |
| `goals_for(account)` | `[GoalCard]` | The tracker view (the product's signature feature). |
| `suggest_goals(account, query?, kind_filter?)` | `[GoalCard]` | Suggested goals via the reachability filter. *(Renamed from the contract-layer `recommendations_for(account)` to avoid the name collision with the opinion-layer **gear** recommender `recommendations_for(target_id, style?, bracket?, account_state)` in `kg-schema-v1.md`.)* |

### 3.2 Intent resolution
| Function | Returns | Purpose |
|---|---|---|
| `search_nodes(query, account?, kind_filter?)` | `[NodeRef]` | Fuzzy text → candidate nodes (reachability-aware when `account` given). |
| `resolve_goal(query, account)` | `Resolved \| Ambiguous \| NotFound` | Pin a phrase to one goal node, or surface candidates. |

`resolve_goal` is a typed union (folded into the envelope): `Resolved{node_id}` → `Ok`; `Ambiguous[{node_id, one_line_disambiguator}]` → `Problem{kind: ambiguous, refs:[candidates]}`; `NotFound` → `Problem{kind: not_found}`. Disambiguators are sourced deterministically from the KG (node name + short prereq summary), never free-recalled.

### 3.3 Mutations (state/goal-tracker; defined here, implemented in the deferred brick)
| Function | Semantics |
|---|---|
| `add_goal(account, node, dry_run=False)` | Idempotent upsert to `status='active'`. `dry_run=True` returns the preview `PlanCard` **without writing**. Returns the resulting `GoalCard` (`created: bool`). |
| `track_goal(account, node)` | Insert/keep at `status='tracked'` (watchlist; not part of committed-plan ordering). |
| `untrack_goal(account, node)` | Remove from the watchlist. |
| `complete_goal(account, node)` | Manual progress assertion → writes the underlying fact into the overlay (see §9; achievement is **derived**, not a stored `done` flag). |
| `uncomplete_goal(account, node)` | Reverse the manual assertion. |

Every mutation returns the resulting `GoalCard` so the Advisor and the optimistic web UI re-sync from one source of truth.

---

## 4. The Result envelope (root fix)

**The single highest-leverage refinement.** Every Engine function returns:

```
Result[T] =
  | Ok{ card: T, refs: Refs }
  | Empty{ status: "ok", refs: Refs, reason: TerminalReason }
  | Problem{ kind: ProblemKind, refs: Refs, message: str }
```

- This **completes** decision #4 (the card already carried node refs; we add a status discriminant + a closed failure taxonomy). It generalizes the existing `expand_need_item` discriminated union (`GpGoal | AcquireVia | Unacquirable`) from one site to all functions × both consumers.
- **Erratum:** decision #2's bare-return wording (`is_unlocked -> bool+blockers`, etc.) now means *an envelope wrapping that payload*.
- **No function raises to the transport.** FastAPI maps `Problem` to a structured 4xx body (never a bare 500); the LLM tool-schema surfaces the same discriminated shape.

```
ProblemKind   = not_found | ambiguous | invalid_target | impossible_for_account
              | missing_state | unsatisfiable_cycle
TerminalReason = goal_complete | no_next_steps_all_done | no_recommendations | no_acquisition_route
```

`ProblemKind` is trimmed to what the Engine can actually return under the merged schema: `unsupported_mode` is dropped (I12 scope grammar prevents it); a `requires_dag` cycle is dropped (I1 FAILs the build before swap, so it can't reach runtime). `unsatisfiable_cycle` is retained **only** for the I15-excluded acquisition walk (§10).

**`Empty` is a success state, not a failure** — "you're already done," "no gear data yet," and "no route" are valid answers the Advisor must narrate correctly, distinct from genuine `Problem`s.

---

## 5. Core data shapes

All shapes are frozen dataclasses, JSON-serializable (no sets, tuples, or `networkx` objects leak across the boundary — serialize to lists/dicts).

### 5.1 Refs — the grounding leash (two lists)
```
Refs{ about: list[NodeId], mentions: list[NodeId] }
```
- `about` = the prereq/closure/claim nodes the card makes claims about — **the only list the web renders as the plan.**
- `mentions` = nodes referenced incidentally by a step's method/advisory slot (HOW context).
- The runtime grounding check (§7) requires: every node the Advisor names ∈ `about ∪ mentions`.

### 5.2 Step — ONE frozen type, reused everywhere
Reused identically by `prereqs_for`, `next_steps` (filtered to `blocked_by == []`, the *same instances* so the two can't drift), `recurse_plan`, and `Blocker.any_of`.

```
Step{
  step_id: str,                      # stable within a card; used for ordering
  node_id: str | None,               # None for ref-less atoms (qp_at_least, ca_points, combat_level, count_done)
  name: str,                         # engine-resolved (node.name or rendered atom gloss)
  kind: "skill"|"quest"|"access"|"item"|"currency"|"acquire"|"unacquirable"|"accumulator",
  metric: str | None,
  threshold: int | None,
  current: int | None,
  done: bool,
  blocked_by: list[str],             # UNMET predecessor step_ids (drives the next_steps frontier: doable iff == [])
  depends_on: list[str],             # ALL hard predecessor step_ids incl. already-done (drives the plan_order check) = requires edges + the selected OR-member
  source: "requires" | "cond_dep",   # grant-flips are cycle-only synthetics, never traversed
  set_ref: str | None,               # for count_done
  currency: { name: str, amount: int } | None,   # "gp" is sugar for currency=coins (scale-G4)
  method: list[NodeId],              # recommended_method carriers (see §8); [] = none
  advisory: list[NodeId],            # non-gating guidance carriers; [] = none
}
```

### 5.3 Blocker — preserve the OR/AND tree (do not flatten)
A flat list of node-ids would recreate the I16 false-AND bug at the contract boundary. Project the unmet-condition tree the `unmet_leaves` walk already produces, as a flat **AND-of-ORs** (matches the schema's amended depth-2 cap):

```
Blocker{
  any_of: list[Step],        # len==1 = a hard single req; len>1 = "do any one"
  cheapest_branch: bool,     # hint (see §13 for the v1 heuristic)
}
UnlockCard{ status: "unlocked"|"locked"|"indeterminate", blockers: list[Blocker], refs }
```
Each `Step` in a blocker carries its typed `reason` (the failing `atom_type`) and a `status: "satisfiable" | "impossible_for_mode"`. `impossible_for_mode` is set **only** by the Engine (never LLM-inferred) in two computable cases: (a) an item leaf where `expand_need_item` returned `Unacquirable`; (b) a branch whose only surviving alternatives were pruned by a false `account_type` atom.

### 5.4 PlanCard / GoalCard / CompareCard / ChangeCard
```
PlanCard{ goal: NodeId, steps: list[Step] (ordered), blockers: list[Blocker], refs }
GoalCard{ node_id, status: "tracked"|"active"|"paused", achieved: bool,   # achieved is DERIVED, not stored
          current: int | None, target: int | None, refs }
CompareCard{ shared: list[Step], only_a: list[Step], only_b: list[Step], refs }
ChangeCard{ newly_unlocked: list[NodeId], refs }
```
`GoalCard.achieved` is metric-aware (boolean goals: satisfied/total prereqs over the `requires_dag` closure; count/threshold goals: `clamp(current/target)` once the prereq gate is open, else 0 + locked — **not** prereq-fraction, which would read 100% at 0/100 KC).

### 5.5 Expansion — one frozen discriminated type
```
Expansion{
  outcome: "gp" | "acquire" | "unacquirable",     # the discriminator both consumers branch on
  item_id: str,
  method: "ge"|"drop"|"shop"|"quest_reward"|"skilling" | None,
  currency: { currency: str, amount: int } | None, # non-coin per scale-G4
  reason: str | None,                              # only when unacquirable
  gp: int | None,                                  # request-time-from-ingest, nullable
  gp_status: "known" | "unavailable" | "not_applicable",
  recurse_plan: list[Step],                        # ALWAYS a list (never None); lazy/bounded, see §13
}
```
Every node-id appearing anywhere in an `Expansion` enters the enclosing card's `refs` so the grounding check passes when the Advisor names a recursed sub-goal.

### 5.6 referenced_atoms — the scalar leash
Parallel to `refs`, each card carries the typed scalars the Engine actually read, so the grounding check can verify numbers (§7):
```
referenced_atoms: list[{ atom_type, ref_node: NodeId|None, threshold|qty|min_stage: int|None,
                         currency: str|None, amount: int|None, is_partial: bool }]
```
`is_partial` (for `quest_stage`: `min_stage < quest end-stage`) lets the check catch "fully complete FT2" when the real atom is a partial `stage >= 40`.

---

## 6. Account state & three-valued (Kleene) evaluation

**Problem:** a two-valued evaluator coerces absent data (unranked Hiscores skill, unobservable `quest_stage`/`ca_points`/currency) to `False`, producing a confident wrong "locked — go train X." This is the launch-common case for public accounts (ADR-0004).

**Fix (additive to the deferred STATE brick; revises no locked decision):**
- `AccountState` becomes **absence-aware** — an `observable_families` / presence set distinguishes *absent* from *zero*, derived from source per ADR-0004's public-vs-claimed split.
- Atom evaluation is **three-valued (Kleene)**: an absent-and-not-manually-asserted ref-bearing atom returns `UNKNOWN`, not `False`. AND/OR/NOT fold `UNKNOWN` and surface it **only when it flips the verdict**.
- `is_unlocked.status ∈ {unlocked, locked, indeterminate}`. `UNKNOWN` surfaces through the `blockers` slot as a distinct `cant_verify` blocker naming the missing-state node + the source needed to resolve it.
- A wholly-absent account → `Problem{kind: missing_state}`.
- The grounding check (§7) makes an `UNKNOWN` **force the Advisor to hedge** ("I can't verify X — confirm it or sync the plugin"), never assert a fabricated "locked."

Every read card also carries lightweight freshness: `source ∈ {hiscores, plugin, manual, inferred}` and `state_synced_at`, so the UI and Advisor can caveat staleness. (`inferred` back-fill — "level 85 ⇒ all level ≤ 85 atoms met" — is a documented later addition.)

**Manual confirmation (first-class, not an edge case).** The public Hiscores only rank players above a per-skill/per-boss popularity cutoff, so low levels, low boss KC, and small clue counts are routinely **unranked → unobservable**. `indeterminate` is therefore the *common* launch state, not a corner case. When the Engine returns a `cant_verify` blocker, the UI surfaces a one-tap *"confirm this value"* prompt; the answer is written as a `manual` fact — trusted per §9.3 and never clobbered by a later Hiscores sync (monotonic metrics still reconcile via `max(old,new)`, so a stale manual value can't hold back a higher synced one). The richest long-term fix is the companion RuneLite plugin (§9.6), which reads true in-game state the Hiscores cannot expose; manual input is the fallback for users without the plugin.

---

## 7. Grounding & faithfulness (the honesty system)

Three layers, matching the locked "spot-check + report card" decision, but extended past node-membership.

### 7.1 Structural (free)
The Advisor's tools *are* the Engine functions, so it can only ever see nodes the Engine returned.

### 7.2 Runtime spot-check (cheap, every reply)
The original check (named node ∈ returned set) is blind to six dimensions. All six are closed with deterministic, post-parse checks keyed off shapes the Engine already produces:

1. **Membership** — every node id the Advisor names ∈ `about ∪ mentions`.
2. **Order** — the Advisor emits a `plan_order` (a permutation of `step_id`s) beside its prose; an O(V+E) partial-order check rejects any step preceding a `depends_on`. `depends_on` = hard `requires` edges + the OR-member actually selected (unselected alternatives are **not** predecessors, to avoid false rejects). Scoped to closure-shaped cards (`prereqs_for`/`expand_for_account`); a no-op on the `next_steps` frontier.
3. **Scalars** — a number stated *as a requirement/threshold* for a referenced atom must match that atom's typed scalar in `referenced_atoms` (skill_level→threshold, has_item→qty, quest_stage→min_stage, …). Pass-through numbers (KC targets, GE prices, combat level 250) are allowed; a requirement-number with no matching atom = fabricated → reject.
4. **Omission** — every **required** step (`requires`, not optional `cond_dep` alternatives) in plan order must be named or explicitly counted by the Advisor, else regenerate.
5. **Connectives** — narrating AND across `any_of` alternatives (when "do any one" is correct) is rejected.
6. **Cross-turn staleness** — the grounded set = exactly the union of `refs` from cards returned by Engine tool calls **this turn**, rebuilt at the start of each user turn. No-tool-call turns that name a node fail closed (forced to call a tool first). A reference to an earlier entity must be re-resolved this turn and re-validated against the fresh set.

### 7.3 Offline LLM-as-judge (the "report card", CI only)
Extended beyond faithfulness scoring to the residual non-regex-able cases: OR/AND connective faithfulness, reason-match (stated reason == `blocker.reason` / recommendation basis), and "impossible_for_mode must be a hard wall, never paired with a buy suggestion."

### 7.4 Engine-level invariant
In the QA-invariant style of `kg-schema-v1.md`: **every Engine function returns a `Result`, and every `Result.refs ⊆ the set of nodes the Engine touched this turn.** This is the structural precondition both the spot-check and the offline judge rely on.

### 7.5 Advisor voice (objective, not chatty)
The projection to the user is **objective and terse — data-first**, never narrator-y. Two hard rules: **(a) no editorializing / marketing prose** (no "a grounded plan, every figure pulled live…" subtitles) — show the data and let it speak; **(b) never explain the player's own account restrictions back to them** — telling an ironman "(you buy this from a shop since you can't use the GE)" is redundant and reads as clueless/AI-generated. State the fact (item · source · cost), not the lecture. See [[objective-voice]].

---

## 8. Method seam (finalized)

The "recommended method" slot is the HOW (e.g. "train WC 1–15 on regular trees"). It must be grounded, vetted, and credited — not a free string the LLM fills.

- **Shape:** the step slot is `method: list[NodeId]`, populated by the Engine **only** from `recommended_method` edges returned this turn. Each projects to a card-side `Method{ node_id, text, source }`:
  - `node_id` — the attributed carrier; **must** appear in the card's `refs` so the spot-check covers any text/source the Advisor quotes. `None` ⇒ empty slot.
  - `text` — curated HOW prose from the opinion row's `data` JSON; `None` ⇒ link-only.
  - `source` — **projected** from the existing provenance side-table (`source_url` / `license` / `title` / `accessed_at` / `origin`), never re-stored inline.
  - Three states: **empty** (`node_id None`), **link-only** (`node_id`+`source`, `text None`), **curated** (all set).
- **Data backing (one new opinion edge, no new node kind):** methods reuse the existing `activity` node kind (e.g. `activity:train-wc-regular-trees`), linked by a new opinion edge type `recommended_method` added to the closed `edge.type` CHECK; endpoint matrix `activity(method) → skill`, optionally scoped by `data.level_range`/`cond_group` (WC 1–15). Extend I8/I9/I14 to recognize the method carrier so provenance-completeness stays a FAIL invariant for methods.
- **Account-type-aware method set + cost metric (the core differentiator).** A method node declares which **account types** it applies to (`applies_to`: e.g. `main`, the `ironman` family), and **cost is measured per account type**: for accounts that can use the Grand Exchange (mains) cost is **GP/XP** (gold per XP, from live GE prices + recipe inputs); for **restricted accounts (ironman family)** GP/XP is **suppressed entirely** — cost becomes **gather-time / effort**, because they can't buy inputs. Consequence: the *same* skill + target level returns a **different method list and a different cost framing** depending on the viewer's account type. (The two Crafting wiki pages prove this: the main page is a GP/XP gem-cutting table; the ironman page has *no* GP/XP and is built from quest XP + free/gathered methods like molten glass and Guardians of the Rift.) This is the heart of "account-type-aware."
- **Method labels (the at-a-glance funnel tags).** Each method carries a fixed label set so the player can choose by motivation: **`afk`**, **`group`**, **`solo`**, **`cheap`** / **`expensive`** (the account-type-relative cost axis above), **`low_req`** / **`high_req`**. The **efficiency vs fun** framing (§13.1) is *derived* from labels + rate + cost — not stored as a separate truth.
- **Method rates → computed effort.** Each method carries its **rate** (skilling `xp/hr` by level band; PVM `kc/hr`); the Engine divides remaining work by the rate to produce the per-account effort estimate (§13.3). Rate + cost + labels together are what let the Advisor say "⚡ fastest" vs "😎 chillest."
- **Quest XP rewards are first-class methods (optimal questing).** Early-game training is often *most efficient by doing quests in a specific order* — their XP rewards compound into levels far faster than slow low-level grinding, for mains and ironmen alike. A quest→skill **XP-reward** is therefore modeled as a method (additive edge; quest nodes already exist), and **"optimal quest order" is an account-type-specific strategy** (separate main vs ironman optimal-quest guides). This is what lets the Engine answer "reach 60 Attack" with *"do these quests, you barely grind at all."*
- **Money-making is the method layer for the *gold* currency — and income realization is account-type-dependent (the income twin of the cost split).** A gold shortfall is a **blocker that expands into money-making options** (catalog domain #10), filtered to what the account can do *now*, ranked by gp/hr, future ones gated. **Critically, the wiki's gp/hr usually assumes GE sale — that is a *main* number.** The Engine therefore stores each method's **outputs** (items/hr + direct coin drops) and **computes gp/hr per account type**: mains realize via **GE price**; **ironmen realize via High Alchemy (Magic 55, the most common iron GP sustain) + shop/coin value, net nature-rune cost** — and methods whose profit depends on **buying inputs or selling outputs on the GE are flagged `main_only`** (e.g. degriming herbs, tanning bought hides, flipping). High Alch is itself a first-class ironman GP layer over combat/skilling loot. This mirrors the `{gold, gather_time}` cost split exactly. See [[gold-cost-and-moneymaking]].
- **Each method carries decision-grade detail, not just a name + rate.** Required fields: recommended **gear/setup**, **stat/quest prereqs**, the **product** (what you actually collect — drops/items), and **how income is realized** (GE / alch / shop / direct coin). A method must answer "what am I doing, what do I need, what do I get, and how does it become gold/levels" — a bare "Zombie Pirates · ~1.77M/hr" is not enough.
- **Method coverage must be complete, including minigame & passive sources.** Beyond active click-methods, the DB must include **minigame methods** (e.g. Mahogany Homes — a top ironman Construction method) and **passive / over-real-time sources** (e.g. Managing Miscellania for hardwood logs & herbs, farming & birdhouse runs). A partial list reads as wrong to real players; completeness is a per-skill authoring requirement (`research/skill-rate-baseline-task.md`).
- **Income methods vs realization channels; methods are multi-output chains; rates must be honest.** Keep them distinct: **High Alch (Magic 55), NPC-shop sales, and direct coin drops are *channels*** (how value becomes coins) — never list them as money-making *methods*. An income *method* is what GENERATES value, and it is often a **multi-step chain with internal costs and multiple outputs** — e.g. green d'hide GP = kill green dragons (combat XP + dragon bones → Prayer) → collect hides → **tan (gold cost)** → craft bodies (**Crafting XP**) → High Alch (gold). The card shows the whole chain, its internal costs, and *all* outputs `{gold, xp, resources}`, and classifies each method by **net-gold sign** — earner vs **sink** (Managing Miscellania *costs* coffer gold to yield hardwood/herbs; it is a resource input, never "income"). And **rates must be honest and level-appropriate**: low-level Slayer is a poor *gold* source (supplies/XP/unlocks, not millions). When the verified gp/hr is low or unknown, the Engine says so — it never invents an "engine." **For ironmen, whether a combat method is *income* depends on whether its drops realize as coins** (alchable gear / direct coin drops) vs. kept gear or Prayer bones — e.g. **Dagannoth Kings = gear + Prayer, NO gold**, but **Zombie Pirates (~100–650k/hr), green dragons w/ lance (~496k/hr), Vorkath (~1.5M/hr) = real iron gold** via alchable drops + coins. Use the canonical **`Ironman money making guide`** wiki page (iron-correct methods + gp/hr by stage) — never guess from a main-account mental model. Iron GP is realized via High Alch / coin drops / shops (never GE); the **bank's High Alch value (§9.7)** is the spend-now figure. (Skilling minigames like Mahogany Homes are themselves net-gold *sinks* — they consume materials.)
- **Method/rate sources (AUDITED — see `research/wiki-source-catalog.md` + `.maps.json`):** the wiki's structured backbone is the **Bucket API** (official JSON query layer; replaces the now-deprecated `action=ask`) covering quests, items/equipment bonuses, money-making (incl. **kc/hr + gp/hr**), combat achievements, clues, minigames. The **`Module:Questreq/data`** Lua page is the full quest-prerequisite DAG (~1,900 entries, with `ironman`/`boostable` flags). **Live GE prices** come from the **`prices.runescape.wiki` API** (`/latest` + `/mapping`). The least-structured domains — skill **xp/hr** rates, optimal-quest order, diaries, unlocks/transport — are hand-authored wikitables/templates pulled via **`?action=raw`** and need partial hand-curation. **Account types are separate pages, not data fields**, mapping to a few families: **main**, **ironman** (HCIM & GIM reuse the Ironman guides — same skilling/method ruleset), and **UIM** (distinct, no-bank). So account-type-awareness = pick the right family; HCIM/GIM ride on ironman data. All CC BY-NC-SA, attributed per the bullet below.
- **Future-aware vetting (planning ahead is a feature, never a limit):** methods are shown for **every** step, including future steps the account cannot do yet — full forward planning is the whole point of the planner. The Engine runs the same unlock-check on each method node, but the result is a **label, not a filter**: a method whose own requirements aren't met yet (e.g. `activity:wintertodt` needing Firemaking 50 for a level-40 account) is shown **clearly gated** ("available once you reach Firemaking 50") or expanded into its own sub-steps — never hidden, and never presented as doable-right-now. This closes decision #6's hole (shipping a method as immediately-doable when it isn't) **without** suppressing the look-ahead the planner exists to provide. The gating is an Engine computation, not Advisor discretion.
- **Attribution/licensing:** because it's an opinion edge, I8 forces a provenance row (OSRS Wiki `Guide:`/`Strategies` or ironman.guide URL + CC BY-NC-SA 3.0 + `accessed_at`). The Advisor may quote only `Method.text`/`source.title`; the web renders `source.url` + license as a Sources credit, exactly like gear loadouts.
- **Advisory sibling:** non-gating guidance (e.g. Lost City's recommended ~45 combat vs its hard 31 Crafting / 36 Woodcutting requires-atoms) uses the schema's already-reserved `advisory` edge type via the step's `advisory` slot; advisory-referenced nodes land in `mentions`.
- **Empty-now / curated-later = how much HOW-TO *we've authored*, not what you can plan:** the full WHAT (every current *and* future step) works from day one. The detailed method coaching is filled in skill-by-skill over time; a step with no authored method yet still shows its WHAT, just without the rich how-to. Nothing is ever free-recalled — the Engine, not the LLM, populates these slots.

---

## 9. Mutations & state semantics

### 9.1 Lifecycle
`goal.status ∈ {tracked, active, paused}` (`archived` optional/deferred). **`done` is dropped from status** — achievement is **derived**, never stored.
- `add_goal` = upsert to `active` (creating, or promoting a `tracked` row in place — no dup).
- `track_goal` = insert/keep at `tracked` (watchlist; surfaces progress but is not part of committed-plan ordering).
- Promotion `tracked → active` = `add_goal` on the same key.
- `complete_goal` = the manual-achievement transition (writes the underlying fact into the overlay).

### 9.2 Idempotency
`UNIQUE(account_id, node_ref, metric)` on `goal`. `add_goal` is an upsert returning the existing id (`ON CONFLICT … DO UPDATE SET target=excluded.target, status='active' RETURNING id`), last-writer-wins on `target` (not `max()`, which would block a deliberate retarget-down). `complete_goal`/`track_goal` resolve by the same natural key.

### 9.3 Two-writer rule (the data-loss fix)
`complete_goal` and Hiscores/plugin `/sync` are two writers of the same truth. Resolution:
- **`account_progress` is the single source of truth** for "is this fact achieved"; reads derive from it. Every `GoalCard` gets a non-stored, engine-computed `achieved` evaluated at read time, so UI and Advisor read the same value.
- **DDL (recorded now, binding on `feat/goal-tracker`):** add a `source` column (`hiscores|plugin|manual|inferred`) and make the PK `(account_id, node_ref, metric, source)` so manual and synced facts coexist. Read-time precedence: `plugin > manual > hiscores > inferred`; `max(value)` for monotonic level/xp/kc/done; manual wins for plugin-only booleans Hiscores can't confirm.
- **`/sync` is a per-row UPSERT, never replace-all.** A Hiscores sync upserts only rows it can speak to (levels/xp/tracked kc) and never blanket-deletes plugin/manual rows. A narrow monotonic guard clamps a same-source Hiscores write to `max(old, new)` for monotonic metrics so a transient derank can't regress a passed level.

### 9.4 Concurrency
Per-turn snapshot: the Engine reads one consistent `AccountState` snapshot per advisor turn / per request. `/sync` runs in a single transaction so a mutation never observes a half-synced overlay.

### 9.5 `suggest_goals` exclusion
Exclude any node already `{tracked, active}` for the account. Read cards tag each referenced node with its per-account goal status so the web renders the watchlist distinctly and the Advisor can say "you're already tracking X."

### 9.6 Where account data comes from (refresh model)
"Achieved" is not a separate detector — every read recomputes it from `account_progress` (§9.3), so a goal flips to done **automatically** the moment fresher stats land. Stats reach `account_progress` three ways:
- **Public Hiscores** fetch — refreshable, but **leaves low levels / low boss KC / few clues UNRANKED** (§6), so it alone is insufficient.
- **Companion RuneLite plugin** — pushes true in-game state keyed to the account hash (RuneProfile-style). The **only** source that sees Hiscores-hidden facts, and the long-term answer to the §6 gap.
- **Manual** user confirmation (§6) — the fallback for users without the plugin.

A manual **"resync now"** action is always available. The exact auto-refresh **cadence** (plugin push on login/logout + periodic; Hiscores poll interval) is an ingest-layer decision in the deferred brick; RuneProfile's push-on-login-plus-periodic model is the reference. The two-writer reconciliation (§9.3) is what makes mixing these three sources safe.

### 9.7 Bank snapshot ingestion (RuneLite pusher) — researched, deferred-but-specified
Bank **contents** are a distinct account-state stream beyond levels/KC, and the biggest Hiscores blind spot. Research of two BSD-2 plugins ([[runelite-bank-data-ingestion]]) settles the path:
- **Capture:** a small Gilded Tome **"bank pusher"** RuneLite plugin reusing the battle-tested `onItemContainerChanged` + `BankSave.fromCurrentBank` capture logic from bank-memory / banked-experience (both **BSD-2**, attribution kept). Neither existing plugin pushes externally, so we POST ourselves.
- **Wire format (dumb client, authoritative server):** `POST /api/v1/accounts/{accountHash}/bank-snapshot` with `{accountHash, displayName, worldType, capturedAt, items:[{itemId, quantity}]}` — ids + quantities only; names / GE / HA values resolved **server-side** from our item DB + `prices.runescape.wiki`. Per-user token auth; debounce on item-list hash. Keyed on the **account hash** (matches ADR-0004 identity), with a separate RSN map.
- **Fallback (zero-install):** import bank-memory's clipboard **TSV** export (`Item id / Item name / Item quantity`).
- **Snapshots are point-in-time and versioned** — bank data is only as fresh as the player's last bank-open (a hard client limit). STATE stores/timestamps snapshots; reads never assume "current."
- **Derived, account-type-correct:** the server computes **GE value** (mains) and **High Alch value** (= the ironman realizable-gold figure, §8) from the snapshot; **banked XP** comes from a JSON transcription of banked-experience's `Activity.java` / `ExperienceItem.java` dataset (BSD-2, attribution). This lets the Engine **subtract banked materials from plan costs** and answer funding **from data**, not guesses.

This rides the §9.3 two-writer rule (`source='plugin'`) and is an ingest-layer brick; the contract pins the shape, the brick implements it.

---

## 10. Error contract

| Situation | Return |
|---|---|
| **Not found** (typo / non-existent id; guard `source ∈ dag` before `descendants()`) | `Problem{not_found, refs:[closest matches]}` |
| **Ambiguous** (`resolve_goal('raids')`, polysemous search, theme matching >1 top-level goal) | `Problem{ambiguous, refs:[candidates]}` + per-candidate KG-sourced `one_line_disambiguator` |
| **Impossible for account** | per-blocker `status='impossible_for_mode'` (from `Unacquirable` or all-mode-pruned OR-branch). `expand_for_account` returns top-level `Problem{impossible_for_account}` only when ALL leaves resolve impossible; else `Ok` with impossible leaves tagged. Advisor must verbalize as a hard wall, never paired with buy/acquire. |
| **Unsatisfiable cycle** (effective cycle in the I15-excluded acquisition graph during `expand_need_item`) | bounded by visited-set + depth cap → `Problem{unsatisfiable_cycle, refs:[cycle nodes]}` (reuses the `Unacquirable` card shape). Not reachable in `requires_dag` (I1-proven acyclic). |
| **Missing/partial state** | ref-bearing atoms over unobservable, not-manually-asserted families → `UNKNOWN` (Kleene) → `cant_verify` blocker; `is_unlocked` → `indeterminate` when it flips the verdict; wholly-absent account → `Problem{missing_state}`. Advisor hedges. |
| **Empty-but-valid** (all done, no opinion data, complete goal, no route) | `Empty{status:'ok', reason}` with `refs:[subject]`. |
| **Mutation: already tracked/active/done** | `Ok{created:false, card}` (idempotent, not an error). |
| **Mutation: non-goalable node** (metric-less skill atom, bare `access:*` sink) | `Problem{invalid_target, refs:[node]}` |
| **Mutation: node never tracked** (`complete`/`untrack`/`uncomplete`) | `Problem{not_found, refs:[node]}` |

**General:** no function raises to the transport; every `Result.refs ⊆ this-turn's touched nodes`; FastAPI maps `Problem` → structured 4xx; the LLM tool-schema surfaces the same discriminated shape.

---

## 11. Projection (Python → two consumers)

The typed Python API is the source of truth. A projection layer derives:
- **LLM tool-schemas** — each function → one JSON tool; `Result`/cards → JSON schema for the tool result. The Advisor's available tools are exactly the function surface (§3).
- **FastAPI endpoints** — each function → one HTTP route; `Ok`/`Empty` → 2xx with the card body; `Problem` → structured 4xx.

Both consumers branch on the same discriminators (`Result` status, `Expansion.outcome`, `resolve_goal` union). Shapes are validated JSON-serializable at the boundary (no `set`/`tuple`/`networkx` leaks).

---

## 12. Testing

Mirror the static `kg-schema-v1.md` invariant suite and the `data-pipeline-v1.md` §8 assertions, on the contract:
- **Engine invariant test:** every function returns a `Result`; every `Result.refs ⊆ touched-this-turn`.
- **State mutation suite** (twin of the static suite): a Hiscores sync after a plugin sync preserves plugin-only rows; a partial sync deletes nothing it didn't mention; `add_goal` twice yields one row; monotonic clamp holds.
- **Golden-set / CI faithfulness scenarios:** inverted `plan_order` rejected; fabricated threshold rejected; `impossible_for_mode` never paired with buy; multi-turn cross-turn bleed rejected; AND-narrated-across-OR rejected; `no_ge_step_for` / `contains_acquisition_for` plan-shape assertions (mirror data-pipeline §8).
- **Three-valued eval test:** an unobservable atom yields `indeterminate` + `cant_verify`, not a false `locked`.

---

## 13. v1 decisions on open questions

Sensible defaults chosen now (the user delegated these); each is a v1 choice to revisit, not a permanent commitment.

1. **`cheapest_branch` heuristic — and the never-auto-pick rule.** OSRS players choose between routes along **two motivations**: **efficiency** (fastest / most *compounding* — e.g. 70 Agility early for Graceful + diary/quest reqs, or multi-questing) and **fun** (the route the player enjoys, even if slower). The Engine therefore **never auto-selects** a route — it returns all branches as choices for the player to pick. v1 still computes a crude **`fewest_unmet_leaves`** hint, but it is explicitly a *proxy for efficiency only* (and an imperfect one — real efficiency is about long-term payoff, not step count). Cross-*kind* branches (a stat-leaf vs a set-acquisition branch) are `comparable=false` and never ranked. Real efficiency cost-weighting lands with G4 (§13.3); a future **efficiency/fun characterization** on methods (§8) lets the Advisor frame each route by the motivation it serves. The Advisor always presents routes neutrally and lets the player choose. *(See [[player-motivation-efficiency-fun]].)*
2. **`expand_for_account` recursion depth — and the two view modes.** The Engine call stays **lazy/bounded, depth cap = 1**: each call inlines the immediate sub-goal as a `Step` (its `node_id` enters `refs`); the consumer re-calls `expand_for_account` for deeper levels. The **same depth-1 contract powers two UI modes**: (a) the **default tap-to-drill-deeper tree** (one layer per tap), and (b) a **"full plan" checklist mode** where the consumer walks the whole tree via repeated depth-1 calls into one flattened, ordered to-do list from current state down to the goal. **Both modes expose per-step manual complete/uncomplete** — some steps can't be auto-observed and must be hand-checked — wired to `complete_goal` / `uncomplete_goal` and the §6 manual-confirmation path. No contract change: "expand-all" is just the consumer recursing on the same depth-1 call.
3. **G4 cost model — computed, broad-coverage at launch (Option B).** Cost/effort is **computed, not hand-authored per goal**: `effort(step) = remaining_work ÷ rate`. Rates live on **method nodes** (§8) — skilling methods carry an **xp/hr** (by level band), PVM methods carry a **kc/hr**; gold cost comes from **live GE prices** + recipe inputs **for accounts that can use the GE (mains)**. **Ironmen still incur real gold costs** — not via the GE, but via **NPC shops, services, and gold sinks** (e.g. sawmill plank fees + shop mats for Construction/POH, charters, run-energy restores) — *plus* **gather-time** for anything GE-only they must self-source. So cost is a **`{gold, gather_time}` pair for everyone**; only the gold *source* differs (GE for mains; shops/drops/sinks for ironmen). "GP/XP-via-GE" is the main-specific lens, **not** "ironmen have no gold cost." One rate populates every goal that uses that method, so "price the whole game" reduces to **populating the rate tables + a GE price feed** (a wiki-sourced ingest job), not authoring thousands of per-goal estimates. Source = the audited wiki backbone (`research/wiki-source-catalog.md`): Bucket API for boss/money-making **kc·hr / gp·hr**, `?action=raw` rate-chart templates + per-skill guides for **xp/hr**, `prices.runescape.wiki` for GE gold cost — **averaged and presented as rough ranges** with the assumed method shown (never implied exact). **Launch target = broad coverage**, but the **"effort not yet estimated" honest fallback** (the old flagship-only floor) is retained for any method/rate not yet ingested — missing data degrades gracefully, never blocks launch, never implies free. Because cost rides on the *method*, the same goal shows different effort under an **efficiency** method vs a **fun** method (§13.1) — so the cost model and the method seam (§8) are **one system**. Completeness check (sibling of C12): every expandable non-GE-route step resolves to either a computed cost (via a method rate) or an explicit not-estimated marker — **WARN on coverage gaps**, never silent.
4. **Observability authority.** ADR-0004 (public-multi-account) is the authority for which atom families each source (`hiscores`/`plugin`/`manual`/`inferred`) can observe; the per-family table the Kleene logic depends on is derived from it. *(Action: confirm/extend ADR-0004 with the explicit table.)*
5. **STATE-layer ownership split.** This contract **pins the API guarantees + the DDL constraints** (UNIQUE on `goal`, `source` column in the `account_progress` PK, the extended status enum, derived achievement). The `feat/goal-tracker` brick **implements** the DDL and inherits these as **binding, not advisory.**
6. **Granularity — "mix" headline + motivation-framed method options.** Settled and refined: each step answer is the clean **headline next-step** (the "mix" from §3) **plus a curated, account-type-aware set of method options framed by the funnel** (⚡ efficient / 😎 fun), each stamped with §8 labels and a computed rate/cost — *not* a single method (too thin) and *not* a firehose (every method dumped). Deep per-method detail stays one tap away. (This is "the mix of THE MIX and FIREHOSE" the user asked for.) See [[player-motivation-efficiency-fun]].
7. **`resolve_goal` confidence/tie rule.** Return `Resolved` iff exactly one candidate clears a high-confidence bar (exact slug/name match, or a single fuzzy match scoring a clear margin above the second). Otherwise `Ambiguous` with up to 5 candidates; `NotFound` if none clear the floor.
8. **`data.tags` theme search.** v1 ships `kind_filter` + the existing `is_boss=1` flag only (covers "I want to get into bossing" for free). Curated free-text theme tags (`'bossing'`, `'raid'`) with provenance are deferred.

---

## 14. Scope boundary

- **This brick (Step 3):** the function surface, `Result`/cards/`Step`/`Blocker`/`Expansion`/`Method` shapes, grounding mechanism, error contract, projection — as a typed Python API + its two projections.
- **Constrained-but-deferred:** the STATE-layer DDL (§9, `feat/goal-tracker`), full method-content authoring (§8), the G4 cost-model **rate-table + GE-price ingest** (§13.3 — now a broad-coverage launch target with a graceful "not-estimated" fallback, no longer flagship-only), `inferred` back-fill (§6).
- **Untouched:** the merged KG schema and DDL (all fixes here are additive — no spine/DDL/invariant change to the merged graph) and the ingest pipeline.

---

## 15. Verdict

The contract design **holds at the spine** — the locked surface, the typed-source-of-truth-with-two-projections form, the card-with-refs, the structural+runtime+offline grounding, the method seam, and account-type expansion are the right architecture. The fixes above are **additive completions**, not redesigns. The two true blockers to clear before implementation are the **`Result` envelope** (§4) and **partial/missing-state three-valued evaluation** (§6); everything else is important-but-additive.
