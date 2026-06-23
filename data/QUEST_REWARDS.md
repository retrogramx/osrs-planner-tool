# Quest Rewards — Format Reference & Cross-Domain Taxonomy

> **Scope:** `data/quest_rewards.json` + `data/completion_goals.json`.
> **Audience:** contributors expanding the seed + other-domain builders reusing this taxonomy.

---

## 1. `quest_rewards.json` Record Schema

Each record in `records[]` covers one quest's full reward set.

```json
{
  "quest": "<exact name matching data/quests.json>",
  "quest_points": <int>,
  "rewards": [ ... ],
  "effects": [ ... ],
  "source_urls": [ "<wiki page URL>" ]
}
```

### 1.1 `rewards[]` entry shapes

#### Fixed XP
```json
{ "reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750 }
```

#### Choice-lamp XP
```json
{
  "reward_type": "xp",
  "form": "choice_lamp",
  "amount": 4650,
  "count": 2,
  "eligible_skills": ["Agility", "Fletching", "Smithing", "Thieving"],
  "min_level": null
}
```
`eligible_skills` is either `"Any"` (string) or an array of skill names.
`count` is the number of lamps (player may pick the same skill multiple times).
`min_level` is the minimum skill level required to spend the lamp on that skill (`null` = none).

#### Special/scaling XP
```json
{ "reward_type": "xp", "form": "special", "amount": <int>, "note": "..." }
```
Not in the current seed — deferred (formula-based XP like While Guthix Sleeps).

#### Item reward (tradeable)
```json
{ "reward_type": "items", "item": "Amulet of accuracy", "item_id": 1478, "qty": 1, "tradeable": true }
```

#### Item reward (untradeable)
```json
{ "reward_type": "items", "item": "Barrows gloves", "item_id": 7462, "qty": 1, "tradeable": false }
```
`item_id` must resolve in `data/items_equipment.json`. `tradeable` must match that record.

#### Item reward with condition (§3.6)
```json
{
  "reward_type": "items",
  "item": "Ava's accumulator",
  "item_id": 10499,
  "qty": 1,
  "tradeable": false,
  "condition": { "type": "skill_level", "skill": "Ranged", "level": 50 }
}
```
Supported condition types:
- `{"type": "skill_level", "skill": S, "level": N}` → `ConditionAtom(SKILL_LEVEL, ref_node=skill_id(S), threshold=N)`
- `{"type": "item", "item_id": N, "qty": Q}` → `ConditionAtom(ITEM, ref_node=item_id(N), qty=Q)`

The builder emits a `ConditionGroup(AND, [atom])` and sets `cond_group` on the GRANTS edge.
Conditions are `≥` (threshold-gated); `< N` cannot be expressed in the current atom vocabulary
and is disclosed in `known_missing`.

#### Unlock
```json
{
  "reward_type": "unlock",
  "category": "<category>",
  "name": "<human-readable label>",
  "stage": "started | in_progress | completed",
  "access": "<access node slug>"
}
```
Valid categories: `skill`, `equipment`, `skilling-method`, `magic`, `spellbook`, `prayer`,
`location`, `area`, `transportation`, `guild`, `shortcut`, `monster`, `slayer`, `minigame`,
`shop`, `respawn-point`, `area-effect`.

`stage` is when the reward becomes available:
- `started` — available immediately after starting the quest
- `in_progress` — available at some partial-completion point
- `completed` — available only on quest completion

#### Cosmetic
```json
{ "reward_type": "cosmetic", "kind": "title | emote | music", "name": "Dräpare" }
```

### 1.2 `effects[]` entry shape

Effects ride on a GRANTED item (not on the quest itself). The EFFECT edge owner is
the item node.

```json
{
  "rides_on_item": "<item name>",
  "rides_on_item_id": <int>,
  "effect_kind": "rate_multiplier | behavior_toggle | stat_multiplier | fee_waiver | recurring_resource | capacity_change | access",
  "magnitude": <float | null>,
  "target": "<description>",
  "condition": "<prose — e.g. while-wielded>",
  "tier_source": "<quest that unlocks the effect>"
}
```

