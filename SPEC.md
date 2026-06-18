# Gilded Tome — Design Document

> **Spec-Driven Development.** This file is the living **design document**: the project's current architecture and roadmap. Per-change **plans** live in [`plans/`](plans/); **architecture decisions** (ADRs) live in [`decisions/`](decisions/). Changes flow **plan → code** (never the reverse); this document records current state. Adrian owns it — scope changes happen here, and in a plan, before code.

**Status:** Active · `feat/web-foundation` shipped → PR #1 · `feat/goal-engine` design+data locked (the engine↔advisor contract, KG schema v1, data foundation) · updated 2026-06-18
**Scope:** public · hosted · multi-account — search any OSRS Hiscores account (Tiger0295 = reference/dev account) · **Repo:** `retrogramx/osrs-planner-tool` (public) · `main` protected, PR-only.

## 0. Document model (how this maps to SDD)

| Artifact | Where | Role |
|---|---|---|
| **Design document** | this file | Overall architecture + current state + roadmap. Living. |
| **Plans** | [`plans/`](plans/) | One dated plan per change. Sections: Context · Goals/Non-goals · Key decisions · Intended changes · Verification · References. Passes the "two-engineers test"; drives code; frozen once merged. |
| **ADRs** | [`decisions/`](decisions/) | MADR-format records of choices with long-term architectural impact. Persist indefinitely. |

