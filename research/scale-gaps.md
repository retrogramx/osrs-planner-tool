# v1 KG scale-readiness — gap analysis (scratch — NOT a decision)

> Output of a multi-source stress-test of the v1 KG schema (`kg-schema-v1.md`) against the breadth
> of real OSRS content. **Non-binding.** Companions: [`kg-schema-v1.md`](kg-schema-v1.md),
> [`data-pipeline-v1.md`](data-pipeline-v1.md), [`data-correctness-and-advisor.md`](data-correctness-and-advisor.md).
> Real decisions move into a plan/ADR per brick.

## Method

Stress-tested the v1 schema against hard real entities across 7 content domains (deep quests, the
access web, account-type acquisition, gear sets/charges, drops nuance, diaries/CAs, skilling/non-boss
goals), sourced **only** from three ground truths:

1. **OSRS Wiki** (mechanics + data shapes).
2. **quest-helper** (`Zoinkwiz/quest-helper`) — the battle-tested requirement/step vocabulary for every quest.
3. **shortest-path** (`Skretzo/shortest-path`, the maintained fork) — every transport in Gielinor with its requirement gating.

38 candidate gaps were each **adversarially verified** (a skeptic tried to refute each one by finding
the v1 escape hatch — `access:*` sink, `activity:*` node, conditional grant, `scope`, `data` JSON,
`verify` — that expresses it). 38 → 7 confirmed → **4 distinct survivors** after dedup.

## Headline verdict

**v1 scales structurally, but its atom vocabulary is incomplete.** The spine — access-sink
acyclicity (I1), the `requires_dag` closure + topo-order, AND-of-ORs condition trees, and the
buy-vs-acquire expansion policy — **held against the hardest content in the game** (the six-quest
fairy-ring access web): it stays acyclic, the closure/ordering claims pass, and the expansion policy
produces genuinely mode-divergent subgraphs from one shared graph. **None of the 4 gaps breaks an
invariant or the DDL spine** — all are *value/closure-faithfulness* failures in the schema's own
"structural validity ≠ factual correctness" regime.

The root cause is one limitation: every threshold atom is `progress[ref_node] >= constant` over **one
scalar account fact**, and the evaluator is a pure all/any/not fold. Four real OSRS quantity-shapes
fall outside that vocabulary.

## The 4 gaps

### G1 — No partial-completion state on the quest atom **(BLOCKER)**

Mid-quest progress gates need *quest at least partway through*, which a binary "completed" check and a
binary "started" check **bracket from opposite sides**. The flagship case: **fairy-ring access
needs Fairytale II partially completed** (the Fairy Godfather step reached — *not* finished). A bare
"completed" requirement false-negatives the huge population that stopped at the Fairy Godfather step;
a bare "started" requirement false-positives every early FT2 stage. Fairy rings underpin dozens of
downstream diaries/quests/boss routes, so the error **poisons the prereq closure graph-wide**.

- **Triangulated across all 3 sources:** quest-helper `VarbitRequirement(QUEST_FAIRYTALE_II_CURE_A_QUEEN, GREATER_EQUAL, 40)` (5+ sites + 4 medium diaries); shortest-path routes the same gate through its varbit-threshold column because its quest column is binary; wiki confirms partial completion.
- **Also resolves a live contradiction:** the pipeline already emits an in-progress quest reading (`data-pipeline-v1.md` §5 Job 1) that a binary-only schema **rejects** — a build-breaking drift. The correct fix is the 3-state generalization, not the boolean.
- **Fix (folded into v1):** model partial completion via the `quest` atom's `state` field ∈ `{not_started, in_progress, completed}` (an ORDERED enum; a requirement means "state ≥ the required value", and an account's quest may be at any of the three). The old wiki "Started:" convention maps to `in_progress`; a bare quest prereq means `completed`. This subsumes both the "completed" check (`state = completed`) and the "started" check (`state ≥ in_progress`). One field, no new operator, no spine change. Author `access:fairy-rings` via one conditional grant: `AND(quest(fairytale_2, in_progress), quest(× 5 precursors, completed))`.

### G2 — No cardinality / N-of-M atom **(important-soon)**

The Culinaromancer's Chest sells a glove tier keyed to the **count** of RFD subquests completed
(any order): "adamant gloves" == "any 6 of 8 subquests done". A faithful condition tree is an
`OR` of `C(8,6)=28` (up to `C(8,4)=70`) AND-clauses — combinatorially absurd and past the depth-3
cap. The access-sink hatch **can't count** (`OR(8 quest)` collapses to a boolean that forgets
*which* member satisfied it, so it can't demand a distinct second).

