<!-- OSRS entity-graph nuance survey (2026-06-24): wiki-schema mining + 14-page diverse hunt.
Run BEFORE locking the ontology to catch structural modeling patterns. 18 findings + synthesis. -->

# OSRS Entity-Graph: Pattern Catalog + Ontology-Gap List

A synthesis of 18 nuance/schema-mining findings, to de-risk the entity-graph schema before lock. The recurring theme: **the draft is a good *static account-fact DAG*, but OSRS is pervasively reified-relations, parameterized-by-state, context-scoped, and stateful.** Most gaps reuse the existing `requires` + condition-atom engine — the structural ones that would force a re-ingest are flagged MUST.

---

## 1. TL;DR — biggest cross-cutting patterns the draft handles weakly

1. **Relations are reified rows, not boolean edges.** Drops (rate + rolls + table-membership + context-gate), sells (price + currency + buyback), and recipes (N materials + tools + facility + skill + xp → output) are *attribute-bearing hyper-edges* the wiki itself models as Bucket tables (Dropsline, Storeline, Recipe). The draft's binary `drops`/`sells` flatten away the payload. **This is the #1 structural risk** — getting the edge shape wrong forces a re-ingest.

2. **Conditions are not all permanent account facts.** The locked atom vocab assumes monotonic, Hiscores-derivable truth. But `on_task(category)`, killcount (session-scoped, resettable), skull/teleblock (transient status), `visited_place`, team-aggregate levels, and `equipped` (vs merely owned) are **different *lifetimes and subjects***. Folding them into the met/blocked DAG produces false "you can kill Cerberus permanently" claims. Needs a **scope/lifetime tag on atoms**, not new edge kinds.

3. **Requirements are two-layer and parameterized, not flat.** Transport proved system-gate ∧ per-node-gate (inheritance/composition). GWD/CoX/Pest Control extend this: requirement *amounts* derive from other conditions (killcount threshold = f(CA tier)), are team-aggregate, or are *boostable*. The unified atom tree is right but needs **modifiers (boostable, ironman-variant, scope/subject) on atoms** and **composition (inherit system gate then AND own)**.

4. **A huge swath of "what should I wield vs X" is structurally unsayable.** No equipment-bonuses facet, no item_set/set_effect, no monster attributes/weakness/immunity, no gear-vs-monster interaction edges. The explicitly-wanted "CAs → Ghommal's hilt → negates Barrows drain" class of fact has nowhere to live. This is the **combat/effect layer** — multiple MUST node/edge kinds.

5. **Effects, prices, and rewards are functions of state, not scalars.** Glory charges, Barrows degradation, Dharok's HP-scaling, Pest Control points = table[boat][CA-tier], Tokkul doubled by diary, Farming yield = f(level, compost, modifiers). The draft has `expand_for_account` on the *cost* side; the survey says **generalize parameterized-payout to the reward/effect/price side**, and add **context-scoped effect edges** (effect carries an `applies_when` cond_group).

---

## 2. Pattern Catalog

For each: description · where it shows up · recommended model (reuse-first).

### P1. Shared-mechanic systems (transport + generalizations)
One node owns a one-time gate; many stops/providers fan out, each with its own overlay gate.
**Where:** fairy rings, spirit trees, canoes, gliders; jewellery-teleport ("rub"); slayer reward shop; repair (6 NPCs + POH stand share one coefficient table); shared teleport *destinations* reachable via item OR spell OR POH object.
**Model:** `transport_system`/shared-mechanic node holds the base `requires` once; each `gives_access`/`connects_to` edge carries its own (possibly empty) `cond_group`. **Effective requirement = system_gate ∧ edge_gate, composed at query time** (requirement inheritance). Generalize the pattern to *access-providers → shared destination node* so destinations aren't duplicated per provider. Tier-as-capability (canoe reach, spirit-tree count) is a `transport_tier` sub-entity: `{threshold, capability_value, capability_unit ∈ stops|count|unlimited}`.

### P2. Charged / degradable / consumable item-state
An item's capabilities depend on a mutable integer/state, not identity.
**Where:** Amulet of glory (1–6 charges, recharge ceiling 4 vs 6), Barrows (100/75/50/25/0 + continuous 0–250 sub-counter), jewellery/run-energy generically.
**Model:** `charge_state`/`consumable_state` as a **value-object/state-machine attached to the item** (NOT N separate nodes, NOT `supersedes` — degradation is reversible & cyclic). State machine has ordered states with **transition triggers** (`on_drop⇒0`, `enters_combat`, `per_90_ticks`) and **per-state capability flags** (tradeable, equippable, gives_set_bonus). `gives_access`/teleport edges carry a `charges≥1` atom; recharge is an action that *sets* charges to a ceiling. Tradeability becomes state-conditional, not a static item bool.

