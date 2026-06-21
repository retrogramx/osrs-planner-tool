# Gilded Tome — Profile Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search any OSRS account on a FastAPI-served page → see a profile that mirrors the account (identity + skills) and tracks one skill-gated goal with its engine-computed status.

**Architecture:** One FastAPI app serves both the `web/` page and a `GET /accounts/{rsn}/profile` JSON endpoint. The endpoint calls `build_profile(rsn)`, which assembles existing bricks per request — `detect_account_type` (probe Hiscores boards) → `fetch_stats` (skills) → `fetch_collection_log` (clog) → engine `AccountState` (with `observable_families` so unobserved requirements read "unknown") → `Engine.is_unlocked(goal)` → a Pydantic `Profile`. The vanilla page fetches and renders it.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, `httpx` (already used by `hiscores`), vanilla HTML/CSS/JS (no build), pytest. Spec: `docs/superpowers/specs/2026-06-21-profile-slice-design.md`.

## Global Constraints

- **Frontend is vanilla HTML/CSS/JS, no build step** (ADR-0002); driven by the existing `web/styles/tokens.css` + fonts + sprites. Hand-write DOM; no framework.
- **One FastAPI app serves page + API** — register API routes BEFORE mounting `web/` static at `/`.
- **Honesty (ADR-0004):** the assembly sets `observable_families={"skill_level","skill_xp"}` so requirements we don't observe (quests/items) read **unknown** (`cant_verify`), never guessed.
- **No live network in the unit suite** — monkeypatch `fetch_stats` / `fetch_collection_log` / `detect_account_type`; the real engine over the real `kg/` is fine (local, fast, deterministic).
- **The featured goal is configurable** (`build_profile(rsn, goal_id=DEFAULT_GOAL_NODE)`); default is a skill-gated KG node, confirmed against a real account in Task 5.
- Run tests with `venv/bin/python -m pytest`. The repo currently has **588 passing**; keep it green.

## File Structure

- **Create** `src/osrs_planner/account/detect.py` — `detect_account_type(rsn, fetcher=...)`.
- **Create** `src/osrs_planner/profile.py` — `SkillEntry`/`GoalStep`/`GoalStatus`/`Profile` models, `DEFAULT_GOAL_NODE`, `build_profile()`.
- **Modify** `src/osrs_planner/api.py` — add `GET /accounts/{rsn}/profile` + mount `web/`.
- **Create** `web/index.html`, `web/app.js`, `web/styles/profile.css` — the screen.
- **Test** `tests/account/test_detect.py`, `tests/test_profile.py`, `tests/test_api_profile.py`.

---

## Task 1: Account-type detection

**Files:**
- Create: `src/osrs_planner/account/detect.py`
- Test: `tests/account/test_detect.py`

**Interfaces:**
- Consumes: `hiscores.fetch_stats(rsn, mode) -> Account` (raises `PlayerNotFoundError` on a 404 / not-on-board); `models.AccountMode`.
- Produces: `detect_account_type(rsn: str, fetcher=fetch_stats) -> AccountMode` — probes most-restrictive-first (`hardcore_ironman` → `ultimate_ironman` → `ironman` → `normal`); returns the first board the account is on. `fetcher` is injectable for tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/account/test_detect.py
import pytest
from osrs_planner.account.detect import detect_account_type
from osrs_planner.models import AccountMode
from osrs_planner.hiscores import PlayerNotFoundError

def _fake_fetcher(on_boards):
    """Return a fetcher that 'finds' the account only on the given AccountModes."""
    def fetcher(rsn, mode):
        if mode in on_boards:
            return object()  # detect_account_type ignores the payload, only success/raise matters
        raise PlayerNotFoundError("not on this board")
    return fetcher

def test_detects_regular_ironman():
    f = _fake_fetcher({AccountMode.ironman, AccountMode.normal})
    assert detect_account_type("X", fetcher=f) == AccountMode.ironman

def test_detects_hardcore_over_ironman():
    # HCIM appears on hcim + ironman + normal -> most restrictive wins
    f = _fake_fetcher({AccountMode.hardcore_ironman, AccountMode.ironman, AccountMode.normal})
    assert detect_account_type("X", fetcher=f) == AccountMode.hardcore_ironman

def test_detects_main():
    f = _fake_fetcher({AccountMode.normal})
    assert detect_account_type("X", fetcher=f) == AccountMode.normal