- **Defer-safe** because sub-quest structure is already deferred (the 8 RFD subquests aren't even nodes); the headline items (Barrows/dragon gloves) need the **full** quest, expressible *today* via `quest(quest:rfd, completed)`. Only the 7 intermediate count-gated tiers are lost.
- **Fix (documented, deferred w/ trigger):** add atom `count_satisfied(set_ref, n)` = "≥ n members of the named set are satisfied" (quest-helper's `Conditions(LogicType, Operation, quantity)` primitive). **Trigger:** when intermediate-tier / subquest acquisition routes are authored.

### G3 — No CA-points accumulator atom **(important-soon)**

Combat Achievement **tier rewards gate on accumulated points across any task mix**, not on completing
a tier (Ghommal's hilt 1–6 at 41/161/416/1064/1904/2630 points; DHCB(b/t) upgrades). The
`combat_achievement` atom is a per-*task* atom and is BINARY (a single task is completed or not — never
"in progress"); minting `ca:<tier>` + per-task membership is incoherent for tiers ("hard tier done" is
not a real OSRS state and the ingest layer can't populate it). A CA tier is reached via points from
ANY tasks, not by completing all of that tier's tasks. v1 mirrored the accumulator pattern for the
other two globals (boss KC → `kill_count`, quest points → `quest_points`) but omitted the CA-points twin.

- **Fix (documented, deferred w/ trigger):** add atom `combat_achievement_points{threshold}` (structural twin of `quest_points`, no `ref_node`). Keep the `combat_achievement` atom for per-*task* gates only; express all tier-reward gates via `combat_achievement_points`. **Trigger:** when CA-reward unlocks are authored. Needs the STATE layer to expose the CA-points total.

### G4 — No cost/currency model on acquisition **(important-soon)**

`expand_need_item` emits a `GpGoal(price)` only on the **GE** branch; the shop/quest_reward branches
recurse into prereqs with **no cost**. So for an ironman, "buy Barrows gloves" (130k coins; 104k with
Elite Lumbridge) and "buy full Void" (850 Pest Control commendation points) are **free** in the plan,
and `cheapest_method()` is a no-op stub for exactly the iron routes it's meant to rank. Commendation
points are an accumulating, capped, **spendable** currency no atom models.

- **shortest-path corroboration:** gp cost is real, **variable, and tiered** (it hacks it as `COINS=qty` pseudo-items with per-tier rows), and there is **no non-gp currency** in its model at all.
- **Fix (documented, deferred w/ trigger):** add a per-method `data.cost = {currency, amount}` (currency ∈ `coins | void_commendation | …`) on shop/quest_reward acquisition facts; emit a `GpGoal`/currency-goal accordingly; makes `cheapest_method()` real. **Trigger — hard blocker** the moment the planner makes its per-mode effort/cost pitch (the moat).

## Cross-cutting notes

- **Escape-hatch test:** the access/activity/conditional-grant hatches are genuinely powerful (they *passed* the multi-hop fairy-ring web), but for stage/cardinality/CA-points they only **relocate** the missing predicate — minting the node is trivial, but its grant's `cond_group` still needs a leaf the closed atom set lacks. "Resolves vs relocates" is the test that separated real gaps from noise.
- **STATE-layer dependency:** 3 of 4 fixes (the `quest` atom's `state` field, `combat_achievement_points`, `cost`) need the per-account STATE layer (a separate deferred brick) to expose the underlying readings (quest stage, CA-points total, currency balances). The KG-side atom additions are cheap now; useful once STATE lands.
- **Amend the load-bearing claim:** "depth ≤ 3 / two-level AND-of-ORs covers all real v1 reqs" → "covers all single-scalar and set-cardinality reqs via {the `quest` atom's 3-state `state` field, `count_satisfied`, `combat_achievement_points`}". Do this before graduating to a binding ADR.

## Recommendation

Land **the `quest` atom's 3-state `state` field now** (blocker + resolves the pipeline contradiction).
Document `count_satisfied`, `combat_achievement_points`, and generic `cost{currency, amount}` as
additive, spine-safe additions with the triggers above. Do **not** graduate the schema to a binding
plan/ADR until the `quest` atom's `state` field lands and the "covers all reqs" claim is amended.
