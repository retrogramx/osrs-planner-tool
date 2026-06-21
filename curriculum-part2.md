# OSRS Planner Tool — Curriculum Part 2

## Context

You've completed the first 5 chapters. The planner works — you can look up stats, generate a Graceful plan, and serve it from an API. But everything is hardcoded to agility and marks of grace. The `Goal` model has `target_marks`. The `Task` model has `marks_per_hour`. The `generate_plan()` function tracks `current_marks` and stops at 260.

The real vision for this tool is planning complex goals with nested dependencies — multiple skills, quests, sub-goals, and ironman-specific requirements. The test case that will drive this refactor is **Birdhouse Runs**, a goal that requires:

```
Birdhouse Runs
├── Hunter 5, Crafting 5
├── Construction 25 (ironman only — Crafting Table 2 for clockwork)
└── Bone Voyage quest
    ├── 1+ Quest Points
    └── 100 Kudos (sub-goal)
        ├── Natural History Quiz (28 kudos, free)
        ├── The Dig Site quest → Uncleaned Finds (50 kudos)
        │   ├── 10 Agility
        │   ├── 10 Herblore
        │   └── 25 Thieving
        └── Remaining ~22 from Timeline Displays or Ancient Relics
```

This is the kind of backwards-planning problem the tool was built for. These two chapters redesign the planner to handle it.

**Same rules as before:** You write the code. Claude guides, explains, reviews, and helps debug.

---

## Chapter 6: Making the Planner Handle Real Goals

**Goal: "I can plan a goal that has quests, multiple skills, and sub-goals"**

The current planner understands one thing: train a skill, collect marks, stop. This chapter rebuilds it to handle the Birdhouse Runs dependency tree — a goal with skill requirements across multiple skills, quest prerequisites that have their own prerequisites, item requirements that depend on account type, and sub-goals like earning 100 Kudos.

You won't hand-write perfect data for every quest and skill method — the Wiki API will do that later. The focus here is building the **model and engine** that can express and solve these dependency chains.

---

### Lesson 6.1: Break It on Purpose

**You'll learn:** How to identify tight coupling by trying to use code for something it wasn't designed for. This is how real refactoring starts — you find what actually breaks, then fix it.

**Video resources:**
- Search YouTube: `"Python refactoring tight coupling tutorial"`
- Search YouTube: `"what is tight coupling in software design" beginner explained`
- Search YouTube: `"code coupling and cohesion explained"`

**Task:** Try to express the Birdhouse Runs goal using the current `Goal` and `Task` models. Don't change any Python code — just try to write a JSON file `src/osrs_planner/goals/birdhouse_runs.json` using the existing format.

You'll immediately run into problems:
- `target_marks: int` is required — birdhouses don't have marks
- `marks_per_hour: float` is required on every task — irrelevant here
- Every task has a single `skill` field — but this goal needs Hunter, Crafting, AND Construction
- There's no way to express "requires Bone Voyage quest"
- There's no way to express "requires 100 Kudos" as a sub-goal
- There's no way to say "Construction 25 only if ironman"
- `generate_plan()` hardcodes `account.skills["agility"]` — it doesn't know about other skills

Write down every limitation you hit. Sketch (on paper, Excalidraw, or in a notes file) what the JSON *should* look like if the models could handle it. Don't worry about getting it perfect — this is a design exercise.

**Deliverable:** A list of everything that needs to change, and a rough sketch of what a flexible goal definition would look like.

---

### Lesson 6.2: Designing New Models

**You'll learn:** How to design Pydantic models that handle multiple types of data. Discriminated unions (a field that changes meaning based on a `type` value), optional fields, nested models, and the Literal type.

**Video resources:**
- Search YouTube: `"Pydantic discriminated unions tutorial"`
- Search YouTube: `"Python Pydantic nested models beginner"`
- Search YouTube: `"ArjanCodes Pydantic"` — ArjanCodes makes great Pydantic content
- Search YouTube: `"Python Literal type hint tutorial"`

**Task:** Redesign `models.py` to handle complex goals. Here's the thinking behind each new model:

