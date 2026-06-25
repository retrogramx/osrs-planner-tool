<!-- Pass-3 (final): configurable-difficulty confirmation + LOCK declaration (2026-06-25). -->

# Configurable Difficulty — Final Survey Verdict (MUST-C lock pass)

## 1. Does `raid_level` generalize?

**No — not as proposed.** The pass-2 MUST-C model (`difficulty_config` holding `invocation_toggle` nodes summed into a continuous `raid_level` scalar) is the **ToA specialization**, not the general shape. Across all 6 systems surveyed, **zero** instantiate the toggle-sum substructure. "Configurable difficulty" is a small **FAMILY** of distinct mechanics.

What DOES generalize across all 6: the **core dual-coupling insight** — *one difficulty driver `scales_with` BOTH the encounter stat-block AND the reward rate*. What does NOT generalize: *how the driver is produced* (toggle-sum) and *that reward is a single monotone `rate = f(level)` multiplier* on a shared table.

### Breakdown (system → family member)

| System | Driver | Family type | Stat scaling | Reward scaling |
|---|---|---|---|---|
| **Vardorvis (Awakened)** | one consumable-gated boolean | `binary_toggle` | swapped stat-block + new mechanics + stat-drain immunity | rate jump 1/136→3/136 **+ variant-exclusive drop** (blood ornament kit, "last of four" gated) |
| **ToB Hard Mode** | party-wide boolean (locked at entry) | `binary_toggle` | +HP + **mechanic mutations** (not numeric deltas) | +15/+30% common, unique→1/7.7, **3 HM-exclusive drops**, points GO DOWN (non-monotonic) |
| **CoX Challenge Mode** | leader boolean | `binary_toggle` | flat **×1.5** all stats incl. HP (Olm hands/head exempt) | **indirect via points** (table unchanged) + time-threshold +5000pts → 2 CM cosmetics |
| **The Nightmare** | participant headcount (5–80, **emergent**) + Phosani's solo | `team_scaling` (+ `variant_instance`) | +200 shield/+30 totem **per player** | independent 2nd unique roll = clamp((party−5)%, 0, 75%) |
| **The Gauntlet / Corrupted** | elected variant enum, prereq-gated | `variant_instance` (binary) | two-point step-up (Crystalline→Corrupted Hunllef 1000 HP) | ~2.4× unique rates, +1 loot roll, guaranteed cape |
| **Doom of Mokhaiotl** | delve floor index 1–8 + deep delves | `floor_escalation` | piecewise HP bands per floor + per-floor mechanics | threshold/piecewise: gated uniques (delve 3/6/8), Qn=Q3+trunc(Q3·Mn) |

