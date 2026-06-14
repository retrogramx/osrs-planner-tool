# Gilded Ledger — Design Document

> **Spec-Driven Development.** This file is the living **design document**: the project's current architecture and roadmap. Per-change **plans** live in [`plans/`](plans/); **architecture decisions** (ADRs) live in [`decisions/`](decisions/). Changes flow **plan → code** (never the reverse); this document records current state. Adrian owns it — scope changes happen here, and in a plan, before code.

**Status:** Active · `feat/web-foundation` shipped → PR #1 · updated 2026-06-13
**Account:** Tiger0295 (OSRS Ironman) · **Repo:** `retrogramx/osrs-planner-tool` (public) · `main` protected, PR-only.

## 0. Document model (how this maps to SDD)

| Artifact | Where | Role |
|---|---|---|
| **Design document** | this file | Overall architecture + current state + roadmap. Living. |
| **Plans** | [`plans/`](plans/) | One dated plan per change. Sections: Context · Goals/Non-goals · Key decisions · Intended changes · Verification · References. Passes the "two-engineers test"; drives code; frozen once merged. |
| **ADRs** | [`decisions/`](decisions/) | MADR-format records of choices with long-term architectural impact. Persist indefinitely. |

All external references use **durable citations** (title, description, accessed date, permanent URL) — see [§8](#8-references-durable-citations).

---

## 1. Product

A personal web app that **mirrors an OSRS ironman account** (Tiger0295) in authentic, in-game-faithful UI, **and** adds the differentiator no existing tool nails: a deeply customizable, **ironman-aware goal tracker** built on a prerequisite **dependency graph** (quest → access → gear → boss).

RuneProfile mirrors *state* but has no goals; RuneLite's Goal Tracker tracks goals but shallowly. We marry the two. The user already maintains this graph by hand in a Google Doc — we're productizing their own system. **Web app first; a thin RuneLite plugin follows** to capture the data public APIs can't (see [ADR-0001](decisions/2026-06-13-0001-web-app-first.md)).

## 2. Architecture (current state)

Three layers + a plugin seam (see [ADR-0003](decisions/2026-06-13-0003-three-layer-architecture.md)):

1. **Ingest** — `httpx` clients per source (Hiscores, WiseOldMan, TempleOSRS), proxied through FastAPI (CORS); normalized to pydantic models.
2. **Static game-data** — own re-derived JSON/modules: collection-log tabs, CA tiers, diary regions/tiers, quest list, the ironman prerequisite graph.
3. **State (SQLite)** — accounts, snapshots, goals, goal_dependencies, projects/milestones, templates, manual overrides.

A `/sync` endpoint + RuneLite hashed-account-hash identity are designed in now so the plugin slots in later without reworking the schema.

**Tech stack** ([ADR-0002](decisions/2026-06-13-0002-frontend-vanilla-no-build.md)): frontend = vanilla HTML/CSS/JS, no build, token-driven, mobile-first, self-hosted assets (`web/`); backend = FastAPI + pydantic + httpx (`src/osrs_planner/`); storage = SQLite; plugin (later) = thin Java RuneLite.

## 3. Data sources

| Data | Source | Auto? |
|---|---|---|
| Skills, XP, total, ~80 boss KC, all clue tiers | Official Hiscores (proxy) | auto |
| Collections-Logged count, CA points/rank | Official Hiscores (proxy) | auto |
| EHP / EHB / gains / history | WiseOldMan | auto |
| Per-item collection log + KC | TempleOSRS (Tiger0295 synced 260/1701) | semi-auto |
| Diaries, quests, pets, per-task CAs | none allowed (WikiSync forbidden — [§8](#8-references-durable-citations)) → manual now, plugin later | manual |

## 4. Goal model

Unified, discriminated `Goal` table + dependency DAG + grouping + templates. Types: SKILL_LEVEL, SKILL_XP, TOTAL_LEVEL, TOTAL_XP/EHP/EHB, BOSS_KC, CLUE_COUNT, CLOG_SLOTS, CLOG_ITEM, CA_POINTS/CA_TIER/CA_TASK, DIARY, QUEST, ITEM_QTY, MANUAL. Dependencies as `GoalDependency{goal_id, requires_goal_id, kind}`. Detailed schema is specified in the `feat/goal-tracker` plan when that brick is built.

## 5. Visual design language

"**Gilded Ledger**" — authentic OSRS materials (textured stone, riveted gold, real RuneScape fonts, yellow-on-black shadowed text) for the account mirror; calm modern dark+gold for the tracker. **The rendered foundation is the visual spec:** [`web/foundation.html`](web/foundation.html) (tokens/palette/type) and [`web/components.html`](web/components.html) (component library + the locked in-game-faithful skills panel).

## 6. Roadmap (bricks)

One feature branch + PR each. Detailed scope/acceptance lives in each brick's plan when written.

| Branch | Scope | Status | Plan |
|---|---|---|---|
| `feat/web-foundation` | Design system + skills panel | ✅ PR #1 | (built pre-SDD; recorded in this doc) |
| `feat/app-shell` | Header + left-mirror / right-tracker layout | planned | [plan](plans/2026-06-13-app-shell.md) |
| `feat/clog-panel` | Collection-log panel | todo | — |
| `feat/quests-diaries-cas` | Quests / diaries / CA panels | todo | — |
| `feat/goal-tracker` | The differentiator — goal-DAG | todo | — |
| `feat/backend-ingest` · `feat/sqlite-store` · `feat/goal-engine` · `feat/api` | Backend + live data | todo | — |
| `feat/runelite-plugin` | Thin Java sync → `/sync` | todo | — |

## 7. Architecture decisions (ADRs)

- [ADR-0001 — Web app first, RuneLite plugin later](decisions/2026-06-13-0001-web-app-first.md)
- [ADR-0002 — Frontend: vanilla HTML/CSS/JS, no build step](decisions/2026-06-13-0002-frontend-vanilla-no-build.md)
- [ADR-0003 — Three-layer architecture + plugin identity model](decisions/2026-06-13-0003-three-layer-architecture.md)

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
- Prerequisite graph: curated/opinionated ironman path vs neutral graph the user orders.
- Project/milestone roll-up: equal-weight vs EHP/EHB-weighted.
- Google Sheet role: one-time import vs ongoing sync.
- Account-type confirm: docs say HCIM; live data says regular ironman.
- Hosting: local-only vs hosted (affects proxy IP-ban / WOM key).