def test_unknown_account_raises():
    f = _fake_fetcher(set())  # on no board at all
    with pytest.raises(PlayerNotFoundError):
        detect_account_type("X", fetcher=f)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/account/test_detect.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'osrs_planner.account.detect'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/osrs_planner/account/detect.py
"""Detect an account's type by probing the OSRS Hiscores boards. An account
appears on every board up to its restriction (a HCIM is on hcim + ironman +
normal), so the most-restrictive board it's on IS its type."""
from __future__ import annotations

from osrs_planner.hiscores import fetch_stats, PlayerNotFoundError
from osrs_planner.models import AccountMode

# most-restrictive first; group-iron variants deferred (spec §8) -> fall through to ironman/normal
_PROBE_ORDER = [
    AccountMode.hardcore_ironman,
    AccountMode.ultimate_ironman,
    AccountMode.ironman,
    AccountMode.normal,
]

def detect_account_type(rsn: str, fetcher=fetch_stats) -> AccountMode:
    for mode in _PROBE_ORDER:
        try:
            fetcher(rsn, mode)
            return mode
        except PlayerNotFoundError:
            continue
    raise PlayerNotFoundError(f"Account '{rsn}' not found on any Hiscores board")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/account/test_detect.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/account/detect.py tests/account/test_detect.py
git commit -m "feat(profile): detect account type by probing Hiscores boards"
```

---

## Task 2: Profile contract + `build_profile` assembly

**Files:**
- Create: `src/osrs_planner/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: `detect_account_type` (Task 1); `hiscores.fetch_stats(rsn, mode) -> Account` (`Account.skills: dict[str, Skill]`, `Skill.level/xp`); `account.temple.fetch_collection_log(player) -> {"obtained": set[str]}`; `engine.state.AccountState(mode, levels, xp, clog_obtained, observable_families)`; `engine.engine.Engine(kg).is_unlocked(state, node_id) -> Ok|Empty|Problem`; `Ok.card: UnlockCard` (`.status` in {unlocked,locked,indeterminate}, `.blockers: list[Step]`, `Step.name/.status`); `engine.kg.json_store.JsonKGStore.from_dir(dir)`.
- Produces: `Profile`, `SkillEntry`, `GoalStep`, `GoalStatus` (Pydantic), `DEFAULT_GOAL_NODE: str`, `build_profile(rsn, goal_id=DEFAULT_GOAL_NODE) -> Profile`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profile.py
import osrs_planner.profile as profmod
from osrs_planner.profile import build_profile, Profile
from osrs_planner.models import Account, AccountMode, Skill

def _fake_account(rsn):
    skills = {n: Skill(name=n, level=l, xp=l * 100) for n, l in
              {"Overall": 1000, "Attack": 75, "Strength": 80, "Defence": 70, "Agility": 5}.items()}
    return Account(rsn=rsn, mode=AccountMode.ironman, skills=skills)

def test_build_profile_shape_and_unknown_handling(monkeypatch):
    monkeypatch.setattr(profmod, "detect_account_type", lambda rsn, **k: AccountMode.ironman)
    monkeypatch.setattr(profmod, "fetch_stats", lambda rsn, mode: _fake_account(rsn))
    monkeypatch.setattr(profmod, "fetch_collection_log", lambda rsn: {"obtained": set()})
    p = build_profile("TestAcc")          # default goal = a skill-gated KG node
    assert isinstance(p, Profile)
    assert p.rsn == "TestAcc" and p.account_type == "ironman"
    assert p.total_level == 1000
    assert {s.name for s in p.skills} == {"Attack", "Strength", "Defence", "Agility"}  # Overall excluded
    assert len(p.goals) == 1
    g = p.goals[0]
    assert g.status in {"met", "blocked", "unknown"}
    # the goal has at least one skill blocker (low Agility=5) OR every step is met -> any way, steps are well-formed
    for step in g.steps:
        assert step.status in {"met", "unmet", "unknown"}
    assert p.clog_synced is True

def test_clog_failure_is_not_fatal(monkeypatch):
    monkeypatch.setattr(profmod, "detect_account_type", lambda rsn, **k: AccountMode.ironman)
    monkeypatch.setattr(profmod, "fetch_stats", lambda rsn, mode: _fake_account(rsn))
    def boom(rsn): raise RuntimeError("temple down")
    monkeypatch.setattr(profmod, "fetch_collection_log", boom)
    p = build_profile("TestAcc")
    assert p.clog_synced is False and isinstance(p, Profile)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_profile.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'osrs_planner.profile'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/osrs_planner/profile.py
