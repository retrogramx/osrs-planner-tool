# Achievement Diaries — Reward / Effect / Content-Node Layer (Design)

**Date:** 2026-06-23
**Goal:** Model the **Achievement Diaries** domain on the knowledge graph — the 48 region+tier completion units, their *full* reward sets (upgrade-ladder items, scaling XP lamps, tiered effects, extra unlocks), and a **queryable content-node layer** that maps each diary effect to the content it benefits (and back) — reusing the quest-foundation reward/edge taxonomy.

**Part of:** the foundation-audit roadmap. Diaries is brick #2 (after Quests). It reuses the taxonomy from `2026-06-21-quest-data-foundation-design.md` and is the first domain to populate the **content-node layer** (monster/activity/region instances + `effect → content` edges) the foundation has been missing.

**Depends on:** the quest-foundation brick (PR #15: `Edge.data`, `EdgeType.EFFECT` / `EdgeType.PROGRESS_TOWARDS` / `NodeKind.GOAL`, the `grants`/`effect` builders, the per-owner-cumulative re-keyer, `validate_quest_rewards.py` + `verify_quest_rewards.py`). The diary **build** lands after PR #15 merges (this branch is stacked on it); the spec stands alone.

---

## 1. Why this

The committed KG has 12 `diary` nodes referenced only as *requirement targets* of quests (the 8 mis-filed diary records). The Achievement Diary domain itself — 492 tasks, 48 tier rewards, the diary cape — is **not modeled at all**, and the diary rewards are exactly the **effect/perk layer** the route/recommendation layer (deferred Layer 2) needs ("do Morytania Hard — +50% Barrows runes helps your Barrows grind"). That sentence is unsayable today because:

1. there is no Achievement-Diary reward/effect data in the KG, and
2. there are **no content nodes** (no `Barrows`, no `Slayer Tower`) for an effect to point at, and `effect.target` was free-text in the quest brick.

This brick fixes both, for diaries, and establishes the **content-node + queryable-effect pattern** the later domains (Combat Achievements, Collection Log) and the route layer reuse.

**Non-negotiable discipline (carried from Quests):** every reward/effect datum is **source-grounded** against the *current* wiki diary pages, never from model memory or the existing prose strings alone. The game is living. A datum that cannot be sourced is left out and disclosed. Editorial values are gated by a committed verifier **and** owner review.

## 2. Structure

The diary domain is two-level; we model both, with the **tier as the completion + reward unit**:

- **48 tier nodes** — `NodeKind.DIARY`, one per region×tier (12 regions × {easy, medium, hard, elite}), id `diary:<region-slug>:<tier>` (e.g. `diary:morytania:hard`). Each tier's *completion* is gated by the existing engine `achievement_diary` atom (3-state, tier-level — the only diary-completion signal the Hiscores/plugins expose). This node is where the tier's rewards, effects, and cape-progress hang.
- **492 task requirements** — each tier's tasks (from `data/achievement_diaries.json`) materialize as the tier's **requirement detail**: a `requires` edge on the tier node whose `cond_group` is the AND of the tier's aggregate gates (the max skill level per skill across the tier's tasks, the union of quest prereqs, with each task's `boostable` honored) plus the per-task list retained in node `data` for "what's needed" detail. Per-*task* completion is plugin-only and is NOT an engine gate; the engine gates the tier via `achievement_diary`.

> Rationale: the rewards are per-tier; the tasks are the work to earn them. Tier-level matches what the engine can observe; the per-task list serves the route layer's "remaining tasks" view without inventing an observability the Hiscores doesn't have.

> **Reconcile existing diary nodes:** the committed KG already has a handful of `diary:<region>:<tier>` nodes minted as *supporting leaves* (referenced as requirement targets by quests, via `build_supporting`). This brick **promotes** those to first-class tier nodes (same ids, now carrying rewards/effects/data) rather than duplicating them — the assembler must dedup so a tier referenced by a quest *and* owned by the diary builder collapses to one node (the existing `dedup_nodes` raises on a content conflict, so the diary builder's definition becomes the canonical one and the supporting factory must yield to it for `diary:` ids).

## 3. Reward model (per tier — full capture)

Each tier `grants` a multiset, reusing the quest-foundation reward taxonomy. Across all 48 tiers the data confirms four recurring shapes:

### 3.1 Regional item — the upgrade ladder
Each tier grants its regional item (Ardougne cloak, Morytania legs, Desert amulet, Rada's blessing, …). These are **distinct items per tier** that **upgrade**: cloak 1 ≺ 2 ≺ 3 ≺ 4. Modeled as a `grants` edge (tier → `item:<id>`) **plus a new `supersedes` edge** (`item:ardougne-cloak-4 → item:ardougne-cloak-3 …`) capturing the ladder. `supersedes` is the §9-deferred socket from the quest spec, made real here.

### 3.2 XP lamp — per-tier values (NOT a fixed formula)
Every tier grants an antique lamp, modeled as a `grants` `xp` reward, `form: choice_lamp` (`{amount, count: 1, eligible_skills: "any", min_level (nullable), lamp_item}`). The *standard* ladder is 2,500 → 7,500 → 15,000 → 50,000 XP at min-level 30/40/50/70 — **but amount + min-level are captured per tier from the source, never hardcoded**, because **Karamja deviates** (wiki + data confirmed, 2026-06-23): Karamja easy = **1,000 XP, _any_ level** (a distinct `Antique lamp (Karamja Diary)` item, no min-level), medium = 5,000 @ 30, hard = 10,000 @ 40, elite = 50,000 @ 70 (standard). The other 11 regions follow the standard ladder — Karamja is the *only* deviation across all 48 tiers. Lamps are one-time per tier and **accumulate** (you collect all four) — they do NOT supersede. The verifier (§10) confirms each tier's amount/min-level against the wiki page so a future re-pull catches any further per-region quirks.

### 3.3 Effects — the bulk, tiered
The majority of diary rewards are passive perks. They map onto the §4 `effect` taxonomy with `effect_kind`:
- `rate_multiplier` — "2.5% → 5% → 7.5% → 10% more Slayer XP in the Slayer Tower", "50% more runes from the Barrows chest", "twice as many death runes".
- `recurring_resource` — daily teleports; "Robin exchanges 13/26/39 bones daily"; daily noted items.
- `capacity_change` — Pharaoh's sceptre 3→10→25→50→100 charges; skull sceptre 10→14→…→26.
- `behavior_toggle` — Bonecrusher auto-buries bones; **ghasts** ignore you (Morytania easy) and **ghasts** stop turning your food rotten (Morytania elite). *(Both are ghasts, not ghosts — corrected 2026-06-23.)*
- `fee_waiver`, `access` (shortcuts; Harmony Island herb patch).

**Item teleports are effects too** (a very common diary perk): a *daily-limited* teleport is `recurring_resource` (`{target_facet: place, qty: N, period: "day"}`); an *unlimited* teleport is `access`. They are **cumulative across the ladder** — e.g. Ardougne cloak 1 unlocks the *unlimited* Monastery teleport (`access`); cloak 2 then 3 add 3-then-5 *daily* teleports to the Ardougne farm patch (`recurring_resource`); cloak 4 makes that farm teleport *unlimited* (`access`). Each teleport effect's `dst` is the **destination** content node (the place reached), so "what teleports does the Ardougne cloak give / what reaches the farm patch" is queryable like any other effect (§4).

Each effect carries `magnitude` (the number, when numeric) tied to **`tier_source`** (the diary tier) — the 2.5→5→7.5→10% ladder is exactly `magnitude`-per-`tier_source`. Effects are **cumulative**: the elite item carries everything the lower tiers gave plus new perks; the supersedes ladder (§3.1) expresses that the higher item is the active one.

### 3.4 Extra unlocks beyond the regional item
Some tiers unlock additional items/abilities: **Bonecrusher** (Morytania Hard, "claimable from a ghost disciple"), and similar. Modeled as `grants` `items`/`unlock` rewards on the tier, with their own effects (the Bonecrusher's auto-bury is a `behavior_toggle` effect on `item:bonecrusher`, upgraded at Morytania Elite to full Prayer XP).

## 4. The effect → content queryable layer (the new value)

This is the brick's headline addition. An `effect` edge's **`dst` is the content node it benefits** — making the tier↔content relationship a plain graph traversal in both directions.

```
effect:  src = item:morytania-legs-3      dst = activity:barrows
         data = { effect_kind: "rate_multiplier", magnitude: 0.5,
                  target_facet: "runes from the chest",
                  tier_source: "morytania:hard", condition: "unconditional-once-earned" }
```

- **tier → content:** outgoing `effect` edges (from the tier's granted items/unlocks) → "Morytania Hard benefits Barrows, the Slayer Tower, …".
- **content → tiers:** incoming `effect` edges to `activity:barrows` → "Morytania Hard (+50% runes) benefits this".

**Content nodes** are created as a **bounded set** — only what the 48 tiers' effects actually target (~30–60), using the existing `NodeKind` instances that have zero rows today:
- `skill:*` (exist) — for XP-boost effects, the `dst` is the skill node; `data.target_facet` carries the location/method qualifier ("in the Slayer Tower").
- `activity:<slug>` — Barrows, Slayer Tower, Pyramid Plunder, Tears of Guthix, the Ectofuntus bone-exchange, etc. (new).
- `region:<slug>` — where the benefit is geographic (Harmony Island herb patch) (new).
- `monster:<slug>` — where an effect targets a specific monster (new, if any).
- `item:<id>` — where the effect rides on / modifies an item (sceptres, Bonecrusher).

The content nodes carry only `{id, kind, name, slug, data}`; their *facts* (drops, location) are out of scope here (future bricks) — this brick gives them existence + the `effect` edges that reference them. `data.target_facet` keeps the human-readable specificity that a bare node can't.

**Every referenced entity is a stable-id node — the KG principle (answering the review's §3.4 point).** This isn't new to diaries: the KG already mints stable ids for items (`item:<id>`), quests (`quest:<slug>`), skills (`skill:<slug>`), access, and goals; this brick extends the *same* discipline to activities/monsters/regions. The payoff is exactly crawl-/join-ability — any entity the data mentions becomes addressable, and **facts accrete onto it across later bricks.** The **Bonecrusher** illustrates the lifecycle: *here* it gets an `item` node + its Morytania-Hard `grants` edge + its auto-bury `effect`; its **charging** (25 charges per ecto-token) and its **upgrade to the bonecrusher necklace** (combined with a *dragonbone necklace* — a Vorkath drop — and a *hydra tail*) are **deferred facts** — the upgrade captured by `supersedes` (necklace ≻ bonecrusher), the full recipe by the §9-deferred `produces→consumes` layer. We model existence + the relationships now; the deeper per-item mechanics later, hung on the same stable id.

## 5. New schema pieces (everything else is reuse)

1. **`EdgeType.SUPERSEDES`** (`"supersedes"`) — the item upgrade ladder (§3.1). Direction: `src` supersedes `dst` (higher → lower). Inert to engine gating (like `effect`/`progress_towards`); a relationship for the upgrade/BiS reasoning the route layer will use.
2. **`AtomType.COUNT_SATISFIED`** (`"count_satisfied"`) — counts how many members of a referenced set (`data.set_ref`) are satisfied/done, compared to `threshold`. Powers **`goal:achievement-diary-cape`** (all 48 tiers). This is the roadmap-flagged member-count mechanism the quest brick deferred; evaluated in `conditions.py` against the set of `achievement_diary` tier-states.
3. **Content-node instances** — the schema kinds (`ACTIVITY`/`MONSTER`/`REGION`/`MINIGAME`) already exist; this brick adds the first instances + id helpers (`activity_id`, `region_id`, `monster_id`, `diary_tier_id`) in `kg_ingest/ids.py`.
4. **`effect` edge `dst`** — already permitted by the schema (`Edge.dst` is optional); the change is *using* it for the content node (the quest brick left effect `dst=None`).

No change to the engine's gating semantics: `supersedes` and `effect` remain inert to the prereq DAG; `count_satisfied` is a new atom evaluated where a goal's completion `requires` references it.

## 6. Completion goal

**`goal:achievement-diary-cape`** — `NodeKind.GOAL`, `data={counter_type: "member_count", thresholds: [48]}`. Its completion `requires` edge is `count_satisfied(set_ref = the 48 tier nodes' achievement_diary states) ≥ 48`. **Each tier feeds it via a `progress_towards` edge (`weight: 1`)** — so "how close am I to the diary cape" is the sum of completed tiers (answering the review's "do we capture progress toward the cape" — yes, this is it). It grants its own reward (the cape + perks) via a threshold-gated `grants` (§5.1 of the quest taxonomy). The base cape is **one** node (mirroring "Quest cape = QP cape, one node").

**Trimmed capes — the first cross-domain goal dependency (wiki/owner-confirmed 2026-06-23).** There are *trimmed* variants that cross-require the other domain's cape: **Achievement diary cape (t)** requires all 48 diaries **and** the Quest point cape; reciprocally **Quest point cape (t)** requires all quests **and** all 48 diaries. This brick adds `goal:achievement-diary-cape-t` (`NodeKind.GOAL`) with a `requires` edge on **both** `goal:achievement-diary-cape` *and* `goal:quest-point-cape`, plus a `supersedes` edge (trimmed ≻ untrimmed). This is the graph's first **cross-domain goal link (diaries ↔ quests)** — a small but meaningful proof that the foundation composes across bricks. The reciprocal `goal:quest-point-cape-t` is the quest domain's to own; this brick models the diary-side trimmed cape and discloses the reciprocal (so the quest brick, when revisited, adds its mirror).

## 7. Canonical source map

| Piece | Canonical source |
|---|---|
| Diary **tasks + requirements** (audit target) | `data/achievement_diaries.json` (492 tasks, validator-gated already) — re-verify the requirement gates against the per-region wiki diary pages |
| Diary **rewards** (items / lamps / effects / extra unlocks) | the 12 per-region wiki diary pages' **Rewards tables** (`<Region>_Diary?action=raw`) — the `reward` prose strings in `achievement_diaries.json` are a *starting point*, NOT truth (they may be imprecise, as the quest seed was) |
| Item **ids / stats / tradeable** | on-disk `data/items_equipment.json` — *reference*, don't re-derive |
| Effect **magnitudes / tier ladders** | the diary pages' reward bullets (the "2.5/5/7.5/10%" patterns) + the individual item pages (`Morytania_legs`, `Pharaoh's_sceptre`, `Bonecrusher`) for the precise mechanic |
| Content-node **identity** (Barrows, Slayer Tower, …) | the wiki page name for the activity/region/monster; this brick gives existence only, not facts |

## 8. Cross-domain reuse & contribution

- **Reuses** the quest-foundation taxonomy verbatim: `grants`/`effect`/`progress_towards` edges, threshold-gated grants, completion-goal nodes, the builder + assemble + re-keyer pattern, and the verifier pattern (`verify_*`).
- **Contributes** the **content-node layer** (activity/monster/region instances + `effect → content` edges) — the missing substrate the route/recommendation layer needs, and which **Combat Achievements** (effect-heavy, e.g. Ghommal's hilt → Barrows prayer-drain) and **Collection Log** reuse. CAs will point their effects at the *same* content nodes this brick creates (e.g. `activity:barrows`), so the set grows coherently.

## 9. Scope

**In:** the 48 tier nodes + their requirement gates (from the 492 tasks); the full reward capture per tier (item ladder + `supersedes`; scaling XP lamp; tiered effects; extra unlocks); the **bounded content-node set + queryable `effect → content` edges**; `goal:achievement-diary-cape` (with `count_satisfied`); a committed `data/diary_rewards.json` overlay + `data/diary_content_nodes.json`; the diary builder; `validate_diary_rewards.py` + `verify_diary_rewards.py` (source-grounding gate, diary analog of the quest verifier); reward-aware `validate_kg` coverage for the new pieces.

**Out (deferred):** content-node *facts* (drops/locations/the monster domain proper) — existence only here; the route/recommendation layer that *consumes* the `effect → content` map; Combat Achievements / Collection Log / Clue Scrolls (own bricks, reuse this); a `main`-account variant of anything iron-specific; per-task completion as an engine gate (plugin-only — kept as route detail).

## 10. Discipline / disclosed limitations

- **Source-grounded, never fabricated.** Rewards parsed from the *current* wiki diary pages with provenance; gated by `verify_diary_rewards.py` (source-token presence in the cached wiki rewards block) + owner review. The `achievement_diaries.json` prose is a starting point, re-verified against the live pages.
- **Full capture, but verified.** All 48 tiers (bounded), unlike the quest seed — *because* it's gated by the verifier + the diary corpus is small and each page has a clean rewards table.
- **Content nodes are existence-only.** This brick gives Barrows/Slayer-Tower/etc. nodes + the `effect` edges; their drops/locations/stats are explicitly out of scope (future monster/region bricks). `data.target_facet` preserves human specificity a bare node lacks.
- **Observability honesty.** Tier completion is the engine signal (`achievement_diary`); per-task completion is plugin-only and stays route detail, not an engine gate.
- **Effect target precision.** Some effects benefit a skill *scoped* to an activity ("Slayer XP **in the Slayer Tower**"); `dst` is the most specific content node (the activity), `data.target_facet` + an optional skill ref carry the rest. Disclosed where a single `dst` can't capture a compound benefit.

## 11. Phasing (for the plan)

1. **Structure** — `diary:` tier nodes + requirement gates from the 492 tasks (correctness re-verify vs wiki) + `goal:achievement-diary-cape` + `count_satisfied` atom + `progress_towards` from tiers.
2. **Rewards (items + lamps)** — the regional item ladder (`supersedes` edge) + scaling XP lamps; `data/diary_rewards.json` reward records (items/lamps) + builder + `validate_diary_rewards.py`.
3. **Effects + content nodes** — the `effect → content` layer: content-node set (`data/diary_content_nodes.json`) + `effect` edges with `dst` + tiered magnitude; the headline value layer.
4. **Verifier + integration** — `verify_diary_rewards.py` (source-grounding gate) + reward-aware `validate_kg` coverage + full 48-tier capture + owner review + byte-stable assemble.

## 12. References

- Quest-foundation taxonomy: `docs/superpowers/specs/2026-06-21-quest-data-foundation-design.md` (the reward/edge model reused here); its plan `docs/superpowers/plans/2026-06-22-quest-data-foundation.md`; `data/QUEST_REWARDS.md`.
- Data: `data/achievement_diaries.json` (492 tasks, 48 tiers), `data/items_equipment.json`.
- Schema lineage: `research/kg-schema-v1.md` (node kinds incl. `activity`/`monster`/`region`/`minigame`; the deferred `supersedes`/opinion layer; accumulator atoms).
- Memory: `[[foundation-audit-roadmap]]`, `[[verbatim-editorial-verification]]`, `[[step-back-and-audit-foundation]]`, `[[curated-route-edges-must-be-grounded]]`.