1. **`Requirement` model** — A goal can require different things. Use a `type` field to distinguish them:
   - `"skill"` — requires a skill at a certain level: `{"type": "skill", "skill": "hunter", "level": 5}`
   - `"quest"` — requires a quest to be completed: `{"type": "quest", "quest": "bone_voyage"}`
   - `"item"` — requires a certain number of items: `{"type": "item", "item": "marks_of_grace", "quantity": 260}`
   - `"kudos"` — requires museum kudos: `{"type": "kudos", "quantity": 100}`

   Think about which fields are shared and which are type-specific. You might use optional fields, or you might use Pydantic's discriminated union pattern (one base model, multiple variants keyed on `type`).

2. **`Quest` model** — Quests are a new concept. A quest has:
   - `id: str` (e.g., `"bone_voyage"`, `"the_dig_site"`)
   - `name: str` (e.g., `"Bone Voyage"`, `"The Dig Site"`)
   - `requirements: list[Requirement]` — what you need before you can start this quest
   - `grants_combat_xp: bool` — does this quest award combat XP? (important for skillers)
   - `quest_points: int` — how many QP it gives on completion

   Quests can require other quests — The Dig Site might be required by Bone Voyage. This creates a chain. You don't need to solve the chain yet (that's Lesson 6.4) — just make the model capable of expressing it.

3. **`Task` model changes:**
   - Remove `marks_per_hour` — replace with `outputs: dict[str, float]` (e.g., `{"marks_of_grace": 12}` or `{}` for no special outputs)
   - Keep `skill`, `from_level`, `to_level`, `xp_per_hour`, `task_type`, `combat_requirement`
   - Add `account_types: list[str]` (optional) — if present, this task only applies to certain account types. E.g., "make clockwork at POH crafting table" only matters for ironmen.

4. **`Goal` model changes:**
   - Replace `target_marks: int` with `requirements: list[Requirement]`
   - Add `quests: list[Quest]` (optional) — quest definitions used by this goal
   - Add `sub_goals: list[str]` (optional) — IDs of other goals that must be completed first (e.g., Birdhouse Runs depends on a "100 Kudos" sub-goal)
   - Keep `id`, `name`, `description`, `tasks`

5. **Update `full_graceful.json`** to use the new format:
   - Requirements: `[{"type": "skill", "skill": "agility", "level": 60}, {"type": "item", "item": "marks_of_grace", "quantity": 260}]`
   - Tasks: replace `marks_per_hour` with `outputs: {"marks_of_grace": 12}`

6. **Verify the old goal still loads:**
   ```python
   from osrs_planner.planner import load_goal
   goal = load_goal("full_graceful")
   print(goal)
   ```

**Deliverable:** New models in `models.py` that can express Graceful, Birdhouse Runs, and goals with quests. `full_graceful.json` updated and loading cleanly.

---

### Lesson 6.3: Refactoring generate_plan()

**You'll learn:** Rewriting a function to be generic while preserving existing behavior. This is the hardest lesson in this chapter — take it slow.

**Video resources:**
- Search YouTube: `"Python refactoring functions step by step tutorial"`
- Search YouTube: `"how to refactor tightly coupled Python code"`
- Search YouTube: `"refactoring legacy code Python" beginner`

**Task:** Rewrite `generate_plan()` in `planner.py` to work with the new models:

1. **Read the skill from the goal's requirements**, not from a hardcoded `"agility"` string. Look through the goal's requirements for ones with `type: "skill"` — those tell you which skill(s) to plan training for.

2. **Track item outputs generically.** Instead of `current_marks`, use a dictionary like `{"marks_of_grace": 0}`. After each task step, add that task's `outputs` to the running totals. For a goal with no item requirements, this dictionary stays empty — and that's fine.

3. **Stop conditions come from requirements.** Currently the code stops at `current_marks >= 260`. Instead, after each step, check: are all skill requirements met? Are all item requirements met? If yes, stop.

