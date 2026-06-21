# Gilded Tome — Profile Vertical Slice (Design)

**Date:** 2026-06-21
**Goal:** The first real product screen: search any OSRS account → see a profile that **mirrors** the account (identity + skills) on the left and **tracks** one goal (Barrows gloves) with its engine-computed status on the right. Built hosting-ready so adding clog / more goals later is trivial.

## 1. Why this slice

The backend is mature but **unassembled** — `hiscores` (skills), `account.temple` (clog), `account.state`/`engine.state` (`AccountState`), and the **engine** (`Engine.is_unlocked(state, goal) -> UnlockCard`) each compute a *piece*, but nothing assembles them into the single `Profile` a page renders. That assembly is the linchpin; its shape is the contract everything else hangs off. We build the smallest end-to-end slice that proves the whole pipe (real account → skills → engine goal status → screen), on the foundation the public product needs.

This honours the documented Gilded Tome vision: a **public, searchable profile site for any Hiscores account** (per `project_osrs_dashboard`), web-app-first (ADR-0001), vanilla no-build frontend (ADR-0002).

## 2. Architecture

A single **FastAPI** app serves *both* the `web/` static files and the JSON API — one process (`uvicorn`), one deployable unit. The page is vanilla HTML/CSS/JS: a search box + the profile screen that fetches `GET /accounts/{rsn}/profile` and renders client-side. The backend core is **`build_profile(rsn)`**, run **per request**, composing the existing bricks. Mobile preview points the cloudflared tunnel at `uvicorn` (page + API from one process) instead of `http.server`.

```
search "Tiger0295"
  -> GET /accounts/Tiger0295/profile
       -> build_profile(rsn):
            detect_account_type(rsn)            # probe Hiscores boards
            fetch_stats(rsn, mode)              # skills/xp (Hiscores)
            fetch_collection_log(rsn)           # clog (Temple; optional)
            -> AccountState(levels, xp, clog_obtained, observable_families)
            -> Engine(kg).is_unlocked(state, BARROWS_GLOVES)
            -> Profile (JSON)
  -> page renders: account-mirror (left) + goal-tracker (right)
```

## 3. Components (each one job, independently testable)

### 3.1 `src/osrs_planner/account/detect.py` — account-type detection (new)
- `detect_account_type(rsn: str) -> AccountMode`
- Probes the restricted Hiscores boards via the existing `hiscores.fetch_stats(rsn, mode)` (which maps `AccountMode` → board suffix and raises `PlayerNotFoundError` on a 404). An account appears on **every** board up to its restriction, so probe most-restrictive-first: `hardcore_ironman` → `ultimate` → `ironman` → `normal`; the first board the account is on (no `PlayerNotFoundError`) is its type.
- Group-iron / HCGIM detection is **deferred** (noted in scope); those fall back to `ironman`/`normal`.
- Depends on: `hiscores.fetch_stats`, `models.AccountMode`.

### 3.2 `src/osrs_planner/profile.py` — the contract + assembly (new, the linchpin)
- Pydantic models (the **contract**): `SkillEntry`, `GoalStep`, `GoalStatus`, `Profile` (see §4).
- `build_profile(rsn: str, goal_id: str = BARROWS_GLOVES_NODE) -> Profile`:
  1. `mode = detect_account_type(rsn)`
  2. `account = fetch_stats(rsn, mode)` → skills/xp/total.
  3. `clog = fetch_collection_log(rsn)` → `clog_obtained`; **on failure/absent, continue with empty clog** + record it (clog is optional for a public account).
  4. Build the engine `AccountState`: `mode`, `levels`, `xp`, `clog_obtained`, and **`observable_families = {the families we actually observed}`** (skill levels/xp from Hiscores; clog/kc/clue activity from Temple/Hiscores). Quests/diaries/items/bank are left empty and **NOT** in `observable_families`, so the engine treats them as **UNKNOWN**, not zero (ADR-0004). This is the honest partial-knowledge behaviour and the core demonstration.
  5. `card = Engine(_KG).is_unlocked(state, goal_id)` (the KG is loaded **once** at module import: `JsonKGStore.from_dir(<repo>/kg)`).
  6. Map the engine result → `GoalStatus` (status + the steps/blockers; engine `Problem`/`Empty` → `status="unknown"` + the message).
  7. Return `Profile(rsn, account_type=mode, total_level, skills, goals=[goal_status])`.
- Depends on: `account.detect`, `hiscores`, `account.temple`, `engine.state.AccountState`, `engine.engine.Engine`, `engine.kg.json_store.JsonKGStore`, `engine.cards`.

### 3.3 `src/osrs_planner/api.py` — expose + serve (extend existing)
- Add `GET /accounts/{rsn}/profile` → `build_profile(rsn)`; FastAPI serializes the Pydantic `Profile` to JSON automatically.
- Mount `web/` as static files so the same app serves the page (e.g. `app.mount("/", StaticFiles(directory="web", html=True))`, registered **after** the API routes).
- Error handling per §6.