All external references use **durable citations** (title, description, accessed date, permanent URL) — see [§8](#8-references-durable-citations).

---

## 1. Product

**Gilded Tome** is a **public, hosted web app** where anyone can **search any OSRS account on the Hiscores** and see it in an authentic, in-game-faithful **mirror** — **and** which adds the differentiator no existing tool nails: a deeply customizable, **account-type-aware goal tracker** built on a prerequisite **dependency graph** (quest → access → gear → boss).

Data arrives in **two tiers**. A **public mirror for any searched account** — skills, XP, boss KC, clues, CA tier, EHP/EHB — pulled **on demand** from the Hiscores + WiseOldMan and cached. And a **deeper claimed-account layer** — per-item collection log, diaries, quests, pets, and the goal tracker — that unlocks when the account's **owner claims it via the RuneLite plugin**, whose account-hash is the ownership credential. That deep per-account data does not exist in any public API until the owner syncs it (the same reason RuneProfile holds only ~199k *opted-in* profiles, not every account).

RuneProfile mirrors *state* but has no goals; RuneLite's Goal Tracker tracks goals but shallowly and per-client. We marry the two — and open it to any account. The goal-DAG productizes a system the author already maintains by hand. **Web mirror first; the RuneLite plugin follows** as both the *deep-data shipper* and the *account-claim / auth gateway* that unlocks the goal tracker for an owner (see [ADR-0001](decisions/2026-06-13-0001-web-app-first.md), [ADR-0004](decisions/2026-06-13-0004-public-multi-account.md)).

## 2. Architecture (current state)

Three layers + a plugin seam (see [ADR-0003](decisions/2026-06-13-0003-three-layer-architecture.md), [ADR-0004](decisions/2026-06-13-0004-public-multi-account.md)):

1. **Ingest** — `httpx` clients per source (Hiscores, WiseOldMan, TempleOSRS), proxied through FastAPI (CORS), normalized to pydantic. **Search is an on-demand pull**: a username resolves to a live Hiscores/WoM fetch, **cached with a TTL** so public traffic can't get the host IP rate-limited or banned.
2. **Static game-data** — own re-derived JSON/modules: collection-log tabs, CA tiers, diary regions/tiers, quest list, the **account-type-aware** prerequisite graph.
3. **State (multi-account)** — accounts are **first-class and many** (single-account is no longer a special case): accounts, snapshots, goals, goal_dependencies, projects/milestones, templates, manual overrides, plus a public-mirror cache.

**Identity & claiming:** the `/sync` endpoint + RuneLite **account-hash** are the ownership model — an owner *claims* their account by syncing once from their logged-in client, and that hash is the credential that unlocks deep-data sync + goal editing for that account (see [ADR-0004](decisions/2026-06-13-0004-public-multi-account.md)).

**Tech stack** ([ADR-0002](decisions/2026-06-13-0002-frontend-vanilla-no-build.md)): frontend = vanilla HTML/CSS/JS, no build, token-driven, mobile-first, self-hosted assets (`web/`); backend = FastAPI + pydantic + httpx (`src/osrs_planner/`); storage = **SQLite for dev, likely Postgres once hosted** (open — [§9](#9-open-decisions)); **hosting = a real paid host + domain** (open); plugin = thin Java RuneLite (deep-data shipper + claim/auth).

## 3. Data sources

Two tiers: **public** (any searched account, pulled on demand + cached) and **claimed** (unlocked once the owner syncs via the plugin).

| Data | Source | Tier |
|---|---|---|
| Skills, XP, total, ~80 boss KC, all clue tiers | Official Hiscores (proxy) | public |
| Collections-Logged count, CA points/rank | Official Hiscores (proxy) | public |
| EHP / EHB / gains / history | WiseOldMan | public |
| Per-item collection log + KC | RuneLite plugin (or TempleOSRS, if that account synced) | claimed |
| Diaries, quests, pets, per-task CAs | RuneLite plugin (WikiSync forbidden — [§8](#8-references-durable-citations)) | claimed |
| Goals (DAG, custom) | the app, attached to a claimed account | claimed |

## 4. Goal model

Unified, discriminated `Goal` table + dependency DAG + grouping + templates. Types: SKILL_LEVEL, SKILL_XP, TOTAL_LEVEL, TOTAL_XP/EHP/EHB, BOSS_KC, CLUE_COUNT, CLOG_SLOTS, CLOG_ITEM, CA_POINTS/CA_TIER/CA_TASK, DIARY, QUEST, ITEM_QTY, MANUAL. Dependencies as `GoalDependency{goal_id, requires_goal_id, kind}`. Goals belong to a **claimed account** (owner verified by account-hash); the prereq graph + planning logic are **account-type-aware** — an ironman must self-acquire where a main can buy, so the optimal path differs by game mode. Detailed schema is specified in the `feat/goal-tracker` plan; the prerequisite-graph **evaluation** (Kleene three-valued unlock/prereq/next-step logic over the KG) is the `feat/goal-engine` brick, designed in the engine↔advisor contract and KG schema v1 and built on a hand-authored KG fixture before ingest exists.

## 5. Visual design language

"**Yesteryear**" (named for the OSRS soundtrack track) — authentic OSRS materials (textured stone, riveted gold, real RuneScape fonts, yellow-on-black shadowed text) for the account mirror; calm modern dark+gold for the tracker. The aged, old-school feel makes the whole app read as an in-world tome, fitting the product name *Gilded Tome*. **The rendered foundation is the visual spec:** [`web/foundation.html`](web/foundation.html) (tokens/palette/type) and [`web/components.html`](web/components.html) (component library + the locked in-game-faithful skills panel).

## 6. Roadmap (bricks)

One feature branch + PR each. Detailed scope/acceptance lives in each brick's plan when written.

| Branch | Scope | Status | Plan |
|---|---|---|---|
| `feat/web-foundation` | Design system + skills panel | ✅ PR #1 | (built pre-SDD; recorded in this doc) |
| `feat/app-shell` | Account-agnostic shell: header + search box + mirror/tracker layout | planned | [plan](plans/2026-06-13-app-shell.md) |
| `feat/backend-ingest` | httpx clients + FastAPI proxy + cache (Hiscores / WoM) | todo | — |
| `feat/account-search` | Search any username → live **public mirror** (first public feature) | todo | — |
| `feat/store` | Multi-account state (SQLite → Postgres) | todo | — |
| `feat/clog-panel` · `feat/quests-diaries-cas` | Deep panels (populated for claimed accounts) | todo | — |
| `feat/goal-engine` | The differentiator's brain — deterministic engine over a hand-authored KG fixture (Result envelope + Kleene + cards). **Design:** engine↔advisor contract (`docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`) + KG schema v1 (`research/kg-schema-v1.md`). **Data:** the source datasets in `data/*.json` (the engine runs on a KG fixture for now, not these directly). | in progress | (this plan) |
| `feat/goal-tracker` | Per-account STATE layer: the goal-DAG DDL (§9 of the contract — `goal`/`account_progress`, two-writer rule) + tracker UI. Inherits the engine's `Result`/card shapes. | todo | — |
| `feat/kg-ingest` | **Separate brick:** the data pipeline that builds the real KG (`data/*.json` → `node`/`edge`/`condition_*` per KG schema v1) which the engine's `KGStore` loads. `feat/goal-engine` ships first on a hand-authored fixture and does NOT block on this. | todo | — |
| `feat/runelite-plugin` | Java sync → `/sync`: deep-data shipper **+ account claim/auth** | todo | — |
| `feat/hosting` | Deploy to the real host + domain + cache / rate-limit hardening | todo | — |

## 7. Architecture decisions (ADRs)

- [ADR-0001 — Web app first, RuneLite plugin later](decisions/2026-06-13-0001-web-app-first.md)
- [ADR-0002 — Frontend: vanilla HTML/CSS/JS, no build step](decisions/2026-06-13-0002-frontend-vanilla-no-build.md)
- [ADR-0003 — Three-layer architecture + plugin identity model](decisions/2026-06-13-0003-three-layer-architecture.md)
- [ADR-0004 — Public, multi-account, hosted; plugin as claim/auth gateway](decisions/2026-06-13-0004-public-multi-account.md) *(amends ADR-0001's framing of the plugin's role)*

## 8. References (durable citations)

- **RuneStar fonts** — extracted OSRS fonts (CC0), release `1.103-0`. https://github.com/RuneStar/fonts/releases/tag/1.103-0 (accessed 2026-06-13).
- **RuneProfile** — reference OSRS account site + plugin (studied, not copied; no LICENSE = all-rights-reserved). https://github.com/ReinhardtR/runeprofile (accessed 2026-06-13, default branch — living).
- **WiseOldMan API** — player metrics / gains / EHP-EHB. https://docs.wiseoldman.net/api (accessed 2026-06-13 — living).
- **OSRS Hiscores API** — `index_lite.json`. https://oldschool.runescape.wiki/w/Application_programming_interface (accessed 2026-06-13).
- **TempleOSRS API** — per-item collection log. https://templeosrs.com/api_doc.php (accessed 2026-06-13).
- **WikiSync** — has diary/quest/CA data but **forbids third-party API use**. https://oldschool.runescape.wiki/w/RuneScape:WikiSync (accessed 2026-06-13).
- **RuneLite Plugin Hub** — plugin dev + local run (no merge needed for personal use). https://github.com/runelite/plugin-hub (accessed 2026-06-13).
- **MADR** — ADR format used in `decisions/`. https://adr.github.io/madr/ (accessed 2026-06-13).

*Game assets (fonts, sprites) are Jagex IP used under fan-project terms; the app carries a Jagex disclaimer in its footer.*

## 9. Open decisions

Resolve here (and in the relevant brick's plan) before building that brick:
- ~~Prerequisite graph: curated/opinionated path vs neutral graph the user orders.~~ **Resolved** (KG schema v1 + contract §13.1): a **neutral facts graph** is the source of truth; the engine never auto-picks a route — it returns all branches as choices, with a crude `fewest_unmet_leaves` efficiency hint. Curated orderings are an optional opinion overlay that must be a valid topo order of the facts graph.
- Project/milestone roll-up: equal-weight vs EHP/EHB-weighted.
- Google Sheet role: one-time import (seed the author's DAG) vs ongoing sync.
- **Storage:** SQLite (dev) → Postgres (hosted multi-account)? Confirm the migration point.
- **Host + domain:** which host (Fly / Render / Railway / VPS / Cloudflare) and domain (e.g. `gildedtome.com`)?
- **Cache + rate-limit:** TTL + back-off strategy for on-demand Hiscores pulls at public scale.
- **Claiming UX:** how an owner proves the account-hash to edit goals (plugin-issued token / session).

*Resolved by [ADR-0004](decisions/2026-06-13-0004-public-multi-account.md): hosting → **hosted / paid**; account-type → **support all game modes** (goal logic is account-type-aware), so the old "HCIM vs ironman" question is moot — Tiger0295 is simply the reference account.*