4. **Handle pure skill goals.** If a goal only has skill requirements and no item requirements (like a future "99 Fishing" goal, or the skill parts of Birdhouse Runs), the plan is just: find the right task for the current level, calculate XP to next task's range, repeat until target level.

5. **Don't handle quests or sub-goals yet** — that's the next lesson. For now, just get single-skill + optional item goals working generically. The Graceful goal should produce the same plan as before.

**Test it:**
```bash
python -m osrs_planner plan "Walks Unseen" --mode ironman --goal full_graceful --skiller
```
Compare the output to what it was before. The numbers should match.

**Deliverable:** `generate_plan()` works with the new models. Graceful plan output matches previous version. The function no longer references "agility" or "marks" by name.

---

### Lesson 6.4: Sub-Goals and Dependency Chains

**You'll learn:** Recursive problem-solving and dependency resolution. This is the most conceptually interesting lesson — your planner becomes a real planning engine.

**Video resources:**
- Search YouTube: `"dependency resolution algorithm Python tutorial"`
- Search YouTube: `"topological sort explained simply" algorithm`
- Search YouTube: `"recursive functions Python beginner tutorial"`
- Search YouTube: `"tree traversal depth first Python" beginner`

**Task:** Now tackle the hard part — goals that depend on other goals and quests.

1. **Write the Birdhouse Runs goal JSON** (`birdhouse_runs.json`). It doesn't need to be perfect or complete — it's a design prototype. The structure should express:
   - Skill requirements: Hunter 5, Crafting 5
   - Conditional requirement: Construction 25 (ironman only)
   - Quest requirement: Bone Voyage
   - Bone Voyage requires: 100 Kudos + 1 Quest Point
   - **100 Kudos is a sub-goal** with its own path:
     - Natural History Quiz: 28 kudos (no prerequisites, just go do it)
     - The Dig Site quest: unlocks Uncleaned Finds (50 kudos), but The Dig Site requires 10 Agility, 10 Herblore, 25 Thieving
     - Remaining ~22 kudos from Timeline Displays, Ancient Relics, or reporting quests to Historian Minas

   Think of 100 Kudos as a mini-goal *inside* the Birdhouse Runs goal. It has its own dependency tree that must be resolved before Bone Voyage can be attempted.

2. **Think about how `generate_plan()` should handle this.** When it encounters a quest requirement, it needs to:
   - Check the quest's own requirements
   - If those aren't met, plan for them first
   - If a quest requires another quest, go deeper
   - Eventually return to the top-level goal once all prerequisites are satisfied

   This is a recursive process — "to do X, I first need Y, and to do Y, I first need Z." The plan output should be ordered: Z first, then Y, then X.

3. **Implement a `resolve_dependencies()` function** (or expand `generate_plan()`) that:
   - Takes a goal and an account
   - Walks the requirement tree (skill reqs, quest reqs, sub-goals)
   - For each unmet requirement, generates the steps to meet it
   - Returns a flat, ordered list of steps: "train Thieving to 25, train Herblore to 10, complete The Dig Site, do Uncleaned Finds, do Natural History Quiz, complete Bone Voyage, train Hunter to 5, train Crafting to 5, start birdhouse runs"

4. **Handle ironman-specific requirements.** If the account is an ironman/HCIM/GIM/HCGIM, include the Construction 25 requirement. If the account is a normal account, skip it (they can buy clockwork from a shop).

5. **Don't aim for a perfect plan** — aim for a *correct* plan. The ordering might not be optimal (maybe it's more efficient to train multiple skills in a different order), but every prerequisite should be listed before the thing that depends on it.

**Deliverable:** A `birdhouse_runs.json` that expresses the full dependency tree. `generate_plan()` (or `resolve_dependencies()`) that produces an ordered list of steps to unlock birdhouse runs from scratch, including quest prerequisites and the Kudos sub-goal.

---

### Lesson 6.5: Updating the CLI and API

**You'll learn:** How to present complex, nested plan data in a readable format — both in the terminal and as JSON.

