# ADR-0003 — Three-layer architecture + plugin identity model

- **Status:** Accepted
- **Date:** 2026-06-13
- **Produced by:** initial design (pre-SDD), informed by a study of RuneProfile's open source; recorded in [SPEC.md](../SPEC.md).

## Context

The app combines live API data (skills, KC, EHP) with data that only a plugin can provide (per-slot collection log, diaries, quests), and renders an authentic UI plus a goal engine over both. We studied RuneProfile's architecture (TypeScript monorepo, Cloudflare Workers + Postgres, a Java plugin posting a flat `PlayerData` payload keyed by a hashed RuneLite account hash). RuneProfile has **no LICENSE** (all-rights-reserved), so we may study it but not copy its code or game-data files.

## Decision

Adopt a **three-layer** architecture: (1) **ingest** httpx clients per source, proxied through FastAPI and normalized to pydantic; (2) a **static game-data** layer (own re-derived collection-log tabs, CA tiers, diary/quest data, prerequisite graph) that turns raw account state into authentic UI and powers goals; (3) a **SQLite state** layer (accounts, snapshots, goals, dependencies, projects, templates).

For the eventual plugin, adopt RuneProfile's proven **identity model**: a **hashed RuneLite account hash** as the primary key + implicit credential, posted via a flat `PlayerData` JSON to a `/sync` endpoint, decoded server-side against the static game-data layer.

## Alternatives considered

- **Single-layer (fetch + render inline)** — rejected. Couples ingest, game knowledge, and persistence; no clean seam for the plugin or for progress history.
- **Copy RuneProfile's stack/data** — rejected. No license (legal risk); Cloudflare+Postgres is overkill for a single-user app and doesn't reuse the user's Python.

## Consequences

- **Easier:** clean separation; the plugin slots in by POSTing `PlayerData` to `/sync` with no schema rework; snapshots enable progress charts; the static game-data layer is reusable across web and plugin.
- **Harder / constrained:** all static OSRS game data must be **independently re-derived** (ongoing maintenance as the game updates). The account-hash identity must be designed before `feat/api` so web and plugin data link.
