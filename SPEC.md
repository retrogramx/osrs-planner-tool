# Gilded Ledger — Specification

> **Spec-Driven Development source of truth.** Nothing gets built that isn't described here. Adrian owns this document; changes to scope happen *here first*, then in code via a feature branch + PR.

**Status:** Active · Foundation (Block 0–1) complete · 2026-06-13
**Account:** Tiger0295 (OSRS Ironman)
**Repo:** `retrogramx/osrs-planner-tool` · default branch `main` (protected, PR-only)

---

## 1. Product

A personal web app that **mirrors an OSRS ironman account** in authentic, in-game-faithful UI, **and** adds the thing no existing tool nails: a deeply customizable, **ironman-aware goal tracker** built on a prerequisite **dependency graph** (quest → access → gear → boss).

**Differentiator (the whole reason this exists):** RuneProfile mirrors *state* but has no goals; RuneLite's Goal Tracker tracks goals but shallowly. Nobody marries an authentic account mirror with a deep, dependency-aware goal tracker. The user already maintains this graph by hand in a Google Doc (`Tiger.txt`) — we're productizing their own system.

**Roadmap:** web app first (proves the concept, reuses Python/web skills); a thin RuneLite plugin follows to auto-capture the data the public APIs can't.

---

## 2. Architecture