**Video resources:**
- Search YouTube: `"Python argparse subcommands advanced tutorial"`
- Search YouTube: `"FastAPI response model Pydantic tutorial"`
- Search YouTube: `"Python CLI formatting rich output"` (for ideas, not required)

**Task:** The CLI and API still hardcode "Marks of Grace" and "Current Agility." Update them for the new generic system:

1. **Fix `cli.py`:**
   - Print the goal's actual requirements (not always "Marks of Grace")
   - Print the correct skill name(s) and current level(s)
   - For multi-step dependency plans, group steps by phase:
     ```
     Plan: Birdhouse Runs for Walks Unseen

     Phase 1: Prerequisites
       Step 1. Train Thieving to 25
       Step 2. Train Agility to 10
       Step 3. Train Herblore to 10

     Phase 2: Quests
       Step 4. Complete The Dig Site
       Step 5. Earn 100 Kudos (Uncleaned Finds + Natural History Quiz)
       Step 6. Complete Bone Voyage

     Phase 3: Skill Training
       Step 7. Train Hunter to 5
       Step 8. Train Crafting to 5
       Step 9. Train Construction to 25 (ironman)

     Ready for birdhouse runs!
     ```
   - This doesn't have to be exactly this format — design something that makes sense to you

2. **Fix `api.py`:**
   - The plan endpoint should return the structured plan data as JSON
   - Include phases/groupings in the response so a future frontend can display them
   - `check_requirements()` should work with the new requirement types

3. **Fix `check_requirements()`** to handle all requirement types (skill, quest, item, kudos), not just agility level.

**Deliverable:** CLI prints readable plans for both Graceful and Birdhouse Runs. API returns structured plan JSON. No hardcoded skill names remain.

---

### Lesson 6.6: Testing the Refactored Planner

**You'll learn:** Testing complex logic with multiple code paths. Fixtures for different account types.

**Video resources:**
- Search YouTube: `"pytest fixtures tutorial beginner"`
- Search YouTube: `"pytest parametrize multiple test cases tutorial"`
- Search YouTube: `"Python testing complex logic" pytest`

**Task:** Update and expand `tests/test_planner.py`:

1. **Fix existing Graceful tests** for the new model structure. They broke when you changed `Goal` and `Task` — update them so they pass again.

2. **Add Birdhouse Runs tests:**
   - A fresh account (level 1 everything) gets the full dependency chain: skill training + quests + kudos
   - An account that already has Bone Voyage completed and the skills — plan should be empty or just "start birdhouse runs"
   - An ironman account includes the Construction 25 step; a normal account doesn't
   - A skiller account — can they even do Bone Voyage? The Dig Site? Flag any quests that grant combat XP

3. **Test sub-goal resolution:**
   - The 100 Kudos sub-goal correctly includes The Dig Site prerequisites
   - Steps are ordered correctly (prerequisites before the things that depend on them)

4. **Test edge cases:**
   - Account missing a skill from their stats (hiscores might not return level 1 skills)
   - Goal where some requirements are met and others aren't

5. Run all tests: `pytest tests/ -v`

**Deliverable:** All tests green. Both goal types covered. Dependency resolution tested.

---

## Verification (Chapter 6)

After Chapter 6, you should be able to:
- `python -m osrs_planner plan "Walks Unseen" --mode ironman --goal full_graceful --skiller` — same Graceful plan as before
- `python -m osrs_planner plan "Walks Unseen" --mode ironman --goal birdhouse_runs` — a full plan showing skill training, quest prerequisites, kudos, and Bone Voyage
- `pytest tests/ -v` — all green, covering both goal types and dependency resolution

---

## Chapter 7: Polish & Quality of Life

**Goal: "The tool handles real-world usage without breaking"**

Chapter 6 rebuilt the planner's engine. This chapter makes the tool pleasant to use — resume partway through a goal, get clean error messages, and stop typing `--skiller` every time.

---

### Lesson 7.1: The `--have` Flag

**You'll learn:** How to pass optional initial state through multiple layers of your application (CLI -> planner -> output).

