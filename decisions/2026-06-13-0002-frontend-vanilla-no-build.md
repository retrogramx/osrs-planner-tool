# ADR-0002 — Frontend: vanilla HTML/CSS/JS, no build step

- **Status:** Accepted
- **Date:** 2026-06-13
- **Produced by:** initial design (pre-SDD); recorded in [SPEC.md](../SPEC.md).

## Context

The frontend must render an authentic, pixel-faithful OSRS interface with heavy visual polish, work on mobile (the user develops from a phone over a tunnel), and eventually be served by the FastAPI backend. RuneProfile's reference stack is React + TanStack + Vite + Tailwind. The user's frontend strength is **vanilla HTML/CSS/JS** (their PokeMMO companion was built this way); the project is vibe-coded.

## Decision

Build the frontend as **vanilla HTML/CSS/JS with no build step**, driven entirely by **CSS custom-property design tokens**, with **self-hosted assets** (RuneStar fonts, OSRS sprites). It lives in `web/` and is previewed by serving the directory statically (`python -m http.server` + cloudflared tunnel); later FastAPI serves the same files.

## Alternatives considered

- **React + Vite (RuneProfile's stack)** — rejected. Adds a build toolchain and a framework the user doesn't work in; complicates the zero-config mobile preview loop; overkill for a token-driven, mostly-static authentic UI. (RuneProfile is also unlicensed, so its code can't be reused anyway.)
- **A lightweight framework (Svelte/Lit/Alpine)** — rejected for now. Still a build/dependency; the component set is small enough that tokens + a tiny bit of vanilla JS suffice.

## Consequences

- **Easier:** instant edit→refresh over the tunnel (no rebuild); trivial to serve from FastAPI; the user can read/modify everything; tokens give cohesion and one-line global restyles.
- **Harder / constrained:** no framework conveniences (components, reactivity, routing) — we hand-write DOM and keep state simple. If the goal-tracker UI grows complex, revisit with a new ADR.
