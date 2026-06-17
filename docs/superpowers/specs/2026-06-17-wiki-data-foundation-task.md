# Wiki Data Foundation — extraction task (small spec)

- **Date:** 2026-06-17
- **Status:** Draft for review (task spec; no extraction runs until approved)
- **Parent:** the deferred *ingest* brick of [`2026-06-15-engine-advisor-contract-design.md`](2026-06-15-engine-advisor-contract-design.md)
- **Inputs:** [`research/wiki-source-catalog.md`](../../../research/wiki-source-catalog.md) + [`research/wiki-source-catalog.maps.json`](../../../research/wiki-source-catalog.maps.json) (the per-domain map of where every data point lives)

## 0. Why
Every scenario bug so far (Mahogany Homes rates, ironman money, Dagannoth Kings, the 404) was a **data hole, not a logic hole.** The engine↔advisor contract holds; the foundation under it doesn't exist yet. This task builds that foundation: extract **all** needed data points from the OSRS Wiki into verified JSON datasets mapped to the KG schema, so the engine makes account-accurate decisions instead of plausible guesses.

## 1. Approach — hybrid (decided)
- **Structured → deterministic scripts (exact, re-runnable, no LLM):**
  - **Bucket API** (`api.php?action=bucket`) — quests, items/equipment bonuses, **money-making (kc/hr + gp/hr)**, combat achievements, clues, minigames.
  - **`Module:Questreq/data`** (`?action=raw`) — the full quest-prerequisite DAG (~1,900 entries, `ironman`/`boostable` flags).
  - **`prices.runescape.wiki`** (`/latest` + `/mapping`) — live GE prices + item id→name/alch metadata.
  - **banked-experience `Activity.java` / `ExperienceItem.java`** → JSON (item→skill/level/xp/secondaries/output chains). BSD-2, attribution kept.
- **Semi-structured → agent fleet (extract) + adversarial verify (second agent):**
  - Skill **xp/hr** rates (rate-chart templates + per-skill guides via `?action=raw`) — *automate + heavy verify* (decided).
  - **Optimal quest order** (main + ironman), achievement diaries, unlocks/transport.
  - **`Ironman money making guide`** — the canonical iron-GP source (the page we missed; MUST be included).
  - **Collection Log** — the full tree (Bosses / Raids / Clues / Minigames / Other): ~1,906 slots / ~1,701 unique entries → each slot's item(s) + source(s), with drop rates pulled from per-source pages (some slots are shared across sources). Cross-check against the bosses / clues / minigames / items domains for consistency.
- **Verify pass (mandatory):** every extracted record is checked by a second agent against the source; an adversarial check would have caught DKs and the rate error. Plus a **golden set** of ~30 hand-verifiable facts spot-checked at the end.

## 2. Output
Per-domain JSON under `data/` (or `research/data/`), keyed to KG schema v1 + contract shapes. Every record carries **provenance** (`source_url`, `accessed_at`, `license: CC BY-NC-SA 3.0`; BSD-2 for the plugin-derived set). A final **coverage report** lists what's filled vs. gaps (no silent truncation).

## 3. Account-type correctness (baked in — our hard-won rules)
The extractor encodes these so the fleet can't repeat past errors:
- **cost = `{gold, gather_time}`** for everyone; income **realized per account type** — GE for mains, **High Alch / shops / coin drops** for irons (never GE).
- A combat method is **iron income only if its drops realize as coins**; tag `main_only` otherwise (e.g. Dagannoth Kings = gear/Prayer, NOT gold; Zombie Pirates/green-dragons/Vorkath = iron gold).
- **Completeness:** include minigame methods (Mahogany Homes) and passive sources (Managing Miscellania, farming/birdhouse runs); flag passive resource sources as net-gold **sinks**, not income.
- **Honest rates:** mark low/unknown, never fabricate; objective values only.
- **HCIM/GIM = ironman data;** families = main / ironman / UIM.
- Each method record: `{gear, stat/quest prereqs, outputs {gold,xp,resources}, internal_cost, realization_channel, account_types, rate}`.