**Video resources:**
- Search YouTube: `"Python argparse custom argument types nargs"`
- Search YouTube: `"passing state through function layers Python design"`

**Task:** The planner always assumes you're starting from scratch. But you might already have 120 marks of grace, or you might already have The Dig Site quest completed. Add a way to tell the planner what you already have.

1. **Design a `--have` flag** that accepts key=value pairs for starting state:
   ```bash
   # I already have 120 marks saved up
   python -m osrs_planner plan "Walks Unseen" --mode ironman --goal full_graceful --have marks_of_grace=120

   # I already completed The Dig Site
   python -m osrs_planner plan "Walks Unseen" --mode ironman --goal birdhouse_runs --have quest:the_dig_site=complete
   ```

2. **Update `generate_plan()`** to accept an optional starting state dictionary. If marks_of_grace is 120, the planner starts tracking from 120 instead of 0 — the Graceful plan needs fewer steps. If a quest is marked complete, skip its prerequisites.

3. **Update `api.py`** to accept have as a query parameter.

4. **Test it:** A Graceful plan with `--have marks_of_grace=120` should need 140 marks instead of 260.

**Deliverable:** Users can resume a plan partway through by declaring what they already have.

---

### Lesson 7.2: API Error Handling

**You'll learn:** HTTP status codes, FastAPI's `HTTPException`, and writing code that fails gracefully.

**Video resources:**
- Search YouTube: `"FastAPI error handling HTTPException tutorial"`
- Search YouTube: `"HTTP status codes explained 400 404 500" beginner`
- Search YouTube: `"FastAPI exception handlers custom error responses"`

**Task:** If you pass a bad player name to the API, FastAPI returns an ugly 500 error with a Python stack trace. Users should get clean JSON errors:

1. **Player not found -> 404:**
   ```
   GET /accounts/FakeName12345/stats?mode=ironman
   -> {"detail": "Player 'FakeName12345' not found"}
   ```
   Wrap `fetch_stats()` in `try`/`except` catching `PlayerNotFoundError`, raise `HTTPException(status_code=404, ...)`.

2. **Goal not found -> 404:**
   ```
   GET /accounts/Walks+Unseen/plan/fake_goal
   -> {"detail": "Goal 'fake_goal' not found"}
   ```
   Catch `FileNotFoundError` from `load_goal()`.

3. **Invalid mode -> 400:**
   ```
   GET /accounts/Walks+Unseen/stats?mode=fake_mode
   -> {"detail": "Invalid account mode: 'fake_mode'"}
   ```
   Catch `KeyError` from `AccountMode[mode]`.

4. **Test each error case** with `curl` or the Swagger docs at `/docs`.

**Deliverable:** Every API error returns clean JSON with the right status code. No more 500s for user mistakes.

---

### Lesson 7.3: Auto-Detect Skiller

**You'll learn:** Making decisions from data instead of asking the user to tell you things you can already figure out.

**Video resources:**
- Search YouTube: `"Python working with dictionaries iteration filtering"`

**Task:** A skiller has level 1 in all combat skills (Attack, Strength, Defence, Ranged, Magic, Prayer) and Hitpoints at 10. You already fetch these stats — the tool can figure this out.

1. **Write `detect_restrictions(account: Account) -> Account`:**
   - All combat skills level 1 + Hitpoints 10 -> `is_skiller = True`
   - Defence level 1, other combat skills trained -> `is_pure = True`
   - Otherwise both `False`

2. **Call it after `fetch_stats()`** in both `cli.py` and `api.py`. The `--skiller`/`--pure` flags still work as manual overrides.

3. **Print the detection:**
   ```
   Account type: Skiller (auto-detected)
   ```

4. **Test** with "Walks Unseen" (should auto-detect skiller) and a normal account.

**Deliverable:** Auto-detection of account restrictions. Manual flags still work as overrides.

---

### Lesson 7.4: List Goals

**You'll learn:** Scanning directories, presenting data, and building discovery features.

**Video resources:**
- Search YouTube: `"Python pathlib glob tutorial beginner"`
- Search YouTube: `"FastAPI multiple endpoints beginner"`

