# Drop-Rate / Rarity Data Brick — Design (v1)

**Status:** design approved 2026-06-19; spec under review → implementation plan next.
**Brick:** `feat/drop-rates` (a pure DATA brick). Builds on the merged knowledge graph (PR #6), cost overlay (PR #7), and income overlay (PR #8).
**Companions:** `research/wiki-source-catalog.md` (the Bucket `dropsline` source), `research/data-pipeline-v1.md` (the rarity/variant grammar study), `data/collection_log.json` (the item set), `data/bosses_pvm.json` (existing `qty_per_hr_or_kill` proxy this eventually replaces).

---

## 1. Purpose & scope

Populate **true drop rarity** (a real `1/N` probability per item-per-source) for OSRS collection-log items, sourced from the OSRS Wiki and gated by a committed validator. Today `data/collection_log.json` carries a `drop_rate` slot that is **`null` for all 1,907 records**, and `data/bosses_pvm.json` only has a kill-rate-blended `qty_per_hr_or_kill` proxy. This brick fills the rarity gap.

**Why now / who consumes it (NOT built here):**
- **Loot-filter generator** ([[runelite-loot-filters]]) wants rarity to drive **rarity-aware beams** (a 1-in-5000 unique gets a special beam, distinct from a value tier).
- **Income overlay** wants true rarity × kc/hr to **replace the `qty_per_hr_or_kill` proxy**, tightening gp/hr (kills the "drop optimism" residual disclosed in the income brick).

**v1 is a PURE DATA BRICK:** source rarity → write a canonical dataset → committed validator. It does **NOT** wire the consumers (income recompute, loot-filter beams are each separate follow-up bricks). This keeps it a clean, independently-testable, independently-mergeable unit — the same scoping every prior brick used.

**v1 does NOT:** rarity for the common long tail of regular-monster junk drops (value-tiered, rarity-irrelevant); a full per-variant model for every team-size/region permutation (v1 captures the *significant* boosted conditions — §6 — and preserves the raw string so the rest is an additive v2); clue reward-casket rarities (a different reward-table model — §8); rewiring any consumer.

---

## 2. Load-bearing decisions (settled in brainstorm)

1. **Coverage = the 1,907 collection-log items** (the curated trophy/unique set — exactly what wants rarity beams + completion tracking). Common monster junk stays value-tiered.
2. **Source = OSRS Wiki Bucket `dropsline` API, queried BY ITEM.** `dropsline` is the wiki's reverse index (item → every monster/source that drops it + each rate). Machine-parseable `drop_json`; officially supersedes the dead SMW. Querying by item (not by source) is the key choice — see §5.
3. **Output = a standalone `data/drop_rates.json` keyed by `(item_id, real_source)`** — NOT a column bolted onto `collection_log.json`. Driven by the generic-source problem (§5): the clog lumps 88 slayer uniques under one fake `"Slayer"` source with no per-monster rate, so a single rate cannot live on a clog row. `collection_log.json` cross-references this table by `item_id`.
4. **Never fabricate.** Every `drop_rate` is a real parsed number with its raw wiki string attached, or `null` with a machine-readable *reason*. No invented or blended numbers.
5. **Boosted/conditional rates are in v1** as a `variants[]` array (§6), populated for the conditions that materially matter (slayer on-task / superior, raid scaling). The raw string preserves anything not fully modelled, so a richer v2 is purely additive.
6. **ToA gets a dedicated deep-dive** (§7) — its uniques scale by invocation + points (a formula, not a fixed `1/N`).

---

## 3. Output data shape — `data/drop_rates.json`

Standard envelope (`_provenance` / `records` / `_excluded`) matching the other `data/*.json` datasets. Each record:

```json
{
  "item_id": 4151,
  "item": "Abyssal whip",
  "source": "Abyssal demon",            // the REAL dropping NPC/activity (resolved, not a clog label)
  "source_node_type": "monster",         // monster | boss | raid | minigame | activity | clue | other
  "drop_rate": 0.001953,                 // canonical numeric probability in (0,1], or null
  "drop_rate_raw": "1/512",              // verbatim wiki string (audit + forward-compat); "" only when null
  "rolls": 1,                            // independent roll count for this drop (default 1)
  "drop_rate_status": "sourced",         // see enum below
  "variants": [                          // boosted/conditional rates (§6); [] when none
    { "condition": "on slayer task", "drop_rate": 0.001953, "drop_rate_raw": "1/512" }
  ]
}
```

**`drop_rate_status` enum (the honesty ledger — every null carries a reason):**
- `sourced` — a real numeric rate parsed from `dropsline`.
- `null-not-in-bucket` — item/source not present in `dropsline` (e.g. clue reward-casket items, many activities).
- `null-activity` — source is an activity/minigame with no kill-based `1/N` (points/action-based).
- `null-qualitative` — `dropsline` gives only a word (`"Common"`, `"Varies"`) with no number; we do NOT invent one.
- `null-unparsed` — a rate string the v1 grammar could not parse (logged for follow-up).
- `null-multi-source` — a generic source that could not be resolved to a single NPC (rare; see §5).

**Invariant:** `drop_rate` is non-null ⟺ `drop_rate_status == "sourced"` ⟺ `drop_rate_raw` is a non-empty string that re-parses to `drop_rate`.

**`collection_log.json` linkage:** v1 does **NOT** modify `collection_log.json` — its `drop_rate` slot stays `null`. `drop_rates.json` is the sole canonical rarity store, and consumers (income, loot filters) **join to it by `item_id`**. (Why not back-fill the clog: a clog row keyed by the fake `"Slayer"` source has no single per-monster rate to receive — §5 — so back-filling would be ambiguous. Keeping the clog untouched avoids that and keeps this brick's write-surface to one new file.)

---

## 4. The rarity grammar — `data/_rarity_grammar.py`

The one genuinely tricky unit, isolated and unit-tested hard. `dropsline`'s rarity field is a small open grammar (documented in `research/data-pipeline-v1.md`):

| Input | → parsed | notes |
|---|---|---|
| `1/512` | `0.001953`, rolls 1 | the common case |
| `1/26.9` | `0.037175`, rolls 1 | decimal denominator |
| `5/128` | `0.039063` | non-unit numerator |
| `2 × 1/128` | `0.015504`, rolls 2 | rolls captured separately; per-roll rate stored, `rolls=2` |
| `Always` / `1/1` | `1.0` | guaranteed |
| `Common`, `Uncommon`, `Varies`, `~` | `null`, status `null-qualitative` | **never** mapped to a fabricated number |
| unparseable | `null`, status `null-unparsed` | logged |

Output: `(drop_rate: float\|None, rolls: int, status: str)`. Pure, deterministic, no I/O.

---

## 5. Sourcing & source resolution — `data/parse_drop_rates.py`

**Query `dropsline` BY ITEM** for each of the 1,701 distinct clog item ids. One bulk-ish set of API calls (batched by item, descriptive User-Agent per the wiki API rules; do not loop naively). **Raw responses are cached to a committed `data/raw/dropsline_*.json`** (the established pattern — no live wiki fetch at validate/build time; the dataset is committed and deterministic).

For each item, `dropsline` returns rows of `{from (the NPC/source), drop_json (rarity, rolls, conditions)}`. We:
1. Parse each row's rarity via `_rarity_grammar`.
2. Emit one `drop_rates.json` record per `(item_id, real_source)`.
3. Tag `source_node_type` (monster/boss/raid/…) from the source.

**The generic-source resolution (note 1 — the load-bearing reason for item-keyed sourcing):** the clog bundles 88 slayer uniques (Abyssal whip, Granite maul, Abyssal dagger, Dragon boots, Dark bow, Occult necklace, Imbued heart, Dust battlestaff, Leaf-bladed weapons, Hydra/Drake parts, …) under a single fake source `"Slayer"`, and others under `"Abyssal Sire"` etc. Querying `dropsline` *by item* sidesteps the bad label entirely: it returns the **real** monsters (Abyssal whip → `Abyssal demon` 1/512 + `Abyssal Sire` …; Granite maul → `Gargoyle`), including the **regular slayer monsters that are not clog sources at all**. So note 1 ("include slayer drops like Abyssal Whip / Granite Maul") falls out for free — no separate curated monster/item list is required.

---

## 6. Boosted / conditional rates — the `variants[]` array (note 2)

The base `drop_rate` is the canonical / most-applicable rate. `variants[]` carries materially-significant conditional rates that `dropsline`/the wiki expose:

- **Slayer on-task / superior** — some uniques drop only or more often while on a slayer task, or only from **superior** slayer monsters (Imbued heart, Eternal gem, the Mist/Dust/etc. battlestaff orbs require the *Bigger and Badder* superior-spawn unlock). These conditions are captured as `{ "condition": "superior only", "drop_rate": …, "drop_rate_raw": … }`.
- **Raid scaling** — CoX (points), ToB (team size/mode), ToA (invocation+points — see §7). v1 stores a canonical reference rate in `drop_rate` and the scaling/notable points in `variants[]`.

Where a condition is real but not machine-parseable, the base rate stands and the condition is noted in `variants[].condition` with `drop_rate: null` (honest). Full enumeration of every permutation is the additive v2 — the raw strings are preserved so no re-sourcing is needed.

---

## 7. Tombs of Amascut — dedicated deep-dive (note 3)

ToA unique drops do **not** have a fixed `1/N`. The per-player unique chance is a **formula of raid level (invocation) and points** (roughly: unique chance rises with raid level up to a cap, then points partition which unique). This is a genuinely hard case and gets its own research+implementation task:

1. **Research** the current ToA unique-drop mechanic from the wiki (the points→chance formula, the per-unique split, the raid-level/cap behaviour) — pinned with sources, not from memory.
2. **Store** a sensible **canonical** `drop_rate` (a documented reference invocation, e.g. a common raid level) so the field is comparable to other rarities, the **formula + key points** in `variants[]`/notes, and the raw wiki expressions in `drop_rate_raw`.
3. **Disclose** in the record + the validator coverage report that ToA rows are invocation-canonical (not a fixed rate). The implementing agent must dig into this rather than approximate it.

(CoX/ToB share the "scaled, not fixed" shape but are less formula-heavy; they reuse this pattern.)

---

## 8. Coverage target & honest nulls

Expected v1 coverage, by clog `node_type` (the real 1,907-record split — these sum to 1,907, no double-counting):

| node_type | count | v1 outcome |
|---|---|---|
| **boss** | 373 | `sourced` from `dropsline` (the core) |
| **raid** | 67 | `sourced` (canonical) + `variants` scaling; ToA per §7 |
| **clue** | 674 | `null-not-in-bucket` — reward-casket model is a clean v2 add |
| **minigame** | 261 | mostly `null-activity` (no kill-based `1/N`) |
| **activity** | 532 | mostly `null-activity` — **BUT** the ~88 generic-`"Slayer"` uniques live in this bucket (the clog files Slayer under "Other"/activity) and **resolve to real monster rates** via item-keyed sourcing (note 1) → `sourced`, not null |

So the 88 slayer uniques are a **subset of the activity bucket rescued by §5's item-keyed resolution**, not a separate category. Partial coverage is **expected and disclosed**, not a failure. The validator prints the coverage breakdown (§9). The honest target: every boss/raid/slayer-unique that `dropsline` exposes gets a real rate; everything else is `null` with a reason.

---

## 9. Validator — `data/validate_drop_rate.py` (iron-gate tradition)

Exits non-zero on any violation; runnable in CI/pre-commit. Invariants:

1. Each `drop_rate` is `null` **or** a float in `(0, 1]`.
2. **No fabrication:** a non-null `drop_rate` has a non-empty `drop_rate_raw` that **re-parses (via `_rarity_grammar`) to the same number** (± float epsilon).
3. Every `null` `drop_rate` has a `drop_rate_status != "sourced"` (a real reason).
4. `rolls` is an integer ≥ 1.
5. Every `item_id` resolves in `item_dictionary.json`; every record's `item_id` appears in `collection_log.json` (coverage stays within the clog scope).
6. `variants[]` entries are well-formed (each has `condition`; `drop_rate` null or in (0,1]; if numeric, a re-parsing `drop_rate_raw`).
7. Envelope/provenance consistency (`record_count == len(records)`, `_excluded` is a list).
8. **Coverage report (informational, non-fatal):** counts by `node_type` + `drop_rate_status`; a dedicated **slayer-resolution line** (how many of the 88 generic-`"Slayer"` uniques resolved to a real monster rate); the ToA-canonical disclosure.

---

## 10. Components (one job each)

- `data/_rarity_grammar.py` — parse a rarity string → `(rate, rolls, status)`. Pure, no I/O. (§4)
- `data/parse_drop_rates.py` — committed builder: query `dropsline` by item (cached raw), resolve sources, parse, emit `drop_rates.json`. Re-runnable, deterministic. (§5)
- `data/_toa_drop_rates.py` — the ToA invocation/points resolver. (§7)
- `data/drop_rates.json` — the canonical output dataset. (§3)
- `data/validate_drop_rate.py` — the committed gate. (§9)
- `data/raw/dropsline_*.json` — committed raw API cache (provenance).

---

## 11. Testing

- **Grammar unit tests** (`_rarity_grammar`): every row of the §4 table + the null/qualitative/unparsed cases + rolls extraction. Exhaustive, since this is the brittle unit.
- **Parser join test** on a small committed raw fixture (e.g. Abyssal whip, Granite maul, a KBD drop, one ToA unique): proves the by-item query → `(item_id, real_source)` resolution (whip → `Abyssal demon` 1/512), source-node-type tagging, and idempotent re-run.
- **Golden rarity set:** a handful of pinned, wiki-verified rarities read from the committed `drop_rates.json` (e.g. Abyssal whip @ Abyssal demon = 1/512; Granite maul @ Gargoyle; a CoX unique; a ToA unique flagged invocation-canonical). Values read at runtime so a re-source updates them.
- **Validator tests:** `validate_drop_rate.py` exits 0 on committed data; constructed-broken inputs (a fabricated rate with no raw; a >1 probability; a null with status `sourced`) each fail.

---

## 12. Scope boundaries / deferred to v2 (designed-for, not built)

- **Clue reward-casket rarities** (674 clue items) — a distinct reward-table model (`DropsLineReward`, per-roll/shared/unique tiers); clean additive dataset later.
- **Full per-variant enumeration** (every team-size/region permutation) — v1 captures the significant conditions (§6) + preserves raw strings; the rest is additive.
- **Regular-monster full drop tables** (the common long tail, for a future "slayer task" loot filter) — `dropsline` supports it; out of v1 clog scope.
- **Consumer wiring** — income gp/hr recompute (drop the `qty_per_hr_or_kill` proxy) and loot-filter rarity beams are each separate follow-up bricks.
- **Live refresh** — v1 is a committed snapshot (like `ge_prices.json`); a daily/live refresh seam is a later concern.
