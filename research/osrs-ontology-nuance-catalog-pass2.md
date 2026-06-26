<!-- Pass-2: targeted survey over 15 UNCOVERED domains + saturation verdict (2026-06-25). -->

# Pass-2 Net-New Report + Saturation Verdict

## 1. Saturation verdict

**NOT YET SATURATED — but close. 3 genuinely-new structural MUSTs survive scrutiny (consolidated from 4 claims). A third pass is justified, narrowly scoped to the new axes below.**

Of the four `has-new-must` claims, I demote one and merge two:

- **Leagues `game_mode`/ruleset overlay** → **survives** (genuinely new scope dimension).
- **Random-events `elapsed_time_trigger`** and **Group-Ironman `time_window` lifetime** → **survive, but are ONE underlying gap**: wall-clock / real-time as a first-class axis (a free-running clock that accrues offline). Count as **one** structural MUST with two faces (a *trigger* face and a *lifetime* face).
- **ToA `raid_level` / Invocations continuous difficulty scalar** → **survives, weakly**. It is on the edge of P12+P5, but the player-elected, summed-continuous-scalar-that-drives-BOTH-NPC-stats-AND-drop-rate is not cleanly expressible as a flat rate-modifier. Kept as a MUST but flagged as the softest of the three.

**Count of distinct new structural MUSTs: 3.** That clears the "3+ ⇒ third pass justified" bar. The third pass should be *targeted* (configurable-difficulty activities, real-time/offline mechanics, and alternate game-modes) rather than a broad re-survey — the rest of the catalog is demonstrably saturated (12 of 15 domains mapped cleanly, see §4).

---

## 2. Genuinely-new structural patterns (new-MUST)

