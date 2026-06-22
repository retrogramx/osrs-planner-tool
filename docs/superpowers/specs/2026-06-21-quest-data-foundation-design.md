# Quest Data Foundation — Correctness Audit + Reward/Edge Taxonomy (Design)

**Date:** 2026-06-21
**Goal:** Make the **Quests** layer of the knowledge graph *correct* and *complete* from the ground up — audit our quest **requirements** against the canonical wiki source, and build the **reward/value layer** the KG is missing — establishing a **domain-agnostic reward/edge taxonomy** that the later foundation bricks (Achievement Diaries → Combat Achievements → Collection Logs → Clue Scrolls) reuse.

**Part of:** the foundation-audit roadmap. Quests is brick #1; the taxonomy defined here is the shared model for all five domains. The progression-route layer (Layer 2) is paused and resumes once the foundation is solid.

---

## 1. Why this

The committed KG is **requirements-only**: 212 `requires` edges, **0 reward edges**, no `diary`/`combat_achievement` nodes, no completion goals (`"Quest Point"` is the `skill:quest-point` pseudo-skill, not a cape). Consequences proven during brainstorming:

- A reward-only quest (e.g. *The Ribbiting Tale of a Lily Pad Labour Dispute*) is in the graph but **unmotivated** — the graph can say "you *can* do it" but never "*why*" (its XP/items/unlocks) or "you need it for the Quest cape." A requirements-only graph can't express value or completion.
- A curated route built on this foundation **fabricated its connective edges** (the held route-layer slice). Layer 2 computes on Layer 1; bad/missing facts propagate. So we verify the ground before building higher.

This brick fixes both: **correctness** (are our requirement arrows right?) and **completeness** (the reward/value layer + the edge types that express it).

**Non-negotiable discipline (the lesson of this session):** every datum is **source-grounded** against the current wiki, never from model memory. The game is *living* — content is added, reworked, and **removed** (Great Kourend favour was removed; my memory still "had" it). Source-grounding + a live player in the loop are both required; neither alone suffices.

## 2. The two axes

1. **Correctness** — diff our committed quest `prereqs` + `skill_reqs` (`data/quests.json`, 213 records → 205 KG nodes) against the canonical **`Module:Questreq/data`** (requirements-only; ~270 main + ~30 miniquests + ~19 diaries). It's a structured-vs-structured **programmatic diff**: flag missing quests, wrong requirements, missing `ironman`/`boostable` flags. Measure the error rate; fix mismatches; add missing quests/miniquests. Evidence-first — the diff tells us how shaky (or solid) the requirement spine is.
2. **Completeness** — build the **reward/value layer** (§3–§6): what each quest *grants*, the edge types that express it, and the completion goals it feeds. Neither our data nor `Questreq` carries rewards, so this is a genuine new build sourced from the wiki reward pages (§7).

## 3. The reward taxonomy (the shared core)

A quest (later: a diary tier, a CA, a clue tier) **grants a multiset** of typed rewards. The reward **types**:

### 3.1 `quest_points` — `int`
QP granted. Feeds `progress_towards goal:quest-point-cape` *and* is read by `requires` on QP-gated quests (one currency, two readers — a progress meter and a gate). The Quest cape **is** the QP cape — one node (`goal:quest-point-cape`), not two.

### 3.2 `xp` — skill experience, three forms
- **fixed** — `{skill, amount}` (Waterfall-style direct XP).
- **choice-lamp** — `{amount, count, eligible_skills, min_level}` — a lamp/book the player applies to a chosen eligible skill. `count` ≥ 1 (the *same* lamp can be awarded N independent times, re-chosen each time — DT2). `eligible_skills` + `min_level` capture the flexibility (what later lets the route layer *route lamps*).
- **special** — `{kind: scaling|random, formula}` — scaling (store the formula, e.g. `15 × level`, not a fixed number) or random amount. (See §3.7 for random across *types*.)

The "huge XP for low effort" efficiency judgment is **derived** (XP ÷ effort), not a hand-picked subset — so we never miss one.

### 3.3 `items` — concrete items
`{item, qty, tradeable, members, condition?, choice_group?}`. `item` **references `items_equipment.json`** for stats / equip-requirements / value (thin overlay — we never re-derive). Kinds: weapon / armour / tool / misc / coins / gem. `tradeable` matters for the iron lens (untradeable = the only source). `condition` / `choice_group` per §3.6.

