# Achievement Diaries — Build Status & Resume (committed handoff)

> **Why this file is committed:** the live SDD ledger (`.superpowers/sdd/progress.md`)
> and the agent auto-memory are **not** in git, so a fresh clone / fresh-memory
> session cannot see them. This doc is the durable, in-repo resume record. It
> supersedes the gitignored ledger if that ledger is absent or stale.

**Branch:** `feat/achievement-diaries`  **HEAD:** `b137da0` (origin == local at time of writing)
**Date:** 2026-06-23

## TL;DR
Tasks **1–8** plus **9.1 / 9.2 / 9.5** are DONE, committed, and pushed. The **only**
remaining work is **Task 9 — the full 48-tier reward capture + mandatory owner
editorial review.** It is **fully offline — no wiki access is required** (see
"Source-grounding is offline" below). A prior session reported being "blocked on
wiki 403 / gitignored raws"; that was a **stale, un-fetched view** — disregard it.

## Verified-green at HEAD `b137da0`
- `validate_kg.py` → PASSED (318 nodes / 373 edges / 288 groups; 205 quest, 48 diary)
- `validate_diary_rewards.py` → PASSED (structural)
- `verify_diary_rewards.py` → PASSED (source-grounding, 0 discrepancies)
- KG byte-stable (local assemble == committed)
- `pytest` → 729 passed, 1 skipped (4 `tests/drop_rates/` collection errors are **pre-existing & unrelated** — `ModuleNotFoundError: data._toa_drop_rates`)

## Done (committed @ `b137da0`)
| Task | What | Key files |
|---|---|---|
| 1 | Schema: `supersedes` edge, `count_satisfied` atom, id helpers | `engine/kg/model.py`, `engine/kg/conditions.py`, `kg_ingest/ids.py` |
| 2 | 48 tier nodes + aggregate requirement gates (from 492 tasks) | `kg_ingest/builders/diaries.py` |
| 3 | `goal:achievement-diary-cape` (count_satisfied/48) + 48 `progress_towards` | `kg_ingest/builders/diary_goals.py` |
| 4 | Reward-record format + structural validator | `data/diary_rewards.json`, `data/validate_diary_rewards.py` |
| 5 | Reward builder: regional-item grants + `supersedes` ladder + lamps + extra unlocks | `kg_ingest/builders/diaries.py` |
| 6 | Content-node layer (activity/region existence nodes) | `kg_ingest/builders/content_nodes.py`, `data/diary_content_nodes.json` |
| 7 | `effect → content` edges (the queryable layer) — verified: 4 seed effects emit `item:<id> → activity:/region:` | `kg_ingest/builders/diaries.py` (`_emit_effects`) |
| 8 | Source-grounding verifier + **complete 48-tier committed cache** | `data/verify_diary_rewards.py`, `data/raw/diary_reward_blocks.json` |
| 9.1–9.2 | `validate_kg` diary invariants + trimmed-cape cross-cape link | `data/validate_kg.py` |
| 9.5 | Format reference + effect→content model doc | `data/DIARY_REWARDS.md` |

## Remaining: Task 9 — full 48-tier reward capture (the ONLY work left)
Expand `data/diary_rewards.json` from the **2-tier seed** (`ardougne easy`,
`morytania hard`) to **all 48 tiers**, grounded against the committed cache.

**Source of truth (offline):** `data/raw/diary_reward_blocks.json["<region>:<tier>"].rewards_block`
— the transcribed wiki reward text for every one of the 48 tiers is already in the
repo. Read each block, structure each reward into the record schema. **No wiki needed.**

**Record schema** (see `data/diary_rewards.json` + `data/validate_diary_rewards.py`):
`{region, tier, regional_item{name,item_id,supersedes_item_id}, lamp{amount,min_level,eligible_skills,lamp_item}, effects:[{effect_kind,magnitude,target_facet,target{kind,name},condition,tier_source,source_token}], extra_unlocks:[{reward_type,name,item_id,untracked}], source_url}`

**For each new tier's effects** add its content-node records to
`data/diary_content_nodes.json` (so `_resolve_effect_target` resolves and Task 7's
edges emit). New activity/region nodes are existence nodes — keep them minimal.

**Per-tier loop:**
1. Read the tier's `rewards_block` from the cache → structure the record.
2. Run `verify_diary_rewards.py` — must PASS (0 discrepancies). For a seeded tier it
   also prints `[note] wiki has '...'` = reward facts in the cache you haven't captured
   yet (your transcription checklist).
3. Run `validate_diary_rewards.py` (structural) — must PASS.
4. `python -m kg_ingest.assemble` → `validate_kg.py` PASS → confirm byte-stable.
5. Full `pytest`.

**MANDATORY final gate:** **owner editorial review** of the complete 48-tier reward
set before merge/PR. This is the live-player correctness check no validator can make
— the project's hard human gate (the verbatim-editorial-verification discipline; the
spec is emphatic that the committed reward prose is "a starting point, NOT truth").

## LOCKED DECISIONS (apply to all 48 tiers)
- **`magnitude` = BONUS FRACTION** (additive over baseline): `0.1`=+10%, `0.5`=+50%,
  `1.0`=+100%/double. **NOT** a total multiplier. Matches the quest brick.
- **Non-equipment reward items** absent from `items_equipment.json` (e.g. Bonecrusher)
  → `item_id: null` + `untracked: true` (disclosed). Validator is fatal only on a
  **non-null** id that doesn't resolve.
- **Karamja lamp quirk:** easy = **1,000 XP, ANY level** (distinct
  `Antique lamp (Karamja Diary)`, no min-level); medium = 5,000@30; hard = 10,000@40;
  elite = 50,000@70. The other 11 regions follow the standard ladder
  (2,500 / 7,500 / 15,000 / 50,000 @ 30 / 40 / 50 / 70) — but **capture amount +
  min_level per tier from the cache, never hardcode** (the verifier guards this).
- **Verified item_ids:** Morytania legs 3 = `13114`, legs 2 = `13113`, Ardougne cloak 1 = `13121`.

## Source-grounding is OFFLINE (important)
`verify_diary_rewards.py` is the diary analog of the quest verifier but, unlike it,
does **not** hit the live wiki. The per-tier reward text is already transcribed in the
committed `data/achievement_diaries.json` (with provenance); the cache
`data/raw/diary_reward_blocks.json` is rebuilt **from that committed snapshot**
(`--refresh` rebuilds from `achievement_diaries.json`, offline). `.gitignore:21`
whitelists the cache so it survives clones. → **Task 9 requires no network.**
(Optional freshness re-audit against the live wiki is a separate, future step that
updates `achievement_diaries.json` itself; not needed to finish Task 9.)

## Commands
```
./venv/bin/python data/verify_diary_rewards.py        # offline source-grounding gate
./venv/bin/python data/validate_diary_rewards.py      # structural validator
./venv/bin/python -m kg_ingest.assemble               # rebuild kg/*.json (byte-stable)
./venv/bin/python data/validate_kg.py                 # graph invariants
./venv/bin/python -m pytest -q --continue-on-collection-errors
```

## Pointers
- Spec: `docs/superpowers/specs/2026-06-23-achievement-diaries-design.md`
- Plan: `docs/superpowers/plans/2026-06-23-achievement-diaries.md` (Task 9 section)
- Format reference: `data/DIARY_REWARDS.md`
- After Task 9 + owner review: use `superpowers:finishing-a-development-branch` → PR.