## 4. Fleet/workflow shape
A single `Workflow` over **15 domains** (the catalog's 14 + Collection Log):
1. **Pull (scripts):** deterministic fetch of Bucket/Module/prices/plugin-data → raw JSON.
2. **Extract (agents):** one per semi-structured domain, reading its catalog-mapped source via `?action=raw`.
3. **Verify (agents):** adversarial second pass per domain (refute/correct against source).
4. **Normalize + critic:** merge to schema-shaped JSON; golden-set spot-check; completeness critic ("what's missing / unverified?").

## 5. Scope boundary
- **Sourcing:** OSRS Wiki only, + the two BSD-2 plugin datasets (attributed). No third-party sites.
- **Produces DATA, not engine code** — feeds the deferred ingest brick.
- Skill rates: automated + verified (decided), with uncertain values flagged for a later manual pass (`research/skill-rate-baseline-task.md` remains the fallback for any the fleet can't pin).
- **Collection Log has two halves:** this task collects the **static tree** (slots → items → sources + drop rates). *Which slots a player has obtained* is **account state** — a separate ingestion stream (in-game collection log / a RuneLite collection-log feed, like the bank feed in §9.7), feeding the future **completionist lens** ([[completionist-collection-log]]). The lens is a deferred *feature*; its underlying data starts being collected here.

## 7. Rollout (decided)
- **Output home:** `data/` at the repo root (JSON per domain; raw pulls under `data/raw/`).
- **Proof run first (3 domains)** before the full 15, to validate the pipeline + output shape + verify pass cheaply:
  1. **Quests** — `Module:Questreq/data` (`?action=raw`) + Bucket `quest` (structured/script path).
  2. **Money-making** — Bucket `money_making_guide` (structured/script path).
  3. **Ironman money making guide** — semi-structured page (agent extract + verify; exercises the account-type-correctness rules).
  Each: pull → adversarial verify → go/no-go report. The full 15-domain run proceeds only after the proof run's shape is approved.

## 8. Output envelope (frozen — from the proof run)
Every domain file uses the same envelope so a generic loader works across all 15:
```json
{
  "_provenance": {
    "domain": "...",
    "source_urls": ["..."],
    "source_query": null,
    "accessed": "2026-06-17T00:00:00Z",
    "license": "CC BY-NC-SA 3.0",
    "extraction_method": "script | agent",
    "raw_files": ["data/raw/..."],
    "record_count": 0,
    "completeness": { "bounded_by": "...", "universe_count": null, "records_count": 0, "known_missing": [] },
    "domain_stats": {}
  },
  "records": [],
  "_excluded": []
}
```
Rules: payload key is **always `records`**; `_excluded` is never counted; domain-specific counters live in `domain_stats`; **never report `complete` when a bounded-universe gap exists** — disclose it in `completeness.known_missing`. **Graph domains** (quests, and future skill/diary/achievement graphs): strip the `Started:*` convention, normalize whitespace, and emit real-but-absent targets as stub nodes or a `_dangling` list — no silent dangles into the KG. **Value fields** (`gp_value`, `gp_hr`, …) carry a `unit`/`basis` and a snapshot date (gp is price-volatile). The **account-type gate** (realization_channel set; no GE-dependent method marked iron-viable; risk flags) is a reusable check applied to every account-sensitive domain.

## 9. Nuances to encode (from the envelope probe)
The proof files surfaced real modeling nuances; bake these into the full run:
1. **Pricing basis / audience (money domains).** `money_making.json` is **GE-priced = a MAIN dataset** (outputs `pricetype: gemw`); its `gp_value` is *per hour* and assumes GE sale. Add `pricing_basis` (`ge|store|value`) + `audience` (`main|f2p`) to each money record; the engine **never shows GE `gp_value` to an ironman** — it recomputes from `outputs` via the iron realization channel, or defers to `ironman_money_making.json`.
2. **F2P is a third account axis.** 117/627 methods are F2P (`members:false`). Account types = {main, ironman (HCIM/GIM), UIM} × {members, F2P}; carry `members` on every relevant record.
3. **GE-arbitrage / buy-process-sell methods** (e.g. *Making divine battlemage potions* ~14M/hr) are **main-only and not an "activity"** — buy inputs on GE, sell outputs on GE. Flag `requires_ge: true` so they're excluded for irons and can be categorized separately.
4. **Variants.** Some methods have versions (`version: "Wilderness"`, "Budget"/"Max efficiency", "(Contract of …)"). Add a `variant` field linking a base method's versions instead of only name-mangling.
5. **Quest prereq STATE — "Started:" = partial-completion.** A prereq like `Started:Waterfall Quest` means *started, not completed* — a real OSRS nuance that maps to the **`quest_stage`** requirement (G1 scale-gap in the contract spec). Model prereqs as `{quest, stage: started|completed}`, not a bare name.
6. **Edge-integrity (refined).** Split dangling edges three ways: **`Started:` → a `stage` flag** (not a dangle); **whitespace typos** (`"Watchtower "`) → normalize; **real-but-missing quests** (`Beneath Cursed Sands`, `Land of the Goblins`) → resolve via the completeness fix (full quest universe), logged in `known_missing`.
7. **Honest nulls.** `gp_hr: null` is valid (qualitative early methods); consumers handle gracefully. Wilderness/risk flags verified present.
8. **Node-type classification (quests domain is really three).** `Module:Questreq` lumps **quests + miniquests + achievement diaries** (e.g. `Easy Ardougne Diary`). Classify each entry `node_type: quest|miniquest|diary`; do not lump all as "quest"; **dedupe against the achievement-diaries domain.**
9. **Outputs: direct coins vs aggregate pseudo-items.** Value-priced outputs split into literal **`Coins`** (direct, iron-realizable) and **aggregate rollups** (`Gem drop table` — not a real item). Iron income recompute = direct coins + alch/use value of real items; **expand or flag aggregate "X drop table" pseudo-outputs.**
10. **"mixed" realization = multi-output (gold + XP + resources)** — confirms the multi-output method model; a money method and a training method are frequently the *same activity* (Green dragons = gold + Prayer/Melee XP; Vorkath = gold + Slayer XP). Capture all outputs, not just gold.
11. **Ironman skill-req semantics:** an `ironman:true` skill req means *"a main buys past this requirement; the iron must train the skill to make the item"* (e.g. The Knight's Sword → Mining/Smithing/Cooking for irons). Preserve the flag; surface it as an iron-only extra requirement.
12. **Don't auto-detect "buy-process-sell" by input cost** — high input ≠ arbitrage (Zulrah = expensive *supplies*, not flipping). Use the dedicated `Ironman money making guide` as the authoritative iron filter + a category-aware rule, not a naive cost heuristic.

## 6. Done criteria
Golden set passes · every method has the required fields + provenance · account-type tags present · coverage report emitted with gaps logged · datasets load against the KG schema.

## 10. Status (2026-06-17) — COMPLETE v1
Built and committed on branch `research/wiki-data-foundation`. **17 datasets in `data/`** = the 16 domains + a canonical **`item_dictionary`** (the universal item↔id join key, 15,496 items, tradeable + untradeable). All **P0/P1/P2/P3 cleared and independently re-validated**: frozen envelope uniform across all files; account-gate fields `{audience, pricing_basis, realization_channel, requires_ge}` standardized across the 5 money domains; iron income gated (no GE-priced method shown as iron-viable; DKs-class drops excluded); join keys in place (`items_equipment.item_id` 98.3%, `banked_xp` ~47% — remainder = unresolvable RuneLite enum constants, disclosed). **Remaining:** skill xp/hr rates are partial (the hardest domain; `research/skill-rate-baseline-task.md` is the manual fallback) + minor disclosed gaps. The foundation is wireable into the engine.