### 3.4 `web/` — the screen (new, on the Block 0-1 design system)
- `index.html` — app shell: header + search box + a two-column layout (left **account-mirror**, right **goal-tracker**), using the existing `styles/tokens.css` + fonts + skill sprites.
- `app.js` — on search: `fetch('/accounts/<rsn>/profile')`, then render the skills grid (sprite + level per skill) and the goal card (label + status badge + the steps list, each step met ✅ / unmet 🔒 / unknown ❓).
- `styles/profile.css` — slice-specific layout built from the existing tokens/components (no new design language).

## 4. The `Profile` contract

```python
class SkillEntry(BaseModel):
    name: str
    level: int
    xp: int
    rank: int

class GoalStep(BaseModel):
    label: str          # "Recipe for Disaster", "Attack 70", ...
    status: str         # "met" | "unmet" | "unknown"

class GoalStatus(BaseModel):
    node_id: str        # the KG goal node
    label: str          # "Barrows gloves"
    status: str         # "met" | "blocked" | "unknown"
    steps: list[GoalStep]

class Profile(BaseModel):
    rsn: str
    account_type: str   # the detected AccountMode value: "normal" | "ironman" | "hardcore_ironman" | "ultimate" (page maps to "Main"/"Ironman"/"HCIM"/"UIM" for display)
    total_level: int
    skills: list[SkillEntry]
    goals: list[GoalStatus]   # slice: exactly one (Barrows gloves); a list for extensibility
    clog_synced: bool = True  # false when Temple clog was unavailable
```

The `goals` list (not a single goal) and `clog_synced` flag are the deliberate **extensibility seams** — adding more goals or a clog summary later doesn't change the contract shape.

## 5. The featured goal — Barrows gloves

Barrows gloves (Recipe for Disaster) is already a known engine demo ("the Barrows-gloves mountain" in `demo_showcase.py`): a deep stack of quest + skill requirements, so it shows the engine's DAG/blocker reasoning well. For a **public** account we know the **skill** requirements (Hiscores) but the **quest** chain is unknown — the goal will read *"skills met / quest log unknown — sync the RuneLite plugin to verify,"* which is the honest, plugin-foreshadowing story, not a bug. The exact KG node id is resolved during planning (it exists in `kg/nodes.json`).

**Disclosed v1 limitation:** the engine `AccountState` has *family-level* observability (skills/clog can be "unknown") but some **scalar** fields (`qp`, `ca_points`) default to `0` with no unknown state. For a public account we can't observe quest points, so a requirement gated purely on `qp` may read **unmet** rather than **unknown**. `combat_level` *is* derived from the (known) skills. Skill-gated requirements — the majority — evaluate honestly; the plugin (quest/diary sync) resolves the rest. This is disclosed, not hidden.

## 6. Error handling

- **Account not found** (`PlayerNotFoundError` on the `normal` board) → API returns **404** with `{"detail": "Account '<rsn>' not found on Hiscores"}`; page shows a friendly "couldn't find that account."
- **Temple clog unavailable** (network/no sync) → `build_profile` continues with empty `clog_obtained` and `clog_synced=False`; page shows the profile with a "collection log not synced" note. Never fatal.
- **Engine `Problem`/`Empty`** (e.g. data inconsistency) → that goal's `status="unknown"` carrying the engine message; the profile still returns identity + skills.
- **Hiscores unreachable** (`HiscoresError`) → API **502** with a friendly message; page shows a retry prompt.

## 7. Testing

- `tests/account/test_detect.py` — `detect_account_type` returns the most-restrictive board (monkeypatch `fetch_stats` to simulate which boards 404; a known iron → `ironman`, a main → `normal`).
- `tests/test_profile.py` — `build_profile` over a **fixture** account (monkeypatched hiscores + temple, no live calls): asserts the `Profile` shape, that skills map through, that `observable_families` is set so unobserved requirements read **unknown**, and that the engine card maps to `GoalStatus` correctly.
- `tests/test_api.py` — FastAPI `TestClient`: `GET /accounts/{rsn}/profile` → 200 + valid `Profile` JSON (monkeypatched assembly); a not-found rsn → 404.
- No live Hiscores/Temple calls in the unit suite (monkeypatch/fixtures); one optional live smoke check kept out of the default run.

## 8. Scope

**In:** search any account, auto-detect type (iron/HCIM/UIM/main), header + skills grid + one goal (Barrows gloves) with engine status, FastAPI serving page + API, graceful errors, tests.

**Out (deliberately — the foundation sets these up):** public hosting/deployment, response caching, rate-limiting, persistence / saving progress, multiple goals, clog-summary display, quest/diary manual input, the goal-DAG visualisation, group-iron/HCGIM detection.

## 9. References

- Bricks reused: `hiscores.fetch_stats`, `account.temple.fetch_collection_log`, `engine.state.AccountState`, `engine.engine.Engine.is_unlocked`, `engine.kg.json_store.JsonKGStore`, `engine.cards`.
- ADR-0001 (web-app first, design `/sync`+identity early), ADR-0002 (vanilla HTML/CSS/JS, no build), ADR-0004 (observability families — absent vs zero).
- Design system: `web/styles/tokens.css`, RuneScape fonts, skill sprites (Block 0-1).