### 3.4 `unlocks` — categorised, stage-tagged
Categories follow the wiki **`Unlockable content`** page: `skill` (a whole skill becomes trainable — Druidic Ritual→Herblore, Pandemonium→Sailing) · `equipment` · `skilling-method` (a training/earning method within a skill, incl. repeatable-XP facilities like Biohazard combat dummies) · `magic`/`spellbook` · `prayer` · `location`/`area` · `transportation` (references `unlocks_transport.json`) · `guild` · `shortcut` (doors/passages) · `monster`/`slayer` · `minigame` · `shop` · `respawn-point` (display-only) · `area-effect`. Each unlock carries a **stage** (`started` | `in_progress` | `completed`) read straight from the `Unlockable content` table, which already tags partial unlocks ("Started X" / "Partial completion of X"). The `skill` unlock is high-fan-out: until it fires, the entire skill subtree is unreachable (level pinned at 1).

### 3.5 `cosmetics`
`emote | music-track | title | decorative | animation-override`. Feeds `goal:music-cape` etc.

### 3.6 conditional & choice mechanics
- **conditional** — a reward gated on player state at completion; **model the condition** (e.g. "Ava's accumulator *requires* Ranged ≥ 50", or RFD "skip the Icefiend fight *if you own Ice gloves*" — the condition predicate vocabulary admits skill-level, quest-stage, **and item-possession** atoms).
- **choice** — pick-one from a set. Three shapes: simple pick-one (`items.choice_group`); choice-lamp (eligible-set + floor, §3.2); and **split-allocation** ("35k to the chosen pair, 20k to the *un*chosen pair" — MM1) — the choice selects who gets the primary amount, with defined non-zero amounts for the others.

### 3.7 random-outcome bundle
A reward may be a **weighted set of possible reward multisets**, each of which can be xp, items, or empty (Observatory: some constellations give no XP). Random lives at the *bundle* level, not nested under `xp`.

## 4. `effect` (the generalised `boost`) — cross-cutting