### MUST-A — `game_mode` / ruleset overlay scope (distinct from `account_type`)
**What:** A whole-mode seasonal overlay (Leagues / Trailblazer / Shattered Relics) that swaps the *global ruleset* under which the entire content graph is evaluated: no trading, blank-slate start, separate economy + separate Hiscores, seasonal (~8wk) lifetime, selective persistence (pets/cosmetics carry over, stats/items do not).
**Domain(s):** Leagues. (Group Ironman's account-family variants do *not* count here — those are `account_type` extensions already covered by K5.)
**Why not covered:** P7 `rule_zone` is a *sub-region of one world*; this reinterprets `account_type`, the economy id, which nodes exist, and which leaderboard applies — for the *whole graph at once*. Nothing in P1–P14 or the MUST list carries a global ruleset axis. Missing it forces re-threading every account-type/economy/ingest assumption to bolt on a "league" dimension later = a re-ingest.
**Recommended model:** Add a `game_mode` scope alongside `account_type` in the evaluation context, parameterizing `{trading_allowed, economy_id, content_lifetime=seasonal, hiscores/leaderboard_id}`. Reuses the requires+atom engine (atoms gate on `game_mode == X` the same way they gate on `account_type`); no new evaluation machinery, just a new context dimension. A `leaderboard` node kind rides along for placement-based ("League Firsts"/trophy-by-rank) rewards.

### MUST-B — real-time / wall-clock axis: scheduled-spawn TRIGGER + `time_window` LIFETIME (offline-accruing)
**What:** A free-running real-time clock as both (i) a *trigger* — random events fire after a random in-game-time window, checked on a schedule, with the clock persisting/accruing **while offline**; the antecedent is "time elapsed in an eligible state," not an action-count or stat-threshold; and (ii) a *lifetime* — Group-Ironman trade caps that ramp on a Week-1→Week-5 schedule keyed to *real elapsed weeks since a per-account event* (join date), and the 7-day leave/kick grace window.
**Domain(s):** Random events (trigger face); Group Ironman (lifetime face — weekly trade-cap ramp, grace periods, 30-day leader-inactivity succession).
**Why not covered:** P11 counters are action/event accumulators (killcount/streak); P6 lifetimes are exactly `{permanent, session, location}`. Neither expresses a wall-clock that advances independently of player action and **continues offline**, nor a lifetime anchored to a real-date event with a ramping schedule. A model with only action-counters and stat-thresholds literally cannot state "random event fires" or "trade cap = f(weeks since join)". Missing it makes random events unrepresentable and the GIM trade-cap model structurally wrong → re-ingest of the lifetime-tag vocabulary.
**Recommended model:** Add (1) a `lifetime` kind `time_window` = `{anchor_event, schedule_table}` to the existing scope/lifetime modifier; and (2) an `elapsed_time_trigger` atom/edge (`subject=self`, clock persists offline) plus a `random_event` node kind whose existence is gated by the trigger + zone-eligibility `rule_zone` (P7) rather than by stat/quest/counter prereqs. Both reuse the requires+atom spine — the new thing is the *clock as an antecedent source*, not new graph topology.

### MUST-C — configurable-difficulty scalar (`raid_level` / invocation set) driving BOTH encounter stats AND reward rate
**What:** A player-ELECTED bundle of difficulty toggles (invocations), each worth +N raid levels, *summed* into a continuous `raid_level` scalar (0–600) chosen before the run, that simultaneously scales NPC stat-blocks (HP/def/acc/dmg) AND the unique-drop rate (per-item, piecewise-interpolated, re-weighted every 5 levels). Fortis Colosseum's per-wave drafted-and-accumulating modifier stack is the same family (self-imposed escalating-difficulty draft).
**Domain(s):** Tombs of Amascut (invocations); Fortis Colosseum (wave-modifier draft — though Colosseum's drop-rate is wave-keyed, *not* modifier-keyed, so its modifiers are the softer P6 case).
**Why not covered:** P12's rate-modifier slot expects a flat/discrete multiplier from an existing node (diary/ring); P6 conditionals are *imposed* (on-task, in-region). Neither models a *player-chosen, additive set of toggles whose SUM is a continuous input axis* feeding a `rate = f(raid_level)` function on the drop_table AND the NPC stat-block at once. The reward edge can't express "rate is a function of a chosen scalar" with current booleans/flat rates.
**Recommended model:** New node kind `difficulty_config` (the invocation set) holding `invocation_toggle` nodes carrying `{raid_level_delta, mutually_exclusive_group}`; a `scales_with` edge linking the `raid_level` scalar to both the drop_table rate-modifier and the NPC stat-block; the drop_table gains a scalar input param so per-member weight becomes a table/function over `raid_level`. This is the **softest** MUST — if a third pass finds no other configurable-difficulty system, it could be down-graded to a parameterized P12 rate-modifier with a chosen-scalar input. Worth confirming against one more configurable activity before locking.

---

## 3. New NICE additions (additive-later, non-structural)

- **`mutually_exclusive_with` / `choice_group`** — pick-exactly-one-of-N, permanent, over reward-shop options (Leagues relic tiers, invocation categories). Layers on P5.
- **`rank_threshold`** — reward gated by relative leaderboard placement, not absolute count (League trophies/Firsts).
- **`stack_capacity`** — per-tier inventory cap raised by quest gate + consumable +1 items (clue scroll boxes).
- **`use_gate`** edge + `individual_prestige` / `group_prestige` / `group_lives` / `group_storage_capacity` team-state atoms (Group Ironman) — all expressible via P11 counters + subject:team + aggregate_count once `time_window` (MUST-B) exists.
- **`ship_facility_built`** atom — gate keyed on "player's ship has facility X built" (Sailing); rides requires+gate=access + existing `facility` node.
- **`spellbook_active` / `accept_aid` / `npc_dialogue_unlock` / `cooldown(duration)` / `spec_bar_full`** atoms (Lunar spells) — all reuse P1 member-of + P2 charge-state + P6 lifetime.
- **Multi-currency cost map** (Mastering Mixology: mox/aga/lye paid together) — generalize the P4 reward-shop cost edge from scalar to `{currency→amount}` map.
- **`encounter_resource`** node (Wintertodt warmth gauge) — bounded bidirectional gauge; collapses to a `survive` gate for the engine; only needed if encounters are ever simulated.
- **Counter `aggregation` field** = `max` (personal-best, e.g. Colosseum Glory) vs `sum` — a field on the P11 counter, not a new kind.
- **Boostable enum** `{not_boostable, boost_at_acquire, boost_at_use}` (Sailing build-vs-use boost asymmetry) — finer value on the existing boostable modifier.
- **`reclaim_source` edge + cosmetic `metamorphosis`/`forms[]` + cat lifecycle (P2)** (Pets) — defer-safe metadata.
- **Action-keyed XP payload** `{build:x, repair:y}` + `completion_bonus_xp` (Mahogany Homes) — payload enrichment of P13.
- **Choosable-target + level-scaled-amount** reward-payload fields (random-event XP lamps / Book of Knowledge) — additive on P12 reified reward.
- **`account_property`** predicate (Jagex-account/bank-PIN/members on event availability) — likely already subsumed by existing account-conditional machinery.

---

## 4. Confirmations (catalog generalizes — 12 of 15 domains clean)

- **Wintertodt → P5 + P12 + P3 + P10.** Points→reward-roll loop; per-category drop tier scaled by skill X = P12 rate-modifier; "warm clothing" = property-defined `item_set` + `aggregate_count(≤4)`; subdue (no kill) = `survive`-variant gate.
- **Guardians of the Rift → P5 + P4 + P3 + P12 + P10 + P13.** Two parallel point currencies (P5 params); pearls dual-shop (P4); Raiments per-piece + full-set kicker (P3); intricate-pouch nesting (P12); team-aggregate essence with a non-linear 20th-player kink (P10 payload); needle+pouches→colossal pouch (P13).
- **Hunter Rumours → slayer-assignment pattern (P6 on-task + P5 payout + P11 counter + P8 distributed + P12 pity-rate + P3 outfit set).** Maps cleanly; on-task hand-in lock = scoped P6.
- **Mahogany Homes → slayer-assignment / reward-shop pattern (P5 carpenter points + P13 plank/steel recipe + P3 carpenter outfit + P12 supply crate + P8 randomized homeowner sites).**
- **Mastering Mixology → P4 + P5 + P13.** Triple-resin reward shop, paste-sequence recipes, Retort/Agitator/Alembic facilities, Digweed payout-doubler.
- **Treasure Trails → P9 + P8 + P11 + P12 + P13 + P6 + P7.** Clue = ordered sub-quest chain with all_of finale; STASH = recipe; emote = equipped+location atom; casket = multi-roll tiered drop_table; milestones = per-tier completion counter; Wilderness despawn = `rule_zone`.
- **Collection log → P10 + P11 + P8.** Account-wide obtained-SET (already the `clog_obtained` field); staff-tier slot thresholds = counter+derived threshold; shared item across pages = P8 fan-out; gilded "90% rounded" = derived denominator.
- **Sailing → P10 + P13 + P7 + P1 + P8 + P11.** Per-account multi-slot ship build = POH-like P10; hazard-gated oceans = `rule_zone` with `ship_facility_built` access atom; ocean→sea→dock = P1 transport; Barracuda trials = P11 tiers. Crew stats confirmed non-gating (captain level is the real gate).
- **Fortis Colosseum → P6 + P11 + P12 + P5 + P2 + P14.** Run-lifetime modifiers (P6); Glory = max-aggregation counter (P11); wave-indexed drop rate (P12, *not* modifier-driven — confirmed negative); quiver guaranteed-on-completion + recommended-vs-required stats (P14).
- **Lunar spells → P1 + P13 + P2 + P6 + P10.** Spellbook = mode/system node owning the gate; cast = rune-consuming recipe; doses/spec-bar/jewelry charges = P2; timed buffs/cooldowns = P6 lifetimes.
- **Pets → P12 + P2 + P6 + P10 + P13.** Multi-source same-pet drops (reified edges); skilling-pet `1/(base − level·25)` = level-parameterized rate with `boostable=false`; tertiary duplicate-suppression = clog-gated roll; cat lifecycle = P2 state-machine; menagerie = `facility`.
- **Varlamore (aggregate) → P5/P11/P8/P12/P3/P9/P1.** Confirms the above sub-domains compose without new structure.

These 12 are strong evidence the pass-1 catalog generalizes across activity/minigame/transport/collection domains.

---

## 5. Net delta to the taxonomy (add on top of pass 1)

**New node kinds:**
- `game_mode` / `ruleset` (seasonal overlay scope; own economy + Hiscores + trade rules) — **MUST-A**
- `leaderboard` (competitive rank source for placement rewards / "firsts") — MUST-A satellite
- `random_event` (interrupt-spawned activity gated by time-trigger + zone eligibility) — **MUST-B**
- `difficulty_config` + `invocation_toggle` (chosen-difficulty bundle + per-toggle scalar delta) — **MUST-C**

**New edge kinds:**
- `scales_with` (chosen difficulty scalar → NPC stat-block AND drop_table rate) — **MUST-C**
- `mutually_exclusive_with` (exclusivity among reward/relic options) — NICE
- `use_gate` (item usability gated by personal killcount; locked-item name-list as data) — NICE
- `voids_prestige` (P14-style negative; activity → group-state) — NICE

**New atoms / modifiers:**
- `scope=game_mode` (trading-allowed, economy-id, seasonal-lifetime; distinct from account_type) — **MUST-A**
- `lifetime=time_window` (anchor_event + ramping schedule_table; persists offline) — **MUST-B**
- `elapsed_time_trigger` (scheduled spawn; antecedent = time-in-eligible-state, offline-accruing) — **MUST-B**
- `raid_level` (player-elected continuous difficulty scalar, threshold-comparable, parameterizes reward rate + NPC stats) — **MUST-C**
- `rank_threshold` (reward by relative leaderboard placement) — NICE
- Counter `aggregation` field (`sum` | `max`) — NICE
- Boostable enum `{not_boostable, boost_at_acquire, boost_at_use}` — NICE
- Reward-shop cost as `{currency→amount}` map (was scalar) — NICE
- `stack_capacity`, `ship_facility_built`, `spellbook_active`, `accept_aid`, `npc_dialogue_unlock`, `cooldown(duration)`, `spec_bar_full`, `account_property` — NICE (all ride the existing spine)

**Bottom line:** lock everything except the three axes — alternate `game_mode`/ruleset (A), the real-time/offline clock as trigger+lifetime (B), and configurable-difficulty scalars (C). A narrow third pass over those three families (other leagues variants; DT2/other invocation-or-modifier activities; any other offline-clock or seasonal mechanic) will confirm whether B and C generalize and let A be specified, after which the schema can be locked.