Set `"rides_on_external": true` if the item is not granted by THIS quest record
(avoids the validator's cross-check error).

---

## 2. `completion_goals.json` Record Schema

```json
{
  "id": "goal:<slug>",
  "name": "<display name>",
  "counter_type": "points | member_count | tier_count",
  "accumulator": "<field name summed across PROGRESS_TOWARDS edges>",
  "thresholds": [<int>, ...],
  "grants": { <single reward entry with reward_type etc.> },
  "note": "..."
}
```

`thresholds` is a list of milestone values. For the QP cape there is one threshold
(335 QP). `member_count` goals (music cape, diary cape) will have one threshold
equal to the total member count.

---

## 3. Reward Type → KG Edge Mapping

| `reward_type` | Edge type | `src` | `dst` | Notable `data` fields |
|---|---|---|---|---|
| `xp` (fixed) | `GRANTS` | `quest:<slug>` | `skill:<slug>` | `reward:"xp"`, `form:"fixed"`, `amount` |
| `xp` (choice_lamp) | `GRANTS` | `quest:<slug>` | `None` | `form:"choice_lamp"`, `eligible_skills`, `count`, `min_level` |
| `items` | `GRANTS` | `quest:<slug>` | `item:<id>` | `reward:"items"`, `qty`, `tradeable` |
| `unlock` | `GRANTS` | `quest:<slug>` | `access:<slug>` | `reward:"unlock"`, `category`, `stage` |
| `cosmetic` | `GRANTS` | `quest:<slug>` | `None` | `reward:"cosmetic"`, `kind`, `name` |
| `quest_points` (auto) | `PROGRESS_TOWARDS` | `quest:<slug>` | `goal:quest-point-cape` | `weight:<int>` |
| effects | `EFFECT` | `item:<id>` | `None` | `effect_kind`, `magnitude`, `target` |

Conditional rewards (§3.6) additionally populate `edge.cond_group` pointing to a
`ConditionGroup` in the `groups` dict (AND, one child atom).

---

## 4. Cross-Domain Reuse

The same taxonomy (`reward_type`, `category`, `stage`, `effect_kind`) is designed to
serve all major game reward domains without schema changes.

### 4.1 Achievement Diaries
- Diary reward records follow the identical shape: `unlock` entries for equipment,
  area, transportation, and guild rewards; `effect` entries for passive perks
  (e.g. Morytania legs prayer restore); `items` for tradeable items.
- Threshold-gated grants use the same `cond_group` / `ConditionGroup(AND, [QUEST atom])`
  path already exercised by Animal Magnetism's conditional accumulator.
- `stage` maps naturally: diary `"started"` (partial task completion grants) /
  `"completed"` (full-tier unlock) semantics.

### 4.2 Combat Achievements
- CAs map to `PROGRESS_TOWARDS` (each CA contributes 1+ `weight` toward a
  `goal:ca-<tier>` node with `counter_type: "points"`) for tier-unlock thresholds.
- Individual task rewards are `unlock` (`category: "equipment"`) or `cosmetic`
  (recolours, titles). Same `stage` enum.
- `effect` entries handle passive perks (e.g. Ghommal's hilt prayer-drain reduction
  in Barrows).

### 4.3 Collection Log
- `progress_towards` contributions to a `goal:clog-<category>` goal with
  `counter_type: "member_count"` drive the collection-log cape.
- Slot completion (obtaining an item) is the `DROPS` edge path, not a quest reward
  edge — but the goal node accumulator is the same design.
- The `_provenance.completeness.known_missing` field discloses that
  `count_satisfied`/`member_count` accumulators are not yet implemented in the
  engine (deferred to the collection-log domain task).

### 4.4 Clue Scrolls
- Clue-scroll tiers use `counter_type: "tier_count"` goals.
- `X Marks the Spot` (a beginner clue-scroll intro quest) is seeded here with its choice-lamp XP reward; modelling clue-scroll-box unlocks and tier-reward caps is deferred to the Clue Scrolls domain / full-corpus pass.
- Drop-table rewards from clues are modelled on the `DROPS` edge path (drop-rates brick).

---

## 5. Disclosed Limitations (§11)

| Limitation | Status |
|---|---|
| **Seed not full corpus.** 14 quests cover all taxonomy shapes but ~140 free quests and ~190 member quests are not in the seed. | Disclosed in `_provenance.completeness.known_missing`; follow-on sourcing plan. |
| **Per-quest shape sample, not exhaustive reward list.** Each included quest captures the reward shapes needed to exercise the taxonomy, not every reward the wiki lists. The included XP/item/QP/cosmetic/conditional values are verbatim-wiki-verified (2026-06-22 sweep; 1 fabrication found and removed — Demon Slayer's "Shadow of the Storm prerequisite" unlock, which is a quest prereq edge, not a reward). Per-quest completeness and unmodeled reward types (currency rewards such as Kudos and coins; misc-ability unlocks such as "ability to make a steak sandwich") are the full-corpus follow-on. | Disclosed in `_provenance.completeness.known_missing`. |
| **Editorial correctness is owner-gated.** The structural validator checks IDs and enum values but cannot verify that XP amounts / QP values are correct. | Owner review required before PR merge. |
| **Condition `< N` not expressible.** The `ConditionAtom` model only supports `≥ threshold`. Ava's attractor (Ranged < 50) is modelled as an unconditional fallback item. | Disclosed in `known_missing`. |
| **`special`/scaling XP deferred.** Quests with formula-based XP (While Guthix Sleeps Slayer, Observatory Quest constellation-random) are not in the seed. | Disclosed in `known_missing`. |
| **`count_satisfied`/`member_count` accumulators not implemented.** The engine's `evaluate` loop does not yet fold PROGRESS_TOWARDS edges for goals with `counter_type: "member_count"`. | Deferred to collection-log domain. |
| **Cross-builder edge-id risk.** `rekey()` discards builder-local ids and reindexes per-owner cumulatively, so two effects on one item get distinct global ids within the quest-rewards builder. The residual risk is an `effect` whose item node is also referenced by a goal-owned `requires` edge: goals and quest-rewards are re-keyed in separate passes, and a hash collision between the two passes could produce a duplicate global edge id. This is caught by `validate_kg`'s duplicate-edge-id guard, not silently dropped. | Currently no item appears in both a goal requires edge and a quest-rewards effect in the seed; safe. |
| **`choice_lamp` with `eligible_skills: "Any"` and `min_level: null` has no condition atom.** The lamp's skill eligibility is advisory metadata in `edge.data`, not a ConditionGroup. | By design — the player picks the skill at runtime, not the static KG. |

| **Quest-state vocabulary mapping.** `Started:` (Questreq source) → `in_progress` (engine vocabulary); the audit's 0-drift status reflects this corrected mapping. | Corrected in `data/raw/questreq_parse.py`; prior parser emitted `"started"` which mismatched committed `quests.json`. |

---

## 6. Validator Notes

- `data/validate_quest_rewards.py`: structural checks — `reward_type` enum, `item_id` resolution
  in `items_equipment.json`, `tradeable` field consistency, `effect_kind` enum, `stage` enum,
  `counter_type` enum, quest name resolution against `data/quests.json`. Does NOT check
  editorial correctness (XP amounts, QP values).
- `data/validate_kg.py`: KG graph invariants — checks for duplicate edge/node/group IDs,
  effect-collision detection, known-gap refs. Runs after `kg_ingest.assemble`.
- Both validators must exit 0 before merging changes to `data/quest_rewards.json`.

---

*Source: OSRS Wiki (CC BY-NC-SA 3.0). Accessed 2026-06-22.*

## 7. Source-Grounding Verifier

`data/verify_quest_rewards.py` is the **deterministic fabrication gate** for `quest_rewards.json`.

**What it checks:** For each seed reward, it confirms that a distinctive SOURCE TOKEN is present
(case-insensitive substring) in the quest's cached `==Rewards==` wiki block
(`data/raw/quest_reward_blocks.json`).  This catches rewards fabricated or misassigned to the
wrong wiki section — e.g. an unlock that appears under "Required for completing" instead of
"Rewards" is NOT in the extracted block and is flagged as a discrepancy.

**Token derivation by reward type:**
- `items` → item name
- `xp/fixed` → skill name + comma-formatted amount (e.g. "13,750")
- `xp/choice_lamp` → comma-formatted amount (e.g. "2,500")
- `unlock` → `access` field (or explicit `source_token` if set)
- `cosmetic` → cosmetic `name`
- `effect` → SKIPPED (rides on a granted item already token-checked)

**Escape hatch:** A reward dict may carry a `"source_token"` string to override token derivation
when the wiki phrasing doesn't textually match the derived field (e.g. `access = "Herblore skill"`
when the wiki says "ability to use the [[Herblore]] skill" → `source_token = "Herblore"`).
The source_token must still be a genuine substring of the rewards block.

**Output:**
- FATAL discrepancy: a required token is absent — exit 1 (gate fails)
- INFORMATIONAL missing-note: a wiki bullet line has no matching seed reward (seed intentionally
  omits many rewards per the shape-sample design) — printed but does NOT fail the gate

**Usage:**
```
./venv/bin/python data/verify_quest_rewards.py           # offline (uses committed cache)
./venv/bin/python data/verify_quest_rewards.py --refresh # re-fetches live wiki, rewrites cache
```

**Relationship to the LLM verbatim sweep:** This verifier is the repeatable deterministic gate
(token presence, offline). The periodic LLM verbatim sweep (performed manually) is the deep
semantic audit — it catches wrong amounts, incorrect conditions, and subtle misattributions that
a token-presence heuristic cannot. Both layers are complementary; this verifier runs on every
data change, the LLM sweep runs periodically or before major merges.

**Generalise when Diaries/CAs arrive:** The same pattern (committed cache of `==Rewards==` blocks
+ source_tokens derivation) should be extended per domain when Achievement Diary reward data and
Combat Achievement reward data are added.