An **effect** is a permanent/passive perk that **rides on** a reward (an item *or* an unlock) — it is **not** a reward type sitting beside items/unlocks, and **not** an item subtype. It is an attribute on the granting reward, so it can attach to an item (Magic Secateurs, while wielded) *or* a non-item unlock (Morytania Hard diary's +50% Barrows runes, unconditional once earned).

```
effect = {
  effect_kind: stat_multiplier(#) | rate_multiplier(#, activity_scope) | capacity_change(from,to)
            | fee_waiver | behavior_toggle | recurring_resource(item, qty, period) | access,
  target,                # the activity/skill/content the effect applies to
  magnitude,             # the NUMBER when numeric (+10% herb, +50% runes) — captured, per owner
  condition,             # while-wielded | while-worn | unconditional-once-earned
  own_requires?,         # an effect may be inert until a gate is met (Desert Elite shortcut needs 86 Agility)
  tier_source            # which tier/source grants this magnitude (diary tiers escalate the %)
}
```

`effect_kind` must be an enum, **not just a number**: diary/CA rewards are *dominated* by non-numeric passive perks — noting drops (`behavior_toggle`), fee waivers, capacity caps (`capacity_change`), daily resource faucets (`recurring_resource`). Hard-coding `magnitude=number` would leave the dominant diary/CA reward kind homeless. The `magnitude` number is captured when the effect is numeric, **tied to its `tier_source`** (a higher diary tier ups the %). Same shape Diaries and CAs reuse (Ghommal's hilt 2 → negate Barrows prayer-drain is a `behavior_toggle`).

## 5. Edges (the relationship set)

| Edge | Meaning |
|---|---|
| `requires` | **Access gate** — binary; AND/OR condition tree; quest-stage 3-state; `ironman`/`boostable` flags. "Can you start it?" (already built) |
| `grants` | **A reward** (§3). **Stage-qualified** (fires at `started`/`in_progress`/`completed`). May be **threshold-gated** (§5.1). |
| `effect` (`boosts`) | An `effect` (§4) attached to a granted item/unlock. |
| `progress_towards` | **Counting contribution** toward a goal — a **weight** on the edge + a **threshold** on the goal node (§6). "How close are you?" |

`requires` and `progress_towards` are the two halves of progression — **gating** vs **accumulating**. The current KG has only the first.

### 5.1 Threshold-gated grants (the keystone gap the critic found)
A `grants` edge may be conditioned on a `cond_group` whose leaf is an **accumulator atom** (`combat_achievement_points` / `clue_scrolls` / `quest_points` / `count_satisfied`), firing when the threshold is crossed. This is the **grant-side twin of `progress_towards`** (which is only the read side). Without it, **tier rewards have no legal source node** — CA tier unlocks (Ghommal's hilt at N points), the diary cape, clue tier-reward unlocks, and RFD's glove tiers (each sub-quest a partial-stage grant bumping the chest tier bronze→…→Barrows gloves). This is the single biggest structural addition and it is mostly *for the domains ahead*.

## 6. Completion goal nodes

First-class nodes that aggregate "complete all/enough of X" and **also grant their own rewards** (two-way: `progress_towards` in, `grants` out — the Quest cape requires-by-counting all quests *and* grants its teleport/perk).

`goal:quest-point-cape` · `goal:music-cape` · `goal:diary-cape` · `goal:ca-tiers` · `goal:clue-tier-rewards` · `goal:clog`.

Each goal node carries `{counter_type, thresholds[]}`:
- `points` — summable weights (QP per quest; CA points per task); CA-tiers is **one** accumulator with **six** nested thresholds.
- `member_count` — **distinct** membership cardinality (music/clog/diary-cape) — distinctness enforced so 600× one track ≠ a 600-track cape.
- `tier_count` — completions counted per tier (clue tiers).

The contribution **weight** is read from the source's tier/QP value (default `1`). **Collection-log** goal progress is fed by **`DROPS`** facts (mode-resolved obtainment), **not** `grants` — a clog slot is filled by obtaining an item; there is no per-slot reward, only the threshold-crossing cape. (Authoring note in the spec so no one models clog slots as grants.)

## 7. Canonical source map

| Piece | Canonical source |
|---|---|
| Quest **requirements** (audit target) | `Module:Questreq/data` (reqs-only; `quests` + `skills` with `ironman`/`boostable`) |
| Quest **XP** rewards (fixed / choice-lamp / special) | `Quest experience rewards` (+ `(F2P)` variant) — has the `Members` column, eligible-skill / level-floor data, the scaling/random footnotes |
| Quest **item** rewards | `Quest item rewards` (grouped weapons/armour/misc/cosmetics/coins/tradeable; conditional + "or" footnotes) |
| Quest **unlocks** + **partial-stage** | `Unlockable content` — structured `Content \| Members \| Unlocked-by`, 19 categories, tags `Started`/`Partial`/full. Cross-domain (also lists diary/equipment unlocks). |
| Item **equip-reqs / stats / value / tradeable** | on-disk `data/items_equipment.json` (4,298 items; `requirements{skills,quests}`) — *reference*, don't re-derive (also gets its own audit) |
| **Transport** unlocks | on-disk `data/unlocks_transport.json` — *reference* |

The in-game **skill guides** are *not* pulled for Quests (item-wield levels are already in `items_equipment.json`); they're earmarked for the future **Skills** brick (non-item level unlocks). Every reward record carries a **`members`** flag (F2P-lens; defaults from `items_equipment` for items).

## 8. Cross-domain reuse (the taxonomy is the point)

The same taxonomy serves the next bricks — verified by the cross-domain stress test:
- **Achievement Diaries / Combat Achievements** — already **task-granular in the data** (492 diary + 637 CA tasks exist in `data/`; not yet materialised in the committed KG). Each task is a node with `requires` + (via §5.1) accumulator-gated tier `grants`. Diary/CA rewards lean heavily on `effect` (§4) and tiered `effect.magnitude`.
- **Collection Log** — `progress_towards goal:clog` fed by `DROPS`; member_count threshold.
- **Clue Scrolls** — completing N caskets of a tier → tier-reward unlock = `progress_towards` (tier_count) + threshold-gated `grants` (§5.1). This is the owner's original clue mechanic, falling straight out of the model.

## 9. Deferred sockets (named now, not built here)

- `prepares-for` — the Layer-2 editorial route edge (the held route layer).
- `supersedes` / upgrades (BiS/tier ladder) — a real item-domain relationship (`item B better-than A in slot/role`); none of our four edges express it. Backlog to the items domain, not quest rewards.
- `produces → consumes` (recipe chains) — the cost/income recipe layer; the *consumption* side of assemblies is already `requires (component items)`.
- method-gating (`unlocks-method`'s "no progress on skill X until this") — the fact half is the §3.4 `skill` unlock; the editorial gating stays socketed in the route layer.
- `respawn-point` / `animation-override` sub-kinds — display-only; fold only if trivial.

## 10. Scope

**In:** the quest-requirement **correctness audit** (diff vs canonical, fix/add); the **reward/edge taxonomy** (§3–§6) defined as the shared model; the **quest reward data build** (source the reward pages into committed data + the new edges/goal-nodes for quests); a **committed validator** (every reward `item`/`unlock`/effect references a real node/source; thresholds well-formed; no fabricated edges); the cross-domain taxonomy documentation.

**Out (own sub-projects / deferred):** the other four domains' *data builds* (Diaries/CAs/Clogs/Clues reuse this taxonomy under their own specs); the Skills/level-unlock layer; the Layer-2 route layer; the `supersedes` / `produces→consumes` edges; the audit of `items_equipment.json` / `unlocks_transport.json` (referenced now, verified when their domain comes up).

### 10.1 Dimensional coverage (the 5 W's)

A completeness lens — the model checked against the questions players actually ask. Each dimension is assigned the **layer that owns it**, not stamped onto every node:

| W | Where it lives | Status |
|---|---|---|
| **What** — content + its rewards | nodes + reward types (§3) | covered |
| **Why** — value / motivation | `grants` · `effect` · completion goals (§3–§6); editorial `prepares-for` (Layer 2) | covered (this brick) |
| **Who** — the account | account-type overlay + live `AccountState` + the `members` flag | covered |
| **When** — timing | quest-*stage* (`started`/`in_progress`/`completed`) covered here; account-*lifecycle* stage → Layer 2; game-*version*/recency (the favour-removal problem) → re-pull discipline (§11) | partial; deferrals named |
| **Where** — geography | `location`/`transportation` unlock categories + `unlocks_transport.json`; **no spatial model** (regions, distances, travel-batching) | deferred — future spatial brick + the route layer |

Discipline: each W lives in its owning layer; we do **not** force a five-field structure onto every node, nor model geography before a feature needs it (YAGNI). The lens confirms What/Why/Who are solid and makes the `Where` + account-stage-`When` deferrals explicit, on the record.

## 11. Disclosed limitations / discipline

- **Source-grounded, never fabricated.** Reward/edge data is parsed from the canonical pages (§7), with provenance, and gated by a committed validator. Model memory proposes structure; sources dispose of specifics. A reward we cannot source is left out and disclosed, not invented.
- **Living game.** Sourced against the *current* wiki; a re-pull is needed when content changes (the favour-removal lesson). The owner (live player) is a required reviewer of editorial/mechanical claims a structural validator cannot check.
- **Reference, don't duplicate.** Item stats/reqs/values (`items_equipment.json`) and transport (`unlocks_transport.json`) are referenced; the reward overlay stays thin.

## 12. References

- Sources: `Module:Questreq/data`, `Quest experience rewards` (+ F2P), `Quest item rewards`, `Unlockable content`; on-disk `data/items_equipment.json`, `data/unlocks_transport.json`, `data/quests.json` (213 records), `data/achievement_diaries.json` (492 tasks), `data/combat_achievements.json` (637 tasks).
- Brainstorming grounding: the two reward-taxonomy workflows this session (edge re-grounding; completeness-critic — confirmed the 4-edge set is sound, surfaced threshold-gated grants + the `effect` generalisation as the two structural gaps).
- Schema lineage: `research/kg-schema-v1.md` (the 5-fact-edge spine incl. `GRANTS`/`DROPS` + the deferred opinion layer; accumulator atoms; v1-CORE task nodes), the committed-validator pattern (`data/validate_iron_gate.py`).
- Memory: `[[foundation-audit-roadmap]]`, `[[curated-route-edges-must-be-grounded]]`, `[[step-back-and-audit-foundation]]`, `[[method-rate-data-sources]]`.
