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
