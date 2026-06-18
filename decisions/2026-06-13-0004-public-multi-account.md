# ADR-0004 — Public, multi-account, hosted; plugin as claim/auth gateway

- **Status:** Accepted
- **Date:** 2026-06-13
- **Produced by:** SPEC.md review (the §1 audience interview). **Amends** [ADR-0001](2026-06-13-0001-web-app-first.md)'s framing of the plugin's role (sequencing unchanged); extends [ADR-0003](2026-06-13-0003-three-layer-architecture.md)'s identity model from a single-account hedge to first-class multi-account.

## Context

The product began as a *personal* mirror of one account (Tiger0295). During the design-doc review the owner re-scoped it: open it to the **public**, host it for real (they will pay for hosting), and let anyone **search any OSRS account on the Hiscores** — not just opted-in profiles. The differentiator (the goal-DAG) must still attach to accounts in a way that respects ownership.

Two facts constrain the design:
- **Public APIs give breadth, not depth.** The Hiscores + WiseOldMan expose skills, XP, boss KC, clues, CA tier, EHP/EHB for *any* ranked account, on demand. But per-item collection log, per-task CAs, diaries, quests, and pets are **not** in any public API we may use (WikiSync forbids third-party use). That data only exists once an account's owner runs a plugin that scrapes it from the logged-in client — which is why RuneProfile has ~199k *opted-in* profiles, not every account.
- **Goals are personal planning** overlaid on an account, so they need an ownership model.

## Decision

Build **Gilded Tome** as a **public, hosted, multi-account** web app with a **two-tier** data model:

1. **Public tier (no claim).** Search any username → on-demand Hiscores/WoM pull → authentic mirror. Cached with a TTL to protect the host IP from rate-limits/bans.
2. **Claimed tier (owner ran the plugin).** The RuneLite **account-hash is the ownership credential** (only the real owner's logged-in client can produce it — no passwords). Claiming = syncing once via the plugin, which unlocks the deep panels (per-item collection log, diaries, quests, pets, per-task CAs) **and** the goal-tracker for that account.

The **RuneLite plugin is therefore the claim/auth gateway**, not just a data-shipper. Web mirror still ships first (it needs no plugin); the goal-tracker can be developed against a seeded local claim before the plugin exists. Storage moves toward **Postgres** for the hosted multi-account site (SQLite for dev); the exact host, domain, cache strategy, and claiming UX are tracked in [SPEC §9](../SPEC.md#9-open-decisions).

## Alternatives considered

- **Stay personal / single-account** — rejected. The owner explicitly wants a public, searchable product and will fund hosting.
- **Goals for any signed-in user via OAuth (Discord/Google), no plugin** — rejected. Maximizes reach but gives only an *unverified* claim on an account; the owner preferred verified ownership tied to the game client.
- **Public mirror only, no goals for others** — rejected. Throws away the differentiator for everyone but the operator.
- **Search only opted-in profiles (pure RuneProfile model)** — rejected. We can pull *any* ranked account's public data on demand, which is strictly broader for the public tier.

## Consequences

- **Easier:** the public mirror is reachable with just the backend proxy + cache (no plugin, no auth); the account-hash gives passwordless verified ownership for the claimed tier; supports **all** game modes (main/ironman/HCIM/UIM), retiring the old "HCIM vs ironman" question.
- **Harder / constrained:** the **plugin moves onto the critical path** to the public differentiator (amends ADR-0001's "optional, later" framing). Public scale forces **caching + rate-limit/back-off** on the Hiscores proxy and likely a **SQLite → Postgres** migration + a real **host + domain** (cost). A **claiming UX** (how an owner proves the account-hash to edit goals — a plugin-issued token/session) must be designed in the `feat/runelite-plugin` and `feat/api` plans. The roadmap reorders: backend ingest + account-search come early.

## Observability table (per condition-atom family × source)

This is the **authority the engine's three-valued (Kleene) evaluation reads** (engine↔advisor contract §6/§6.4) to decide *Known* vs `UNKNOWN` for each KG condition-atom. It is the explicit table the contract's §13.4 defers to. **Validated against real Hiscores lookups (a mid-game ironman + a near-maxed main), 2026-06-18.**

> **Cardinal rule — Hiscores absence ≠ zero.** A ref-bearing atom over a family that is *absent-and-not-manually-asserted* evaluates to `UNKNOWN`, **never `False`**. An activity (boss KC, clue/minigame score) only appears once the account clears that activity's **population-dependent tracking cutoff**, so a missing score could mean *0* **or** *below cutoff* — indistinguishable, hence `UNKNOWN`. (Per-skill **levels/XP are an exception**: they are returned for any tracked account even when that skill's *rank* is unranked, shown as `--`.) A wholly-untracked account → contract `Problem{missing_state}`.

**Sources:** `hiscores` (public, no claim — official OSRS Hiscores `index_lite` for the account's board) · `plugin` (claimed; three sub-streams — **core**: quests (state not_started/in_progress/completed)/diaries/per-task CAs/pets/equipment · **bank** §9.7: bank contents→`item`, banked XP, GE/HA value · **clog**: obtained collection-log slots) · `manual` (§6/§9.3 user-confirmed; overrides; monotonic reconcile) · `derived` (engine-computed from other atoms) · `inferred` (monotonic back-fill, deferred).

| Condition atom | Hiscores (public) | Plugin (claimed) | Manual | Derived |
|---|---|---|---|---|
| `skill_level` / skill XP | ✅ any **tracked** account — level+XP present even when per-skill rank is `--` | ✅ | ✅ | — |
| `combat_level` | ❌ **not a Hiscores field** | ✅ (RuneLite HiScore plugin) | ✅ | ✅ from the combat skills |
| `account_type` | ✅ via **which board ranks them**: main / Ironman / Ultimate / Hardcore / GIM + HCGIM (group size 2–5) / Seasonal (DMM·Leagues·Tournament) / Skiller / 1-Def | ✅ | ✅ | — |
| `kill_count` | ⚠️ score only once tracked; **appear-threshold is population-dependent → absence = `UNKNOWN`, not 0** | ✅ | ✅ | — |
| `clue_scrolls` (clue tiers; minigames LMS/Rifts/PvP-Arena/…) | ⚠️ same — absence = `UNKNOWN` | ✅ | ✅ | — |
| `combat_achievement_points` (Combat Achievements total) | ✅ (tracked activity; same cutoff caveat) | ✅ | ✅ | — |
| collections-logged **count** | ✅ **count only** (shown even when rank `--`) — never *which* slots | ✅ | ✅ | — |
| `quest_points` (quest points) | ❌ not on Hiscores | ✅ (from quests) | ✅ | ✅ from `quest` |
| `quest` (state: not_started/in_progress/completed) | ❌ | ✅ core — completed; ⚠️ in_progress is partial state | ✅ | — |
| `achievement_diary` (region:tier; state not_started/in_progress/completed — a tier completes when all its tasks are done) | ❌ | ✅ core | ✅ | — |
| `combat_achievement` (per task; binary completed/not) | ❌ (only the points *total* is public) | ✅ core | ✅ | — |
| `item` (bank / equipment) | ❌ | ✅ bank (§9.7) | ✅ | — |
| `clog_slot` (obtained) | ❌ | ✅ clog | ✅ | — |
| `access:*` / `is_unlocked` | — | — | — | ✅ engine, from grants + the atoms above |

**Notes.**
- **Account-type family mapping.** The board identifies the exact type; the engine maps it to the **rule families** (main / ironman — HCIM, GIM, HCGIM ride here — / UIM) per contract §8. A dead HCIM/HCGIM that reverts to standard iron is then observed on the iron board.
- **GIM / HCGIM** Hiscores are **group-scoped** (contributed XP by group size); an individual member's skills/KC still come from that member's own (iron) account lookup.
- **`derived` atoms** (`combat_level`, `quest_points`, `access:*`/`is_unlocked`) are never read from a source — the engine computes them from the observed atoms above, and they inherit `UNKNOWN` if any input is unknown (Kleene fold).
- **WiseOldMan** adds derived public metrics (EHP/EHB/gains/history) over the same Hiscores families; it observes no *new* atom family.