"""The Profile contract + assembly: search a player -> mirror (skills) + one
goal's engine-computed status. Composes existing bricks per request. The single
seam every consumer (API, future plugin) hangs off."""
from __future__ import annotations

import os
from pydantic import BaseModel, Field

from osrs_planner.account.detect import detect_account_type
from osrs_planner.account.temple import fetch_collection_log
from osrs_planner.hiscores import fetch_stats
from osrs_planner.engine.engine import Engine
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.result import Ok, Empty

# A skill-gated KG goal (blockers are observable skill levels). Confirmed/tuned in Task 5.
DEFAULT_GOAL_NODE = "quest:cold-war"

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_KG = JsonKGStore.from_dir(os.path.join(_REPO, "kg"))   # loaded once at import

class SkillEntry(BaseModel):
    name: str
    level: int
    xp: int

class GoalStep(BaseModel):
    label: str                 # "Agility", "Recipe for Disaster", ...
    status: str                # "met" | "unmet" | "unknown"

class GoalStatus(BaseModel):
    node_id: str
    label: str                 # the goal's display name
    status: str                # "met" | "blocked" | "unknown"
    steps: list[GoalStep] = Field(default_factory=list)

class Profile(BaseModel):
    rsn: str
    account_type: str          # AccountMode.name: "normal" | "ironman" | "hardcore_ironman" | "ultimate_ironman"
    total_level: int
    skills: list[SkillEntry]
    goals: list[GoalStatus]
    clog_synced: bool = True

_STEP_STATUS = {"satisfied": "met", "satisfiable": "unmet",
                "cant_verify": "unknown", "impossible_for_mode": "unmet"}
_CARD_STATUS = {"unlocked": "met", "locked": "blocked", "indeterminate": "unknown"}

def _goal_label(goal_id: str) -> str:
    try:
        return _KG.get_node(goal_id).name
    except Exception:
        return goal_id

def _goal_status(goal_id: str, result) -> GoalStatus:
    label = _goal_label(goal_id)
    if isinstance(result, Ok):
        card = result.card
        steps = [GoalStep(label=b.name, status=_STEP_STATUS.get(b.status, "unknown"))
                 for b in card.blockers]
        return GoalStatus(node_id=goal_id, label=label, status=_CARD_STATUS[card.status], steps=steps)
    if isinstance(result, Empty):
        return GoalStatus(node_id=goal_id, label=label, status="met", steps=[])
    # Problem: surface the message, mark unknown
    return GoalStatus(node_id=goal_id, label=label, status="unknown",
                      steps=[GoalStep(label=getattr(result, "message", "could not evaluate"), status="unknown")])

def build_profile(rsn: str, goal_id: str = DEFAULT_GOAL_NODE) -> Profile:
    mode = detect_account_type(rsn)                       # AccountMode; raises PlayerNotFoundError if nowhere
    account = fetch_stats(rsn, mode)                      # Account
    try:
        clog = fetch_collection_log(rsn)["obtained"]
        clog_synced = True
    except Exception:
        clog, clog_synced = set(), False
    levels = {f"skill:{n.lower()}": s.level for n, s in account.skills.items() if n != "Overall"}
    xp = {f"skill:{n.lower()}": s.xp for n, s in account.skills.items() if n != "Overall"}
    state = AccountState(mode=mode.name, levels=levels, xp=xp,
                         clog_obtained=clog, observable_families={"skill_level", "skill_xp"})
    result = Engine(_KG).is_unlocked(state, goal_id)
    total = account.skills["Overall"].level if "Overall" in account.skills \
        else sum(s.level for n, s in account.skills.items())
    skills = [SkillEntry(name=n, level=s.level, xp=s.xp)
              for n, s in account.skills.items() if n != "Overall"]
    return Profile(rsn=rsn, account_type=mode.name, total_level=total,
                   skills=skills, goals=[_goal_status(goal_id, result)], clog_synced=clog_synced)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_profile.py -q`
Expected: PASS (2 passed). If `quest:cold-war` is missing from the KG, the test still passes (label falls back to the id, goal evaluates), but confirm the node exists: `venv/bin/python -c "from osrs_planner.profile import _KG; print(_KG.get_node('quest:cold-war').name)"` → prints `Cold War`.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/profile.py tests/test_profile.py
git commit -m "feat(profile): Profile contract + build_profile assembly (skills+clog+engine)"
```

