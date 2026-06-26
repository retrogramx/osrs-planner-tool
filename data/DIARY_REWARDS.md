# Achievement Diary Rewards — Format Reference & Effect→Content Model

> **Scope:** `data/diary_rewards.json`, `data/diary_content_nodes.json`,
> `data/diary_goals.json` and the diary builder (`kg_ingest/builders/diaries.py`,
> `diary_goals.py`, `content_nodes.py`).
> **Audience:** contributors expanding the reward overlay to all 48 tiers and
> other-domain builders (Combat Achievements, Collection Log) reusing the
> content-node + effect taxonomy.
> **Taxonomy lineage:** reuses the quest-foundation reward/edge model
> (`data/QUEST_REWARDS.md`, `docs/superpowers/specs/2026-06-21-quest-data-foundation-design.md`).

---

## 1. The domain in the KG

The Achievement Diaries are modelled at **tier granularity** (spec §2):

- **48 tier nodes** — `NodeKind.DIARY`, id `diary:<region-slug>:<tier>`
  (12 regions × {easy, medium, hard, elite}), built by `build_diaries` from the
  492 tasks in `data/achievement_diaries.json`. Each tier node carries
  `data={region, tier, tasks[], skipped_quest_reqs}`.
- **One `requires` edge per tier** — the tier's aggregate gate: the **max skill
  level per skill** across the tier's tasks (each `boostable` honoured) + the
  **union of quest prereqs** (3-state). Per-*task* completion is plugin-only and
  is NOT an engine gate (the engine observes tier completion via the
  `achievement_diary` atom).
- **`progress_towards goal:achievement-diary-cape`** (`weight: 1`) per tier.

Region slugs (`kg_ingest.builders.supporting.DIARY_REGION_LABELS`):
`ardougne, desert, falador, fremennik, kandarin, karamja, kourend, lumbridge,
morytania, varrock, western, wilderness`.

---

## 2. `diary_rewards.json` record schema

One record per (region, tier). The `reward` prose strings in
`achievement_diaries.json` are the **starting point, not truth** — every datum
here is re-grounded by `verify_diary_rewards.py` (§6).

```json
{
  "region": "morytania",
  "tier": "hard",
  "regional_item": { "name": "Morytania legs 3", "item_id": 13114, "supersedes_item_id": 13113 },
  "lamp": { "amount": 15000, "min_level": 50, "eligible_skills": "any", "lamp_item": "Antique lamp (hard)" },
  "effects": [ ... ],
  "extra_unlocks": [ ... ],
  "source_url": "https://oldschool.runescape.wiki/w/Morytania_Diary"
}
```

### 2.1 `regional_item` — the upgrade ladder (§3.1)
Each tier grants its regional item (cloak/legs/amulet/…). `item_id` references
`data/items_equipment.json`. `supersedes_item_id` (nullable) is the **lower** tier's
item; the builder emits a `supersedes` edge (`item:<higher> → item:<lower>`) so the
ladder cloak 1 ≺ 2 ≺ 3 ≺ 4 is a graph fact. → one `grants` edge (tier → `item:<id>`).

### 2.2 `lamp` — per-tier XP (NOT a fixed formula)
`form: choice_lamp` — `{amount, min_level (nullable), eligible_skills: "any", lamp_item}`.
The **standard ladder** is 2,500 / 7,500 / 15,000 / 50,000 XP at min-level 30 / 40 / 50 / 70.
**Karamja is the only deviation** (verified 2026-06-23): easy = **1,000 XP, _any_ level**
(a distinct `Antique lamp (Karamja Diary)`), medium = 5,000 @ 30, hard = 10,000 @ 40,
elite = 50,000 @ 70. Amount + min-level are **captured per tier from the source, never
hardcoded** — the verifier confirms each against the wiki block, so a future per-region
quirk is caught. → one `grants` edge (tier → `None`, `data.form=choice_lamp`).

### 2.3 `effects[]` — the perks, tiered (§4)
The bulk of diary rewards. Each maps onto the §4 `effect` taxonomy:

```json
{
  "effect_kind": "rate_multiplier",
  "magnitude": 0.5,
  "target_facet": "runes received from the Barrows chest",
  "target": { "kind": "activity", "name": "Barrows" },
  "condition": "unconditional-once-earned",
  "tier_source": "morytania:hard",
  "source_token": "50% more runes from the Barrows chest",
  "rides_on_item_id": null
}
```

- `effect_kind` ∈ `stat_multiplier | rate_multiplier | capacity_change | fee_waiver |
  behavior_toggle | recurring_resource | access`.
- `magnitude` — the number when numeric (a **bonus fraction**: `0.1`=+10%, `0.5`=+50%,
  `1.0`=double), `null` for non-numeric perks; tied to `tier_source` (the % ladder is
  magnitude-per-tier_source).
- `target` — resolved by the builder to the effect's `dst` **content node**:
  `kind=skill`→`skill:<slug>`, `activity/region/monster`→the content node (§3),
  `item`→`item:<item_id>`. The raw `target` is **replaced by `dst`** in the edge.
- `rides_on_item_id` (optional) — the item the effect rides on; defaults to the
  regional item. Set it for effects on an extra-unlock item (e.g. the Bonecrusher).