**Task:** Users should be able to see what goals are available.

1. **Write `list_goals() -> list[Goal]`** in `planner.py` — scans the `goals/` directory, loads each JSON file, returns a list of Goal objects.

2. **Add a CLI command:**
   ```bash
   python -m osrs_planner goals
   ```
   ```
   Available Goals
   ===============
   full_graceful     Full Graceful Set      Obtain all 6 pieces of the Graceful outfit
   birdhouse_runs    Birdhouse Runs         Unlock birdhouse trap runs on Fossil Island
   ```

3. **Add `GET /goals`** to `api.py` using the same `list_goals()` function.

4. **Handle an empty goals directory** gracefully.

**Deliverable:** Goal discovery from both CLI and API.

---

## Verification (Chapter 7)

After Chapter 7, you should be able to:
- `python -m osrs_planner plan "Walks Unseen" --mode ironman --goal full_graceful --have marks_of_grace=120` — plan resumes from 120 marks
- `curl http://localhost:8000/accounts/FakePlayer/stats` — returns clean 404 JSON
- `python -m osrs_planner stats "Walks Unseen" --mode ironman` — shows "Skiller (auto-detected)"
- `python -m osrs_planner goals` — lists all available goals
- `pytest tests/ -v` — all tests green

---

## What's Next

After Chapters 6 and 7, the planner handles complex dependency chains, serves clean API responses, and auto-detects account types. Here's the roadmap for what comes next:

### 1. OSRS Wiki API Integration
Instead of hand-writing XP rates, quest requirements, and skill methods in JSON files, pull them from the OSRS Wiki API. The wiki has structured data for every quest, skill, and item in the game. This means:
- Auto-generate goal definitions from wiki data
- Keep XP rates and quest requirements up to date without manual edits
- Add new goals by pointing at a wiki page instead of writing JSON by hand

This is the foundation — once the tool can read game data from the wiki, every feature after this gets easier.

### 2. Frontend (JavaScript Framework)
Build a real web UI for the planner. The FastAPI backend becomes a pure API, and a separate frontend (React, Vue, or Svelte) provides the visual experience. Design inspiration: sites like slayerscape.io — dark OSRS-themed aesthetic, skill icons, interactive plan visualization, progress tracking.

This is where you'll learn a second programming language (JavaScript/TypeScript) and a frontend framework. The choice of framework (React vs Vue vs Svelte) can be decided when you get here — each has trade-offs:

| Framework | Learning curve | Best for |
|---|---|---|
| Svelte | Gentlest (closest to plain HTML) | Small/medium projects, fast dev, great first framework |
| Vue | Moderate, excellent docs | Balanced choice, progressive complexity |
| React | Steepest, most job-relevant | Largest ecosystem, most transferable skill |

**Video resources for when you get here:**
- Search YouTube: `"JavaScript for Python developers" tutorial`
- Search YouTube: `"React vs Vue vs Svelte" 2025 comparison beginner`

### 3. Discord Bot
Bring the planner into your GIM group's Discord server. Your existing `fetch_stats`, `load_goal`, and `generate_plan` functions become Discord slash commands. Python's `discord.py` library handles the connection. By this point the planner and frontend are solid, so the bot is a thin layer on top.

Group-specific features:
- `!plan WalksUnseen birdhouse_runs` — generate a plan
- `!stats Tiger0295` — quick stat lookup
- `!group` — all 5 members' stats side by side
- `!suggest WalksUnseen` — "based on your stats, here's what to work on next"

**Video resources for when you get here:**
- Search YouTube: `"discord.py bot tutorial" 2025 Python`
- Search YouTube: `"discord slash commands Python tutorial"`

### Further Out
- **Session Planner** — "I have 2 hours tonight, what should I work on?"
- **Ironman Dependency Resolver** — deep chains like "Barrows Gloves requires X quest, which requires Y skill, which requires Z items to gather yourself"
- **SQLite Persistence** — save plans and track completion progress
- **RuneLite Plugin** — overlay the planner in the game client (Java project)