---

## Task 3: API endpoint + static page mount

**Files:**
- Modify: `src/osrs_planner/api.py`
- Test: `tests/test_api_profile.py`

**Interfaces:**
- Consumes: `profile.build_profile(rsn) -> Profile` (Task 2); `hiscores.PlayerNotFoundError`, `HiscoresError`.
- Produces: `GET /accounts/{rsn}/profile` → `Profile` JSON (200), `404` for not-found, `502` for Hiscores unreachable; `web/` mounted at `/`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_profile.py
from fastapi.testclient import TestClient
import osrs_planner.api as apimod
from osrs_planner.api import app
from osrs_planner.profile import Profile, SkillEntry, GoalStatus
from osrs_planner.hiscores import PlayerNotFoundError

client = TestClient(app)

def _fake_profile(rsn, goal_id=None):
    return Profile(rsn=rsn, account_type="ironman", total_level=1000,
                   skills=[SkillEntry(name="Attack", level=75, xp=7500)],
                   goals=[GoalStatus(node_id="quest:cold-war", label="Cold War", status="blocked", steps=[])])

def test_profile_endpoint_ok(monkeypatch):
    monkeypatch.setattr(apimod, "build_profile", _fake_profile)
    r = client.get("/accounts/Tiger0295/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["rsn"] == "Tiger0295" and body["account_type"] == "ironman"
    assert body["goals"][0]["label"] == "Cold War"

def test_profile_endpoint_not_found(monkeypatch):
    def boom(rsn, **k): raise PlayerNotFoundError("nope")
    monkeypatch.setattr(apimod, "build_profile", boom)
    r = client.get("/accounts/FakeName123/profile")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_api_profile.py -q`
Expected: FAIL — `404` on `/accounts/.../profile` (route doesn't exist) so `test_profile_endpoint_ok` fails its 200 assertion.

- [ ] **Step 3: Write minimal implementation** — add to `src/osrs_planner/api.py`

Add these imports near the top (after the existing `from fastapi import FastAPI`):

```python
import os
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from osrs_planner.profile import build_profile
from osrs_planner.hiscores import PlayerNotFoundError, HiscoresError
```

Add the endpoint **after** the existing routes but **before** any static mount:

```python
@app.get("/accounts/{rsn}/profile")
def get_profile(rsn: str):
    try:
        return build_profile(rsn)
    except PlayerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Account '{rsn}' not found on Hiscores")
    except HiscoresError:
        raise HTTPException(status_code=502, detail="Hiscores is unreachable right now — try again")
```

Add the static mount as the **last** statement in the file (mounting `/` must come after all API routes):

```python
_WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web")
app.mount("/", StaticFiles(directory=_WEB, html=True), name="web")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_api_profile.py -q`
Expected: PASS (2 passed). Note: the static mount needs `web/` to exist — if Task 4 isn't done yet, create an empty `web/index.html` first (`mkdir -p web && echo "<!doctype html>" > web/index.html`) so the mount doesn't error at import.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/api.py tests/test_api_profile.py
git commit -m "feat(profile): /accounts/{rsn}/profile endpoint + serve web/ from FastAPI"
```

---

## Task 4: The page (search → mirror + tracker)

**Files:**
- Create: `web/index.html`, `web/app.js`, `web/styles/profile.css`
- Test: extend `tests/test_api_profile.py` with a served-page smoke test.

**Interfaces:**
- Consumes: `GET /accounts/{rsn}/profile` (Task 3) — the `Profile` JSON.
- Produces: a page with a search input `#rsn-search`, a `#mirror` panel (skills grid), a `#tracker` panel (the goal). Uses existing `web/styles/tokens.css`, fonts, and `web/assets/sprites/skills/<skill>.png`.

- [ ] **Step 1: Write the failing test** (the page is served + has the search box)

```python
# add to tests/test_api_profile.py
def test_page_is_served():
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="rsn-search"' in r.text          # the search box exists
    assert "app.js" in r.text                     # the script is wired
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_api_profile.py::test_page_is_served -q`
Expected: FAIL — the placeholder `web/index.html` lacks `id="rsn-search"`.

- [ ] **Step 3: Write the page**

`web/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Gilded Tome</title>
  <link rel="stylesheet" href="/styles/tokens.css" />
  <link rel="stylesheet" href="/styles/fonts.css" />
  <link rel="stylesheet" href="/styles/base.css" />
  <link rel="stylesheet" href="/styles/profile.css" />
</head>
<body>
  <header class="gt-header">
    <h1>Gilded Tome</h1>
    <form id="search-form">
      <input id="rsn-search" name="rsn" placeholder="Search any account…" autocomplete="off" />
      <button type="submit">Search</button>
    </form>
  </header>
  <main id="profile" hidden>
    <section id="mirror" class="gt-panel">
      <div id="identity"></div>
      <div id="skills" class="skills-grid"></div>
    </section>
    <section id="tracker" class="gt-panel">
      <h2>Goal</h2>
      <div id="goal"></div>
    </section>
  </main>
  <p id="status" class="gt-status"></p>
  <script src="/app.js"></script>
</body>
</html>
```

`web/app.js`:
```javascript
const form = document.getElementById('search-form');
const statusEl = document.getElementById('status');
const profileEl = document.getElementById('profile');

const SKILL_ORDER = ['attack','hitpoints','mining','strength','agility','smithing','defence','herblore',
  'fishing','ranged','thieving','cooking','prayer','crafting','firemaking','magic','fletching','woodcutting',
  'runecraft','slayer','farming','construction','hunter'];

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const rsn = document.getElementById('rsn-search').value.trim();
  if (!rsn) return;
  statusEl.textContent = `Loading ${rsn}…`;
  profileEl.hidden = true;
  try {
    const res = await fetch(`/accounts/${encodeURIComponent(rsn)}/profile`);
    if (!res.ok) { statusEl.textContent = (await res.json()).detail || 'Something went wrong'; return; }
    render(await res.json());
    statusEl.textContent = '';
  } catch (err) { statusEl.textContent = 'Could not reach the server.'; }
});

function render(p) {
  const typeLabel = {normal:'Main', ironman:'Ironman', hardcore_ironman:'HCIM', ultimate_ironman:'UIM'}[p.account_type] || p.account_type;
  document.getElementById('identity').innerHTML =
    `<h2>${p.rsn}</h2><div class="meta">${typeLabel} · Total level ${p.total_level}</div>` +
    (p.clog_synced ? '' : '<div class="note">Collection log not synced</div>');

  const byName = Object.fromEntries(p.skills.map(s => [s.name.toLowerCase(), s]));
  document.getElementById('skills').innerHTML = SKILL_ORDER.map(slug => {
    const s = byName[slug];
    return `<div class="skill"><img src="/assets/sprites/skills/${slug}.png" alt="${slug}"/>` +
           `<span>${s ? s.level : '–'}</span></div>`;
  }).join('');

  const g = p.goals[0];
  const badge = {met:'✅ Done', blocked:'🔒 Blocked', unknown:'❓ Unknown'}[g.status] || g.status;
  const steps = g.steps.map(st => {
    const icon = {met:'✅', unmet:'🔒', unknown:'❓'}[st.status] || '•';
    return `<li class="step ${st.status}">${icon} ${st.label}</li>`;
  }).join('');
  document.getElementById('goal').innerHTML =
    `<h3>${g.label}</h3><div class="badge ${g.status}">${badge}</div>` +
    (steps ? `<ul class="steps">${steps}</ul>` : '<p>No remaining requirements.</p>');

  profileEl.hidden = false;
}
```

`web/styles/profile.css` (lean, built on the existing tokens — adjust token names to match `tokens.css`):
```css
.gt-header { display:flex; gap:var(--s4,1rem); align-items:center; padding:var(--s4,1rem); }
#search-form { display:flex; gap:.5rem; }
#profile { display:grid; grid-template-columns:1fr 1fr; gap:var(--s4,1rem); padding:var(--s4,1rem); }
@media (max-width:720px){ #profile{ grid-template-columns:1fr; } }
.gt-panel { padding:var(--s4,1rem); }
.skills-grid { display:grid; grid-template-columns:repeat(8,1fr); gap:.4rem; }
.skill { display:flex; align-items:center; gap:.3rem; }
.skill img { width:20px; height:20px; image-rendering:pixelated; }
.steps { list-style:none; padding:0; }
.step.unmet { font-weight:bold; }
.gt-status { padding:0 var(--s4,1rem); }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_api_profile.py -q`
Expected: PASS (all). Then **manual visual check** (the JS rendering can't be unit-tested cleanly): `venv/bin/python -m uvicorn osrs_planner.api:app --app-dir src --reload`, open `http://localhost:8000`, search a real account → mirror + goal render. (Mobile: tunnel cloudflared at port 8000.)

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/app.js web/styles/profile.css tests/test_api_profile.py
git commit -m "feat(profile): search page -> account mirror + goal tracker (Block 2 shell)"
```

---

## Task 5: End-to-end integration + confirm the default goal

**Files:**
- Modify (only if needed): `src/osrs_planner/profile.py` (the `DEFAULT_GOAL_NODE` value)
- Test: `tests/test_profile.py` (add a marked live integration test, skipped by default)

**Interfaces:**
- Consumes: everything above. No new public surface.

- [ ] **Step 1: Add a live integration test (opt-in, skipped in CI)**

```python
# add to tests/test_profile.py
import os, pytest

@pytest.mark.skipif(os.environ.get("LIVE") != "1", reason="hits live Hiscores/Temple; run with LIVE=1")
def test_live_tiger0295_profile_has_a_real_goal():
    from osrs_planner.profile import build_profile
    p = build_profile("Tiger0295")
    assert p.account_type in {"ironman", "hardcore_ironman", "ultimate_ironman", "normal"}
    assert len(p.skills) == 23 and p.total_level > 0
    g = p.goals[0]
    assert g.status in {"met", "blocked", "unknown"}
    print(f"\nTiger0295: {p.account_type} total {p.total_level} | goal '{g.label}' = {g.status}, {len(g.steps)} steps")
    for s in g.steps: print("   ", s.status, s.label)
```

- [ ] **Step 2: Run it live and inspect the goal**

Run: `LIVE=1 venv/bin/python -m pytest tests/test_profile.py::test_live_tiger0295_profile_has_a_real_goal -q -s`
Expected: PASS, and the printout shows Tiger0295's type, total, and the goal's status + steps.

- [ ] **Step 3: Confirm or swap `DEFAULT_GOAL_NODE`**

Read the printout. The default is good if the goal is **`blocked`** with at least one **`unmet`** *skill* step (shows the engine's value). If it's already `met` (no blockers) or all-`unknown`, swap `DEFAULT_GOAL_NODE` in `src/osrs_planner/profile.py` to another skill-gated node and re-run Step 2. Candidates (skill-gated, quest-free starts, verified in the spec): `quest:cold-war`, `quest:enakhras-lament`, `quest:tears-of-guthix`, `quest:the-giant-dwarf`. Pick the one that reads best for Tiger0295.

- [ ] **Step 4: Full suite + manual page check**

Run: `venv/bin/python -m pytest -q` → all green (588 + the new tests).
Then `venv/bin/python -m uvicorn osrs_planner.api:app --app-dir src`, open the page, search `Tiger0295`, confirm the mirror + the goal (with its blockers) render correctly.

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/profile.py tests/test_profile.py
git commit -m "feat(profile): confirm default goal vs a live account + live smoke test"
```

---

## Self-Review

- **Spec coverage:** §2 architecture → Tasks 2–4; §3.1 detect → Task 1; §3.2 assembly/contract → Task 2; §3.3 API+static → Task 3; §3.4 page → Task 4; §4 contract → Task 2 (note: `SkillEntry.rank` dropped — `models.Skill` has no rank; the grid shows level, which is what matters; documented deviation); §5 configurable skill-gated goal → Task 2 default + Task 5 confirmation; §6 errors → Task 2 (clog-not-fatal) + Task 3 (404/502); §7 testing → every task's tests + Task 5 live smoke; §8 scope respected (one goal, no deploy/cache/persist).
- **Placeholder scan:** none — every step has runnable code/commands. `DEFAULT_GOAL_NODE` is a concrete value confirmed in Task 5.
- **Type consistency:** `Profile`/`GoalStatus`/`GoalStep`/`SkillEntry` field names identical across Tasks 2–4; `build_profile(rsn, goal_id)` signature consistent; `AccountMode.name` used for `account_type` and `AccountState.mode` throughout.