### P3. Equipment sets + set effects + cross-slot modifiers
An effect emerges from a *co-equipped set*, scales on runtime vars, and can be amplified from another slot.
**Where:** Barrows brother sets (Wretched Strength, Dharok HP-scaling), void, justiciar; amulet of the damned amplifies; Salve/Slayer-helm.
**Model:** promote set to first-class **`item_set` node**; `item_set --grants--> set_effect` with a `requires` cond_group = AND of `item`-atoms **+ a new `equipped` qualifier**. **`set_effect` is a node** with typed attrs `{trigger, proc_chance, target, affected_stat, magnitude_kind, scaling_ref}` (store the *formula identity* for Dharok, engine displays it). Add **`modifies` (effect-on-effect)** edge for cross-slot amplifiers. Member-level `requires` stays (Dharok weapon needs Att/Str, armour needs Def — set is not homogeneous).

### P4. Alt-currencies + closed-loop economies + bidirectional shops
Not every price is coins; some currencies are sealed, only exiting via a bridge item; shops buy *and* sell.
**Where:** Tokkul (sealed, exits only via onyx→GE), commendation points (capped 4000, single faucet, non-tradeable), slayer points (resettable streak), Hallowed marks, Castle Wars tickets, raid points (ephemeral per-instance).
**Model:** first-class **`currency` node kind** (coins is just one). Price = `{amount, currency_ref}` on `sells`. Add **`accepts`/`buys_back` edge** (shop→item, own price+currency+margin) — the income side. Add **`realizable_via`** edge (currency → bridge items) so the iron-realizable engine can trace exits; tag currencies `tradeable`/`external_exchange`. Ephemeral raid/instance points are a *resource node scoped to the activity instance*, never realized to GP.

### P5. Points / reward-shop loops with parameterized payout
Earn a scalar from heterogeneous sources (capped per-source), spend it; payout/eligibility is a function of account state.
**Where:** Pest Control (points = table[boat][CA-tier], coins = 10×combat, XP = f(skill level)), CoX (points→unique-roll probability, common cap 131,071), slayer streak milestones, Tokkul scaled by waves+diary.
**Model:** generalize **`expand_for_account` to the reward side** — reward edges carry a *parameterized payout expression / lookup* evaluated against AccountState, not a scalar. Add a **`reward_eligibility` cond_group** attachment point distinct from `entry requires` (objective_met ∧ participation>0). Currency→XP is a distinct **`converts_to`** edge (currency → skill XP, formula + per-skill `skill_level≥25` gate).

### P6. On-task / contextual / transient conditionals
Conditions that flip many times per session, are mutually exclusive, or depend on traversal/position — *not* derivable from a snapshot.
**Where:** slayer `on_task(category)` (gates helm bonus, superior spawns, boss attackability, brimstone keys, most uniques), GWD killcount, skull/teleblock, fairy-ring "trapped-escape" waiver, `visited_place`, build-mode vs normal-mode.
**Model:** add a **lifetime/scope tag on every atom**: `{account_permanent | session_transient | location_scoped | context}`. Edges carrying transient atoms are **NOT account-satisfiable** — the engine reports "conditionally true given context C", never folds into the permanent met/blocked DAG. Reuses the atom tree; the discriminator is the new piece. (Prevents asserting permanent capabilities falsely.)