- `source_token` (optional) — a **verbatim** substring of the wiki reward block the
  verifier checks (§6). Excluded from edge data. Omit → the effect is not token-checked
  (it rides on the already-checked regional item).

→ one `effect` edge per effect: `src = the item it rides on`, `dst = content node`,
`data = {effect_kind, magnitude?, target_facet, tier_source, condition}`.

### 2.4 `extra_unlocks[]` — beyond the regional item (§3.4)
`{reward_type, name, item_id (nullable), tradeable?, untracked?, note?}`. A resolvable
`item_id` → `grants` (tier → `item:<id>`); a null/untracked item (inventory items not in
`items_equipment.json`, e.g. **Bonecrusher**) → `grants` (tier → `None`) with `name` +
`untracked: true`.

---

## 3. `diary_content_nodes.json` — the effect→content layer (spec §4)

A diary effect's `dst` is the content it benefits, making tier↔content a plain graph
traversal both ways. Content nodes are **existence-only** (id/kind/name/slug + optional
data); their facts (drops/location/stats) are out of scope and accrete in later bricks.

```json
{ "id": "activity:barrows", "kind": "activity", "name": "Barrows", "slug": "barrows" }
```

`build_content_nodes` mints only `activity` / `monster` / `region` (kind must match the
id prefix). `skill:` targets are NOT minted here (skills already exist); `item:` targets
resolve via `build_supporting`. The bounded set covers exactly what the 48 tiers' effects
target.

---

## 4. `diary_goals.json` — the cape (spec §6)

- **`goal:achievement-diary-cape`** — `counter_type: member_count`, `thresholds: [48]`.
  Completion `requires` is `count_satisfied(set_ref = the 48 tier ids) ≥ 48`; each tier
  feeds it a `progress_towards` (weight 1); a threshold-gated `grants` yields the cape.
- **`goal:achievement-diary-cape-t`** (the trimmed cape) — the **first cross-domain goal
  link**: `requires` BOTH `goal:achievement-diary-cape` AND `goal:quest-point-cape`
  (dst-bearing requires edges), `supersedes` the untrimmed cape, ungated grant. The
  reciprocal `goal:quest-point-cape-t` (all quests + all 48 diaries) is the **quest
  domain's to own** — disclosed here, not modelled.

---

## 5. New schema pieces (everything else is reuse)

- `EdgeType.SUPERSEDES` — the item/cape upgrade ladder. `src` supersedes `dst`. Inert to
  gating (like `effect`/`progress_towards`).
- `AtomType.COUNT_SATISFIED` — counts done members of `data.set_ref` vs `threshold`,
  Kleene-aware over `achievement_diary` tier states. Powers the diary cape.
- Content-node instances + id helpers (`activity_id`/`region_id`/`monster_id`/
  `diary_tier_id`) in `kg_ingest/ids.py`.

---

## 6. `verify_diary_rewards.py` — the source-grounding gate

The **deterministic fabrication gate** (the diary analog of `verify_quest_rewards.py`).
It checks each structured reward carries a distinctive **source token** present
(case-insensitive) in that tier's cached wiki reward block:

| reward piece | token checked |
|---|---|
| `regional_item` | its `name` |
| `lamp` | comma-formatted XP `amount` (e.g. `15,000`) |
| `extra_unlocks[]` | each `name` |
| `effects[]` | the explicit `source_token` **if present** (else skipped) |

A token absent from the block → **FATAL** (fabrication / stale seed); a wiki bullet with
no matching seed token → **informational** missing-note (a reward the overlay omits —
expected while the overlay is partial).

**Cache** (`data/raw/diary_reward_blocks.json`, 48 tier blocks, whitelisted as committed
provenance): built **offline** from `achievement_diaries.json`'s committed per-tier reward
prose — which carries its own wiki provenance + accessed date — so verification is
deterministic and needs no live fetch. `--refresh` rebuilds it from that committed
snapshot. (Contrast the quest verifier, whose `--refresh` hits the live wiki; the diary
reward prose is already an in-repo wiki snapshot.) The **LLM verbatim sweep + owner
editorial review remain the deeper periodic audit** on top of this token gate.

---

## 7. Disclosed limitations (spec §10)

- **Content nodes are existence-only** — Barrows/Slayer-Tower/etc. nodes + the `effect`
  edges; their drops/locations/stats are future bricks. `target_facet` preserves the
  human specificity a bare node lacks.
- **Tier-level observability** — the engine gates tier completion (`achievement_diary`);
  per-task completion is plugin-only, kept as route detail in `node.data.tasks`.
- **Effect target precision** — an effect scoped to a skill *within* an activity ("Slayer
  XP **in the Slayer Tower**") sets `dst` to the most specific content node and carries the
  rest in `target_facet`.
- **Trimmed-cape reciprocal deferred** — `goal:quest-point-cape-t` is the quest domain's.
- **Reward overlay is a partial seed** — `diary_rewards.json` currently covers a verified
  subset of the 48 tiers; the remaining tiers are transcribed from the wiki (gated by the
  verifier) and **owner-reviewed** before the brick is considered complete.