**Notably, the ToA-style `accumulating_draft` / `continuous_scalar` member that MUST-C was derived from did not appear in this 6-system sample at all** — it remains a *known* member (the model's origin), but this pass confirms it is **one leaf, not the trunk**.

Three structural facts the toggle-sum + monotone-rate model **cannot express**, surfaced repeatedly:
- **Variant-exclusive drops** (Vardorvis kit, ToB Sanguine/Holy, CoX cosmetics) — new table ROWS gated on difficulty, not a re-scale of existing rows.
- **Non-monotonic / indirect reward** (ToB points DOWN; CoX rewards flow through the existing points→loot pipeline, table literally unchanged).
- **Emergent (non-elected) driver** (Nightmare headcount is not a chosen input) and **piecewise/threshold** reward maps (Doom), neither of which is `rate = f(scalar)` linear.

---

## 2. Final MUST-C shape for the v2 spec

Generalize from "scalar" to **typed difficulty driver**, keep the `scales_with` fan-out, and express reward/encounter effects as **difficulty-conditioned atoms** (the real unifying primitive) rather than a single monotone multiplier.

### Unifying abstraction

```
difficulty_input  --scales_with-->  { encounter (stat-block / mechanic-set),
                                      reward (drop_table rows + rates) }
```

where `difficulty_input` is **one of**:
`binary_flag | toggle_set_summed_to_scalar | accumulating_draft | floor_counter | party_size`

and each `scales_with` edge carries its **own function** (constant-multiplier | additive-per-unit | piecewise/threshold | enum-lookup), not a single shared `f`.

### Nodes / edges / atoms to add (reuses requires+atom engine, no new evaluation primitive)

**Node — `difficulty_config`** attached to an encounter, carrying:
- `driver_kind` ∈ {`binary_flag`, `scalar_toggle_sum`, `accumulating_draft`, `floor_index`, `party_size`} (the family discriminator — `invocation_toggle` becomes ONE optional sub-structure under `scalar_toggle_sum`, not the base substrate)
- `elected: bool` — true for player-chosen (Vardorvis/ToB/CoX/Gauntlet/Doom), **false for emergent** (Nightmare headcount). Lets the planner DAG leave emergent drivers unspecified rather than forcing a chosen field.
- `selections` — enum members / scalar range / floor range.

**Edge — `scales_with`** from `difficulty_config` to:
1. the **encounter variant stat-block / mechanic-set** (allow a *swapped variant stat-block*, not just a numeric delta — required for Vardorvis/ToB/Gauntlet mechanic mutations), and
2. the **reified drop_table**, where the effect is **difficulty-conditional drop-table atoms**:
   - *re-rate* existing rows (Vardorvis 3/136, Gauntlet ~2.4×), AND/OR
   - *unlock new rows* gated by a difficulty atom (ToB Sanguine/Holy, Vardorvis kit, Doom Eye of Ayak @ delve≥3).

**Atoms (all plain requires+atom, no new engine):**
- `difficulty_state` atom — e.g. `awakened: true`, `challenge_mode: true`, `corrupted: true`, `delve_level ≥ 3`. These gate variant nodes and exclusive drop rows.
- **Access preconditions** as ordinary requires-atoms: consumable-in-inventory (Awakener's orb) + quest (`DT2 complete`); prereq-completion (`gauntlet_completed ≥ 1`); party-wide `≥1 normal completion`.
- **Indirect-reward routing:** when the game mediates via a score (CoX points), add an explicit `points`/scoring node and route reward effects through it — do **NOT** fabricate a direct `difficulty → drop_rate` edge where none exists (CoX table is unchanged).
- **Team/threshold values** as numeric-comparison atoms keyed on `party_size` (Nightmare +200/+30 per player, unique-roll clamp; CoX time thresholds + 5000pts/player).

### Two hard guardrails (from prior brick learnings)
- **Never fabricate the loot MECHANISM** (e.g. "3 rolls on upgraded table", RDT/GDT routing) as structured edges — record per-variant rates as flat observable drop-table facts (dropsline pattern).
- **Variant_instance** (Phosani's, Corrupted Gauntlet) is better modeled as a **sibling boss node sharing a requires-subtree** than as a toggle — the `difficulty_config` carries the prereq edge; the variant carries its own stat-block + drop_table.

---

## 3. New structural MUSTs surfaced (beyond MUST-C)?

Effectively **zero new primitives** — but the lock must record these **three refinements to MUST-C's shape** (they are corrections, not new requirements, and all reduce to atoms/edges already in the engine):

1. **Driver is typed, not assumed-scalar** (`driver_kind` discriminator; `elected` flag for emergent drivers). 
2. **Reward effect is difficulty-CONDITIONAL atoms** (re-rate ∪ unlock-new-rows ∪ route-through-score), not a single monotone `rate=f(level)` multiplier. 
3. **Encounter effect may be a swapped variant stat-block / mechanic-set**, not only a numeric stat delta.

No new node KIND beyond `difficulty_config`, no new edge TYPE beyond `scales_with`, **no new evaluation primitive** — the requires+atom engine covers every observed case via difficulty-conditioned atoms. **Saturated on primitives — lock.**

---

## 4. Lock declaration

**YES — structurally done.** Six independent self-imposed-difficulty systems spanning binary_toggle (×3), team_scaling, variant_instance, and floor_escalation all reduce to the single abstraction *typed `difficulty_input` —`scales_with`→ {encounter stat-block/mechanic-set, difficulty-conditioned drop_table atoms}* over the existing requires+atom engine. No system required a new primitive; the only deltas were the three shape refinements above. **The ontology is locked.**