### P7. Region-wide rules + overlapping rule-zones + continuous coordinates
A place carries *rules* and a numeric position field; rule-zones overlap and crosscut containment.
**Where:** Wilderness (level 1–56 drives PvP range, teleport cutoffs 20/30, item→coin >20, resource quality), multi/single-combat zones, safe tiles, Ferox/Resource-area fee zones, GWD chamber safety-profiles.
**Model:** keep `located_in` for **containment**; add (a) a **`coordinate_field` attribute** on place (e.g. `wilderness_level: range`) with **`region_coordinate_threshold` atoms**; (b) a separate many-to-many **`rule_applies_in` overlay** to `rule_zone` nodes (multicombat, pvp_safe, entry_fee) — *not* single-parent containment; (c) **derived/parametric relations** (a `rule` node carrying a predicate like attackable = |cmbA−cmbB| ≤ local_level) the engine evaluates, KG only stores the definition. Place-scoped **environmental-hazard nodes** (chill, prayer-drain, darkness) with `negated_by` conditions, including cross-boss links (Zilyana drop → Saradomin's light → negates darkness).

### P8. Distributed / replicated activities (place × type instance)
The same activity recurs at N sites, each with local overrides; the (place × type) join is a real third object.
**Where:** Farming patches (Catherby herb gets Kandarin +25; Falador tree gets Elite disease-immunity; Trollheim quest-gated+disease-free), slayer monster variants per dungeon, Mor Ul Rek as activity-hub.
**Model:** first-class **instance node** (`farming_patch`) with `located_in→place` + `instance_of→patch_type`; **all per-site overrides hang off the instance.** `patch_type` holds shared mechanics; place holds geography. **Modifier edges carry a `scope` qualifier**: `global-player | patch_type:<t> | patch_instance:<id> | location:<p>` — without it, single-site bonuses leak game-wide or stack wrong.

### P9. Composite / sub-entity quests
One quest with independently-gated children; partial progress; per-child rewards; set-cardinality finale.
**Where:** Recipe for Disaster (8 subquests, each own req-tree), RfD final = ALL siblings, Troll Stronghold "partial (defeat Dad)" quest-step gate.
**Model:** **`has_part` containment edge** (subquest = first-class quest-like node owned by parent, mirrors place recursion). Each subquest carries own `requires` + own `grants` (+1 QP, lamp) so **partial-completion QP accrues correctly**. Add a **quantified `all_of(part-of set)` condition** (references the group, not a brittle hand-listed AND). Add **quest-STEP granularity atom** (`quest:X, step=Y`, finer than 3-state). Mark derived aggregates (RfD's 175-QP, mostly self-satisfied) as **DERIVED/informational vs PRIMARY gate** to avoid double-count/near-self-reference.

### P10. Group / instanced / account-conditional existence
Nodes that exist only per-account or per-instance; requirements over teams; sampled composition.
**Where:** POH builds, player-grown spirit trees, DIQ POH fairy ring, superior slayer spawns (unlock-gated), CoX rooms (sampled subset), quest-vs-post-quest Vorkath variant.
**Model:** **`availability` attr** `{always | player_built | unlock_gated | sampled_from_pool}` + `build_requires` cond_group. **KG holds the CATALOG/template; AccountState materializes realized instances** (link-don't-merge — never bake account builds into the shared graph). Sampled containment edges carry presence semantics `always | sampled(pick k of N)`. **Team-aggregate requirements** need a **subject qualifier on atoms** `{self | team_sum | team_each | party_size}`; party_size is a scaling parameter. Temporal **participation/membership** (joined_before_start, present_at_chest) gates reward eligibility for group content.

### P11. Counters (killcount, streaks) + derived/resettable progression
A running, often non-monotonic counter that gates a threshold; the threshold itself may be derived.
**Where:** GWD per-faction killcount (resets on exit; bypassed by Ecumenical key; threshold = f(best CA tier 40/35/30/25/15)), slayer streak (milestones 10/50/100/250/1000, Turael reset, Krystilia=5), Vorkath head guaranteed_at kc==50.
**Model:** **counter mechanic node** (owned by faction/master) fed by `counts_toward` edges; the gate `requires` references the counter with a threshold and **scope=session/volatile**. Mark counters **non-monotonic/resettable** with the reset trigger as a state-transition (breaks the `progress_towards` monotonic assumption). **Derived threshold**: model CA tiers as `lowers` edges onto the base requirement (engine takes min), Ecumenical key as an OR-branch. `guaranteed_at:{counter, value}` on the drop edge for pity drops.

### P12. Probabilistic / tiered / reified-payload rewards
Drops are distributions with rolls, tables, context-gates, modifiers, and pity floors — not booleans.
**Where:** Vorkath (2-roll standard table, tertiary 1-roll, nested Shark sub-table, Brimstone-key only on Konar, Legends'-gated rates, RoW removes "nothing"), CoX, glory eternal 1/25000 on recharge.
**Model:** **promote drop table to a node**: `monster/activity --has_table--> drop_table{rolls:N} --contains{rate,qty}--> item`; tertiary = separate rolls=1 table; nested = table→table. **Per-kill probability is COMPUTED, never a stored weight.** Source typed as a **union (monster | activity | scenery-site)** with a `drop_type` discriminator (drop|reward). Context-gated drops reuse `requires` cond_group ON the contains edge (incl. new `slayer_assignment` atom). **Rate-MODIFIERS** (not gates) are a typed `rate_modifier{trigger, op: replace|remove_slot|scale, value}` applied at *table* scope (RoW re-normalizes). Probabilistic transmutes (eternal glory) reuse the 1/N rarity pattern on a `transmutes_to` edge.

### P13. Production / recipe hyper-edges (cross-cutting)
A bundle of {N materials + tools + facility + skill + xp + ticks → output(s)} is one unit.
**Where:** Recipe Bucket (7,312 rows), enchant-to-make-glory, Construction builds, Farming compost loop, smithing.
**Model:** **reify recipe as a node** (matches the wiki's own Bucket:Recipe) with typed edges to inputs/tools/facility/skill/output. Distinguish **`consumes`** (destroyed, quantity) from **`requires`** (tool/level, kept) — critical so the cost brick doesn't double-charge tools or miss plank consumption. Guarded output: `produces` can switch output by a `cond_group` (CoX potion tier capped by producer Herblore at creation). **Material cycles allowed** (produce→compost→patch→produce, harvest→seed→replant) — the requires/produces graph is **not a DAG**; tag feedback edges so the planner detects self-sustaining loops for iron gather-time accounting.

### P14. Required-vs-recommended (soft advisory) + negative relations
Some gear is "you die without it" but is a consumable, not a hard gate; some boosts conflict or are void.
**Where:** Vorkath (antifire required-for-survival, Salve recommended, immune cannon/thrall/poison/venom), Salve ⊕ Slayer-helm non-stacking, GWD soft-protection, fairy-ring CLR "reachable but harmful".
**Model:** keep hard gates as `requires`; add **soft `recommended_for`/`strategy` edges with a strength enum** `{required_for_survival | strongly_recommended | optional}` — the Layer-2 advisory overlay, **never auto-blocks** (efficiency-vs-fun principle). Add **negative edges**: `does_not_stack_with` (symmetric), `immune_to`/`counters` (monster ↔ damage-type/gear, keyed on monster attribute). Split `requires_access` vs `requires_to_damage`/`requires_to_kill` so the advisor says "bring salt" not "blocked". Soft/advisory traversal cost distinct from hard access (warn, don't block).

---

## 3. Ontology Gaps (MUST vs NICE)

**MUST** = structural; omitting it forces a re-ingest or makes a whole question-class unanswerable. **NICE** = additive later via link-don't-merge.

### New node kinds
| Node kind | MUST/NICE | Why |
|---|---|---|
| `scenery`/`game_object` (object_id) | **MUST** | Top-level wiki entity (Infobox_scenery, Bucket:object_id); drops, sells, gates, is the target of transport/gather/requires. Transport stops, rocks, altars, doors are scenery. Folding into place/npc breaks object_id bridging. |
| `currency` | **MUST** | Tokkul/points/marks; coins-only already bit us. Prices/rewards reference currency_ref. |
| `equipment_bonuses`/`gear_profile` facet | **MUST** | Separate Infobox/Bucket (Infobox_bonuses); 11-slot × stab/slash/crush/magic/range attack+defence + str/rstr/mdmg/prayer/speed/slot/combat_style. No BIS without it. |
| `item_set` | **MUST** | Set effects attach nowhere truthfully without it. |
| `set_effect` (structured) | **MUST** | `{trigger, proc_chance, target, affected_stat, magnitude_kind, scaling_ref}`. |
| `drop_table` (reified) | **MUST** | rolls/membership/nesting; per-kill prob computed. |
| `recipe`/`production` (reified hyper-edge) | **MUST** | {materials+tools+facility+skill+xp→output}. |
| `transport_system` (already planned) | **MUST** | Confirmed; plus tier sub-entity. |
| `task_category` (slayer) | **MUST** | Assignment/block/extend/on-task operate on category, not monster. |
| `faction`/`god` | **MUST** | Join key for killcount attribution AND aggression-soothing. |
| `rule_zone` (overlay) | **MUST** | Overlapping, crosscuts containment. |
| `farming_patch`/place×type instance | **MUST** | Carrier of per-site overrides. |
| `subquest` (via has_part) | **MUST** | Partial completion + per-child rewards. |
| `mechanic`/`boss_phase` | NICE→MUST | Causal grounding for why gear/CAs exist; needed for the effect layer but additive. |
| `hotspot`/`buildable_object`/`room` (Construction) | NICE | POH; mostly per-account/catalog. |
| `spell` | NICE | Gates methods; carries own requires; additive. |
| `money_making_method` (mmg) | NICE | Income brick wants it; additive. |
| `counter`/`score` resource node | **MUST** | Killcount/streak/raid-points have no home. |
| `prayer`, `music_track`, `deity`, `relic`, `emote`, `book`, `armour/weapon_group`, `varbit` | NICE | Authoritative kinds in the 48-template taxonomy; ingest later. |

### New edge kinds
| Edge | MUST/NICE | Why |
|---|---|---|
| `has_bonuses` (item→gear_profile) | **MUST** | Gear/BIS substrate. |
| `has_table`/`contains` (→drop_table→item) | **MUST** | Reified drops. |
| `consumes` (distinct from requires) | **MUST** | Destroyed vs kept — cost accounting correctness. |
| `produces` (guarded) | **MUST** | Recipe output, switchable by cond. |
| `accepts`/`buys_back` (shop→item) | **MUST** | Income side; differential buy/sell. |
| `aligned_with` (monster/item→faction) | **MUST** | Killcount + soothing join. |
| `has_part` (quest→subquest) | **MUST** | Composite quests. |
| `member_of` (item→equipment_group/set) | **MUST** | Set/void/Barrows. |
| `rule_applies_in` (overlay, many-to-many) | **MUST** | Rule-zones. |
| `modifies`/`amplifies` (effect→effect) | NICE | Amulet of the damned; advisory layer. |
| `recommended_for`/`strategy` (strength enum) | **MUST** | Layer-2 soft gear; else hard DAG wrongly blocks on consumables. |
| `does_not_stack_with` (symmetric), `immune_to`/`counters` | **MUST** | Negative relations; planner suggests void strategies otherwise. |
| `counts_toward` (kill→counter) | **MUST** | Counter feed. |
| `rate_modifier` (table-scope) | NICE | RoW/CA rate transforms; additive. |
| `converts_to` (currency→skill xp) | NICE | XP brick deferred. |
| `realizable_via` (currency→bridge item) | **MUST** | Iron-realizable can't trace exits otherwise. |
| `assigns` (slayer_master→category, weighted) | **MUST** | Slayer routing. |
| `negated_by` (hazard→item/quest) | NICE | Environmental effects. |
| `teaches` (npc→skill), `spawns_at`/`ground_spawn` (item→place) | **MUST** | Tutor layer + 3rd item-source channel (free spawns) unrepresentable today. |
| `service` (npc/facility→effect, cost+cond) | **MUST** | Repair/toll/lost-item; gives_access has no toll/waiver. |
| `requires_facility` (activity→facility) | **MUST** | Furnace/anvil/altar/range/wheel have no node. |
| `covers` (diary→place*), `unlocks_music` (region→track) | NICE | Multi-place diary; completionist lens. |
| `placed_at`/`has_geometry` (any node→coords) | NICE | Proximity/pathing/plane; additive. |
| `same_entity` for combat variants (Vorkath, glory ladder) | NICE | Reuse existing bridge. |

### New / extended condition-atom types & modifiers
| Atom / modifier | MUST/NICE | Why |
|---|---|---|
| **scope/lifetime tag** `{permanent\|session_transient\|location_scoped}` | **MUST** | Prevents false permanent-capability claims (on_task, killcount, skull). The single highest-leverage atom change. |
| **subject tag** `{self\|team_sum\|team_each\|party_size}` | **MUST** for group content | CoX/ToB/ToA team-aggregate; else unsayable. |
| `equipped`/`worn` (distinct from owning `item`) | **MUST** | Set effects, gear context. |
| `boostable` flag on skill_level | **MUST** | False block/pass on "can I do this now" (Awowogei Cooking 70 boostable vs Agility 48 not). |
| ironman-variant / account-scoped threshold on skill_level | **MUST** | Recurring economic-leak class; Questreq encodes per-row ironman flag. |
| quest 3-state `{started\|completed}` + **quest-step** granularity | **MUST** | Questreq Started:/Full:; Troll Stronghold partial. Binary over-constrains. |
| `aggregate_count` family `{quest_points, kudos, combat_level, ca_points, clog_count}` | **MUST** | Computed-over-graph counters. |
| `slayer_assignment` (master==Konar, category) | **MUST** | Context-gated drops (Brimstone key). |
| `unlock_purchased` (superiors, boss-tasks) | **MUST** | Existence-conditional content. |
| `visited_place`/`location_discovered` | NICE | Fairy-ring codes; **NOT Hiscores-observable** (provenance gap). |
| `region_coordinate_threshold` (wilderness_level) | **MUST** for Wildy | Continuous coordinate gates. |
| `combat_encounter`/`can_defeat` (monster ref + constraint e.g. no_prayer) | NICE | RfD "defeat lvl-N without Prayer"; argues monster nodes must exist. |
| `house_contains(room_type, count)` | NICE | Servant hire; POH. |
| all_of(part-of set) quantified condition | **MUST** | RfD finale; brittle hand-AND otherwise. |
| `state` qualifier on effect edges (`applies_when` cond_group) | **MUST** | Context-scoped item/prayer effects (Bulwark off vs players, glory worn-vs-charged). |
| PRIMARY vs DERIVED atom flag | NICE | Avoid double-count on self-referential aggregates. |
| satisfies/`slot_id` label on OR groups | NICE | "Met via diary, item not needed" loadout advice. |
| `persistence` flag on requires/gives_access `{one_time_unlock\|per_use}` | **MUST** | Frozen key (permanent) vs hammer (per-visit) read identically today. |

### New attributes
**MUST:** item facets (tradeable/equipable/alchable/value/weight/buy_limit/high_alch — economic+mechanical, the income/cost layer needs them); monster facets (combat stats, attribute[], elemental weakness, poison/venom/freeze resistance, immune cannon/thrall/burn, slayer_level/category/assigned_by); place facility flags (bank/poll/deposit) + wilderness-range; CA `type` + `league_region` + points-per-tier; charge/state-machine on degradable items; modifier **scope** qualifier; **version discriminator** (dropversion/shopversion) on drops/sells edges. **NICE:** geometry (coords/plane/mapID), varbit_index bridge, music regions, diary `coordinate_field`.

---

## 4. Consolidated Node/Edge Taxonomy Proposal

**Node kinds (current + additions):**
- *Keep:* place (recursive), npc, monster, shop, item, activity, skill, quest, diary, combat_achievement, minigame, goal, transport_system.
- *Add MUST:* `scenery`/`game_object`, `currency`, `equipment_bonuses` (facet), `item_set`, `set_effect`, `drop_table`, `recipe`/`production`, `task_category`, `faction`, `rule_zone`, `farming_patch` (place×type instance), `subquest`, `counter`/`score` resource, `facility`/`station`.
- *Add NICE:* `mechanic`/`boss_phase`, `spell`, `prayer`, `music_track`, `hotspot`, `buildable_object`, `room`, `transport_tier`, `equipment_group`, `money_making_method`, `varbit`, `deity`/`relic`/`emote`/`book`/`miniquest`.

**Edge kinds (current + additions):**
- *Keep:* located_in, operates, sells, drops, requires, gives_access/served_by/connects_to, grants, progress_towards, supersedes, effect, same_entity.
- *Add MUST:* `has_bonuses`, `has_table`/`contains`, `consumes`, `produces` (guarded), `accepts`/`buys_back`, `aligned_with`, `has_part`, `member_of`, `rule_applies_in`, `counts_toward`, `recommended_for`/`strategy` (strength enum), `does_not_stack_with`, `immune_to`/`counters`, `realizable_via`, `assigns` (weighted), `teaches`, `spawns_at`, `service` (cost+cond), `requires_facility`, `instance_of`.
- *Add NICE:* `modifies`/`amplifies`, `rate_modifier`, `converts_to`, `negated_by`, `covers`, `unlocks_music`, `placed_at`/`has_geometry`, `companion`/`adjacent_protects` (patch→patch), `buildable_in`, `protects`, `can_anchor`.

**Edge-payload principle (cross-cutting MUST):** drops/sells/produces/grants are **attribute-bearing reified relations** (rate+rolls+table | price+currency+stock | quantities+xp+ticks | parameterized-payout), not booleans — and carry an optional `cond_group` **and a version discriminator**. This mirrors the wiki's own Bucket-table shape; getting it wrong is the primary re-ingest risk.

---

## 5. Impact on the Open Decisions

**A1 — Geography (`located_in`).** *Changes the recommendation.* Containment is necessary but insufficient. (a) Add a **vertical/floor axis** (Lumbridge bank top-floor, Cook basement) as an edge attribute or place_type=floor. (b) Add **absolute geometry** (coords/plane/mapID, multi-feature) as a *separate* relation from containment (NICE). (c) Add a **continuous `coordinate_field`** (wilderness_level) with threshold atoms (MUST for Wildy). (d) **Separate containment from `rule_applies_in` overlays** — many-overlapping, not single-parent (MUST). (e) Diaries are **multi-place** (`covers`), not `located_in` one place. **New sub-decision A1b: containment vs rule-zone vs coordinate are three distinct "where" relations — don't conflate.**

**A2 — `operates`.** *Mostly confirmed, extend.* Shop.owner ↔ NPC.shop are reciprocal (symmetric). But add **`teaches`** (tutors), **`service`** (repair/toll/lost-item with cost+waiver), **`accepts`/buys_back** (income side), and **`assigns`** (slayer master). `operates`/`sells` alone can't express the tutor/service/buyback layer. **New decision A2b: shops are two-way exchanges (buy+sell, currency-typed), not one-way vendors.**

**B1 — Conditional fidelity.** *Biggest impact; adds decisions.* The unified atom tree is validated (requirements span quests/spells/recipes/construction/slayer/music). But fidelity must extend along **five new axes**: (1) **scope/lifetime** (permanent vs transient vs location-scoped) — MUST; (2) **subject** (self vs team) — MUST for group content; (3) **modifiers** (boostable, ironman-variant) on atoms — MUST; (4) **composition/inheritance** (system_gate ∧ edge_gate) — MUST; (5) **derived/parameterized amounts** (threshold = f(another atom)) — MUST. Plus `equipped`≠owned, quest 3-state+step, aggregate_count, all_of-quantified, and **PRIMARY vs DERIVED** gating. **New decision B1b: distinguish hard-gate `requires` from soft `recommended_for` (advisory strength enum) — the hard DAG must never block on a consumable.** **B1c: effect edges carry an `applies_when` cond_group (context-scoped effects).**

**C1 — npc-vs-monster.** *Changes the recommendation — the binary split is insufficient.* Need (a) **`scenery`/game_object** as a third interactable kind (MUST — object_id, drops/sells/gates); (b) an **objective/protect-target role** (Void Knight, GWD) — attackable-relevant but not player-attackable, not a vendor → a role attribute, not a new kind; (c) **monster variants** (quest vs post-quest Vorkath) via `same_entity`; (d) drop/reward **source is a union** (monster | activity | scenery). **New decision C1b: interactable kind is npc | monster | scenery, plus a role attribute (tutor, protect_target, slayer_master).**

**E1 — Competency gate.** *Refines significantly.* Split **`requires_access` vs `requires_to_damage`/`requires_to_kill`** (slayer: present but 0 damage until level N; gargoyle needs rock hammer to finish) — else "bring item" advice collapses into "blocked". Add **`combat_encounter`/can_defeat** for "defeat lvl-N (without Prayer)" (NICE, but argues monster nodes/stats must exist). Add **boostable** (soft vs hard threshold) and **persistence** (one-time vs per-use). **New decision E1b: gate semantics is access vs damage vs kill vs survive — a qualifier on the requires edge.**

**F1 — cache-ids.** *Confirmed and extended.* The wiki has explicit id-bridge tables (item_id/npc_id/object_id) = its own link-don't-merge. **Add `object_id`** (scenery) to the bridge set (MUST if scenery is added). **Add an optional `varbit_index`** on completion atoms (quest/diary/CA/account-flag) to reconcile against live gamestate — RuneLite reads varbits; without it account-mirroring stays heuristic (NICE but high-value). **New decision F1b: items are versioned** — one page hosts many cache item_ids (charged/uncharged, poison-tiers) with version_anchor/default_version. Model as item-page identity + child variant nodes bridged by `same_entity`; **drops/sells/exchange target the VARIANT.** This is **MUST** — flat one-node-per-item either over-merges (loses per-variant stats/value/drop-identity) or over-splits (loses equipment identity), and it's a re-ingest risk.

---

## 6. Wiki-as-Schema Mapping

Ingestion should be driven by the wiki's own schema. The wiki has **three source layers**, not two (the draft's cache=node / wiki=edge misses the third): **cache** (node existence + ids) · **Infobox/Bucket** (attrs + editorial) · **Module/Bucket relational tables** (versioned stock/drops/reqs, keyed by a version discriminator). Recognize the **module_table layer** explicitly.

| Wiki source | → Node/edge kind |
|---|---|
| Infobox Location / **Bucket:Infobox_location** + Bucket:Map | `place` (+ facility flags, wilderness-range, coordinate_field, geometry); `covered_by`→diary, `plays`→music |
| Infobox Monster / **Bucket:Infobox_monster** | `monster` attrs (combat stats, attribute[], weakness, immunities, slayer_level/category); `assigned_by`→`assigns` edge; `aligned_with`→faction |
| Infobox NPC / **Bucket:Infobox_npc** | `npc` (+ shop link, quest assoc, role) |
| Infobox Shop + **Bucket:Storeline** | `shop` node; `sells` + **`accepts`** edges carrying `{store_buy/sell_price, store_currency, stock, restock}` — currency proves alt-currencies |
| Infobox Item / **Bucket:Infobox_item** (item_id REPEATED + version_anchor) | `item`-page + **item-variant** children; tradeable/value/alch/weight/buy_limit facets |
| **Infobox Bonuses / Bucket:Infobox_bonuses** | `equipment_bonuses` facet → `has_bonuses` (slot + attack/defence/str/prayer/speed/combat_style) |
| Infobox Scenery / **Bucket:Infobox_scenery** (object_id) + **Bucket:Mine** | `scenery`/game_object; `Mine.rocks_json` → gather-site binding scenery→item |
| **Bucket:Dropsline** (38,707 rows) | `drop_table`/`contains` edges `{rarity, rolls, drop_value, drop_type, rare_drop_table}`; source = union (monster\|activity\|scenery) |
| **Bucket:Recipe** (7,312) | `recipe` node + `consumes`/uses_tool/uses_facility/uses_skill/`produces` (production_json: qty, level, xp, ticks, is_boostable) |
| Infobox Quest + **Bucket:Quest** + **Module:Questreq/data** | `quest` node (series/order from infobox) + `requires` DAG from Questreq (Started:/Full: 3-state, skills rows w/ ironman+boostable, QP/Kudos aggregates) — **AND-only; OR comes from elsewhere.** `has_part` for subquests. **Authoritative-for-atoms = Questreq, NOT the prose "Requirements" blurb in QuestDetails.** |
| Module:QuestDetails / Template:Quest details | quest *attribute* layer (difficulty/length/start_npc/enemies/series) — **separate from the requirement DAG; keep them apart** |
| **Module:Combat_Achievements / SMW combat_achievement** | `combat_achievement` (id, monster→`tested_on`, tier, type, task, league_region) + per-tier `ca_points` threshold → `grants` reward |
| Infobox Achievement Diary (+ tier pseudo-quests in Questreq) | `diary` *region* container + per-tier nodes w/ own requires + tier-chain; `covers`→places, `rewards_dispenser`→npc |
| Infobox Activity + **Bucket:money_making_guide** | `minigame`/`activity` (currency-reward, players-min, skills) + `money_making_method` node |
| **Bucket:Infobox_spell** | `spell` (magic_level, spellbook, runes, slayer_level) — gates methods |
| **Bucket:Exchange** + Infobox_item.high_alchemy_value | item pricing facet (GE high/low, alch) — income/cost realization |
| **Bucket:Varbit** | `varbit` bridge → optional `varbit_index` on completion atoms |
| Infobox Construction / **Bucket:Infobox_construction** | `buildable_object`/furniture (level, xp, room, hotspot, item_id) |
| Infobox Set / Armour/Weapon Group | `equipment_group`/`item_set` + `member_of` |
| Bucket:item_id / npc_id / object_id | `same_entity` id-bridges (cache↔wiki) — the wiki's own link-don't-merge |
| Transportation / Canoe / Fairy_ring / Spirit_tree pages (template/SMW params) | `transport_system` + `transport_tier` + per-route `connects_to` cond_groups (two-layer gate) |

**Ingestion guidance:** the reified Bucket tables (Dropsline/Storeline/Recipe) map 1:1 to reified edge-with-payload — ingest the table row as the edge, not a boolean. Carry the **version discriminator** (dropversion/shopversion) so multi-version pages (pre/post-quest shop, monster variant tables) don't collapse. The "Requirements" prose field is a **trap** — never parse atoms from it; use Questreq/data. Reward-shop catalogues often live on a **separate page** (Void Knights' Reward Options) — link-don't-merge across pages for one logical feature.

---

**Honest bottom line:** the draft's `requires`+atom engine is the right spine and most additions *reuse* it (modifiers, scope/subject tags, composition, soft-gate variant). The genuinely *structural* MUSTs that would force a re-ingest if missed: **reified attribute-bearing edges (drops/sells/recipe), item-variant versioning, scenery node kind, currency node kind, the equipment-bonuses/set/monster-stat combat layer, the atom scope/lifetime tag, and faction/task_category/farming_patch instance nodes.** Everything else is additive.