Three layers + a plugin seam (mirrors RuneProfile's proven split — studied, not copied; RuneProfile is unlicensed):

1. **Ingest** — `httpx` clients, one per source (Hiscores, WiseOldMan, TempleOSRS), all proxied through FastAPI (CORS). Normalize into pydantic models.
2. **Static game-data** — own re-derived JSON/modules: collection-log tabs, CA tiers, diary regions/tiers, quest list, and the ironman **prerequisite graph**. Turns raw account data into authentic UI and powers goal progress.
3. **State (SQLite)** — accounts, snapshots (progress charts), goals, goal_dependencies (the DAG), projects/milestones, templates, manual overrides.

A `/sync` endpoint + RuneLite **account-hash identity** are designed in from day one so the plugin slots in without reworking the schema.

### Tech stack
- **Frontend:** vanilla HTML/CSS/JS, no build step, token-driven, mobile-first, self-hosted assets. Lives in `web/`.
- **Backend:** FastAPI + pydantic + httpx (evolves the existing `src/osrs_planner/`).
- **Storage:** SQLite (stdlib `sqlite3`, schema pattern from `hcim-tracker`).
- **Plugin (later):** thin Java RuneLite plugin (separate project) → POSTs flat `PlayerData` JSON to `/sync`.

---

## 3. Data sources (honest matrix)

| Data | Source | Auto? |
|---|---|---|
| Skills, XP, total, ~80 boss KC, all clue tiers | Official Hiscores (proxy) | auto |
| Collections-Logged count, CA points/rank | Official Hiscores (proxy) | auto |
| EHP / EHB / gains / history / time-to-max | WiseOldMan | auto |
| Per-item collection log + KC | TempleOSRS (Tiger0295 synced 260/1701) | semi-auto |
| Diaries, quests, pets, per-task CAs | none allowed (WikiSync forbidden) → manual now, plugin later | manual |

`file://` cannot be served to mobile; preview via cloudflared tunnel over `python -m http.server` (see [[reference]] / `DESIGN.md`).

---

## 4. Goal model

Unified, discriminated `Goal` table + a dependency DAG + grouping + templates.
- **Types:** SKILL_LEVEL, SKILL_XP, TOTAL_LEVEL, TOTAL_XP/EHP/EHB, BOSS_KC, CLUE_COUNT, CLOG_SLOTS (%), CLOG_ITEM, CA_POINTS/CA_TIER/CA_TASK, DIARY, QUEST, ITEM_QTY, MANUAL/CUSTOM.
- **Fields:** id, account_id, type, title, target_value, current_value, progress_source (AUTO|MANUAL|HYBRID), data_source, status, manual_override, pinned, sort_order, deadline, project_id, milestone_id, template_id, timestamps.
- **Dependencies:** `GoalDependency{goal_id, requires_goal_id, kind: HARD|SOFT}` — pinning "Corrupted Bowfa" auto-expands to Song of the Elves → Corrupted Gauntlet; "Barrows Gloves" → RFD's 10 subquests + 175 QP. Generalizes the existing `planner.py` (already a backwards-resolver).
- **Grouping:** Project → Milestone → Goals, with roll-up %.
- **Templates:** versioned, shareable; seed from `Tiger.txt` (Things-to-do, the Medium-CA ladder, the gear chains).

---

## 5. Visual design language

"**Gilded Ledger**" — authentic OSRS interface materials (stone, parchment, riveted gold, real RuneScape fonts, the yellow-on-black shadowed text) fused with a calm modern analytics cockpit. Gold = the language of achievement.

The **rendered foundation is the visual spec** — see `web/foundation.html` (tokens, palette, type, in-game text) and `web/components.html` (the component library + the locked, in-game-faithful skills panel). Detailed rationale + reference history in `../osrs-dashboard-mockups/DESIGN.md`.

Key rules: real OSRS fonts (RuneStar, CC0, self-hosted); `--rs-shadow` on all in-game text; sprites `image-rendering: pixelated`; OSRS panels are **fixed-size** (never stretched); authentic mirror uses textured grey stone, modern tracker uses dark+gold; mobile-first/touch (tooltips hover→tap).

---

## 6. Brick breakdown (one feature branch + PR each)

Each brick is small enough to review in one sitting and ends in a PR to `main`.

### `feat/web-foundation` — Design system + skills panel  ✅ DONE (this PR)
- **Scope:** design tokens, RuneStar fonts, base/canvas, component library (`panel`, `card`, buttons, badges, progress, `window`, `slot`, `statcell`), the locked authentic skills panel, the cloudflared/Pages preview workflow.
- **Acceptance:** `foundation.html` + `components.html` render; skills panel matches the in-game tab (textured stone, current/base + diagonal, real-XP colored bars, hover/tap XP tooltip with virtual levels to 200M); mobile-responsive; assets self-hosted.

### `feat/app-shell` — Page scaffold
- **Scope:** `index.html` — header (logo, Tiger0295 avatar + colored ring, resource counters), responsive **left-mirror / right-tracker** layout, footer with Jagex IP disclaimer. Skills panel slots into the mirror.
- **Acceptance:** two-column layout that stacks on mobile; skills panel renders in the mirror; disclaimer present; header reads as a product.
- **Deps:** web-foundation.

### `feat/clog-panel` — Collection log
- **Scope:** clog UI (tabs Bosses/Raids/Clues/Minigames/Other), item slots (sprites, obtained vs dim-unobtained, count, padlock for locked), 260/1701 progress, tooltips.
- **Acceptance:** renders from a clog manifest; obtained/unobtained/locked states; item tooltips. **Deps:** app-shell.

### `feat/quests-diaries-cas` — Rest of the mirror
- **Scope:** quest list, achievement-diary tiers (Easy/Med/Hard/Elite per region), combat-achievement tiers (points/progress), with manual/plugin provenance badges.
- **Acceptance:** each renders from manifests with correct provenance badges. **Deps:** app-shell.

### `feat/goal-tracker` — THE differentiator
- **Scope:** goal cards with progress, the dependency-DAG "what's blocking this" visualization, projects/milestones, templates seeded from `Tiger.txt`.
- **Acceptance:** renders sample goals incl. a real dependency chain (Barrows Gloves → RFD; Bowfa → SOTE → Gauntlet); auto vs manual progress shown. **Deps:** app-shell.

### `feat/backend-ingest` — FastAPI proxy + clients
- **Scope:** extend `hiscores.py` (stop discarding activities), add `wiseoldman.py`, `temple.py`; normalize to pydantic; CORS proxy; caching.
- **Acceptance:** GET endpoints return normalized Tiger0295 data; respects rate limits/User-Agent. **Deps:** — (parallel).

### `feat/sqlite-store` — Persistence
- **Scope:** schema (accounts, snapshots, goals, goal_dependencies, projects, milestones, templates) using the `hcim-tracker` pattern; CRUD.
- **Acceptance:** schema + CRUD + snapshots. **Deps:** —.

### `feat/goal-engine` — Generalize the planner
- **Scope:** compute goal `current_value`/`status` from ingest, resolve the dependency DAG (blocking path), roll up projects.
- **Acceptance:** given account state + goals, computes progress, status, and "what's blocking this". **Deps:** backend-ingest, sqlite-store.

### `feat/api` — Wire live data
- **Scope:** FastAPI routes serving the frontend; `/sync` endpoint (accepts plugin `PlayerData`); wire panels to live data + manual refresh.
- **Acceptance:** frontend shows live Tiger0295 data; `/sync` accepts a `PlayerData` payload. **Deps:** goal-engine + frontend bricks.

### `feat/runelite-plugin` — Thin Java sync (later)
- **Scope:** read in-game events (clog, CAs, diaries, quests, pets), POST `PlayerData` to `/sync` keyed by hashed account hash.
- **Acceptance:** a locally-run plugin fills the manual-gap data into the app. **Deps:** api.

---

## 7. Build order

- **Phase 1 — Mirror:** web-foundation ✅ → app-shell → clog-panel + quests-diaries-cas
- **Phase 2 — Differentiator:** goal-tracker
- **Phase 3 — Backend / live data:** backend-ingest + sqlite-store → goal-engine → api
- **Phase 4 — Plugin:** runelite-plugin

---

## 8. Conventions

- **Git:** one feature branch per brick (`feat/<brick>`), PR to `main`. `main` is review-only. Claude pushes branches + opens PRs; Adrian reviews/merges.
- **Frontend:** `web/` — vanilla HTML/CSS/JS, no build, token-driven, mobile-first, self-hosted assets, in-game-faithful.
- **Backend:** `src/osrs_planner/` — FastAPI + pydantic + httpx; evolve existing code.
- **Preview:** cloudflared tunnel over `python -m http.server` (works on mobile/cellular); GitHub Pages optional for a persistent URL.
- **Data:** live API data is canonical; any baked-in snapshot is dev-only and labeled.
- **Vibe-coded:** Claude authors implementation; Adrian directs, reviews, and merges.

## 9. Open decisions (resolve in this doc before building the relevant brick)

- Prerequisite graph: curated/opinionated ironman path vs neutral graph the user orders.
- Project/milestone roll-up: equal-weight vs EHP/EHB-weighted.
- Google Sheet role: one-time import vs ongoing sync.
- Account type confirm: docs say HCIM, live data says regular ironman.
- Hosting: local-only vs hosted (affects proxy IP-ban / WOM key).
