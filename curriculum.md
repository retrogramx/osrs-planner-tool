# OSRS Planner Tool — Curriculum

## Context

You're building a personal OSRS planning tool that **works backwards from end goals** to produce step-by-step plans. Given an account's current stats and restrictions (e.g., level 3 skiller), the tool figures out what's needed and in what order. The first test case is "Full Graceful set" for the account "Walks Unseen" (a level 3 skiller who cannot gain any combat XP).

The approach prioritizes **small wins** — each lesson is a working piece of software that builds on the last. Start as plain Python scripts, layer FastAPI on top later.

**This is a learning project.** You're writing the code yourself. Claude's role is to guide, explain concepts, review code, and help debug — not to write everything.

---

## Tech Stack

- **Python 3.12+** with type hints throughout
- **httpx** for HTTP requests (async-ready, modern alternative to requests)
- **Pydantic** for data models (shared with FastAPI later)
- **pytest** for tests
- **FastAPI** added in a later chapter (not MVP)
- **SQLite** for persistence (later)
- **Data:** manually authored JSON goal definitions, static XP table

---

## Project Structure

```
osrs-planner-tool/
├── pyproject.toml                 # Project config, dependencies, CLI entry point
├── src/
│   └── osrs_planner/
│       ├── __init__.py
│       ├── models.py              # Pydantic models: Account, Skill, Goal, Requirement, Task, Plan
│       ├── xp.py                  # XP table, level-from-xp, xp-remaining calculations
│       ├── hiscores.py            # Fetch stats from secure.runescape.com
│       ├── planner.py             # Backward-chaining plan generator
│       ├── cli.py                 # CLI entry point (argparse)
│       └── goals/
│           └── graceful.json      # First goal definition: Full Graceful set
└── tests/
    ├── test_xp.py
    ├── test_hiscores.py
    └── test_planner.py
```

---

## Chapter 1: Project Setup & XP Math

**Goal: "I have a real Python project that knows the OSRS XP table"**

### Lesson 1.1: Your First Python Project

**You'll learn:** How Python projects are organized — `pyproject.toml`, `src/` layout, virtual environments, installing your own package in dev mode.

**Task:** Create the project skeleton:
- Create `pyproject.toml` with project name, Python version, and dependencies (just `pydantic` and `pytest` for now)
- Create the `src/osrs_planner/` directory with an `__init__.py`
- Create a virtual environment and install your package in editable mode (`pip install -e .`)
- Verify it works: `python -c "import osrs_planner; print('it works!')"`

**Deliverable:** A project you can import. No real code yet — just the skeleton.

---

### Lesson 1.2: The XP Table

**You'll learn:** Python lists, indexing, and how to store lookup data. Type hints on functions.

**Task:** Create `src/osrs_planner/xp.py` with:
- A list called `XP_TABLE` containing the XP required for each level 1–99 (get the values from the OSRS wiki)
- One function: `xp_for_level(level: int) -> int` that returns the minimum XP needed for a given level
- Test it manually: `python -c "from osrs_planner.xp import xp_for_level; print(xp_for_level(99))"` → should print `13034431`

**Deliverable:** A working function that looks up any level's XP threshold.

---

### Lesson 1.3: Your First Test

**You'll learn:** How pytest works — writing test functions, assertions, running tests.

**Task:** Create `tests/test_xp.py` with:
- A test that `xp_for_level(1)` returns `0`
- A test that `xp_for_level(99)` returns `13034431`
- A test that `xp_for_level(92)` returns `6517253` (the halfway point!)
- Run with `pytest tests/test_xp.py -v`

**Deliverable:** Green tests. You now have a safety net.

---

### Lesson 1.4: XP Calculator Functions

**You'll learn:** Writing functions that call other functions. Using loops or `bisect` for searching a sorted list.

**Task:** Add two more functions to `xp.py`:
- `level_for_xp(xp: int) -> int` — given a raw XP amount, what level is that? (e.g., `level_for_xp(14000000)` → `99`)
- `xp_remaining(current_xp: int, target_level: int) -> int` — how much XP do I still need? (e.g., `xp_remaining(0, 99)` → `13034431`)

Add tests for both. Think about edge cases: what if current XP is exactly on a level boundary? What if target is already met?

**Deliverable:** Three working, tested XP functions.

---

### Lesson 1.5: Your First Pydantic Model

**You'll learn:** What Pydantic is and why it's useful — classes that validate their own data. Enums for fixed sets of values.

**Task:** Create `src/osrs_planner/models.py` with:
- An `AccountMode` enum with values: `normal`, `ironman`, `hardcore_ironman`, `ultimate_ironman`, `group_ironman`
- A `Skill` model with fields: `name: str`, `level: int`, `xp: int`
- Try creating a `Skill(name="agility", level=50, xp=101333)` — it works
- Try creating a `Skill(name="agility", level="not a number", xp=101333)` — Pydantic rejects it

**Deliverable:** A `Skill` model that validates its data. You'll use this everywhere.

---

### Lesson 1.6: The Account Model

**You'll learn:** Nested Pydantic models, optional fields, boolean flags.

**Task:** Add to `models.py`:
- An `Account` model with: `rsn: str`, `mode: AccountMode`, `skills: dict[str, Skill]`, `is_skiller: bool` (default `False`)
- Create a test account manually in a Python REPL — build an `Account` with a few skills and print it
- Verify that `is_skiller=True` can be set for Walks Unseen's account

**Deliverable:** A complete Account model ready to be populated from the hiscores.

---

## Chapter 2: Talking to the Hiscores

**Goal: "I can look up any OSRS account's real stats from the terminal"**

### Lesson 2.1: Your First HTTP Request

**You'll learn:** How HTTP works (URLs, GET requests, status codes), the `httpx` library.

**Task:**
- Add `httpx` to your `pyproject.toml` dependencies and reinstall
- Write a small script (can be in `hiscores.py` or a scratch file) that:
  - Makes a GET request to `https://secure.runescape.com/m=hiscore_oldschool_ironman/index_lite.json?player=Walks+Unseen`
  - Prints the raw response status code and body
- Just get the data printing. Don't parse it yet.

**Deliverable:** You can see your own raw OSRS stats in your terminal.

---

### Lesson 2.2: Parsing the Hiscores Response

**You'll learn:** Parsing JSON in Python, mapping raw data to your Pydantic models.

**Task:** In `src/osrs_planner/hiscores.py`, build a function `fetch_stats(rsn: str, mode: AccountMode) -> Account`:
- Make the HTTP request (you wrote this in 2.1)
- The JSON response has a `skills` array — map each entry to a `Skill` model
- Build and return a full `Account` object
- Handle the different URL paths for each account mode

**Deliverable:** `fetch_stats("Walks Unseen", AccountMode.ironman)` returns a populated `Account`.

---

### Lesson 2.3: Error Handling

**You'll learn:** `try`/`except`, custom exceptions, handling HTTP errors gracefully.

**Task:** Make `fetch_stats` robust:
- Player not found (404) → raise a clear `PlayerNotFoundError`
- Network error → raise a clear `HiscoresError`
- Write tests using `pytest` mocking (mock the HTTP response so tests don't hit the real API)

**Deliverable:** Your code handles errors instead of crashing.

---

### Lesson 2.4: Building a CLI

**You'll learn:** `argparse` for command-line arguments, `__main__.py` entry points, string formatting.

**Task:** Create `src/osrs_planner/cli.py` and `src/osrs_planner/__main__.py`:
- Command: `python -m osrs_planner stats <rsn> [--mode ironman]`
- Output: a clean table of skills, levels, and XP
- Something like:
  ```
  Stats for Walks Unseen (ironman)
  ─────────────────────────────────
  Agility      Level 45    101,333 XP
  Fishing      Level 38     31,191 XP
  Thieving     Level 22      5,902 XP
  ...
  ```

**Deliverable:** A working CLI command. Show it to a friend — you made software.

---

## Chapter 3: The Planner Engine

**Goal: "I tell it I want Graceful, it tells me exactly what to do"**

### Lesson 3.1: Defining a Goal in JSON

**You'll learn:** JSON file format, loading JSON in Python, designing data structures.

**Task:** Create `src/osrs_planner/goals/graceful.json` with the Graceful set goal definition:
- The goal has requirements (Agility 60, 260 Marks of Grace)
- The goal has tasks — one per Agility course, each with a level range, XP/hr, marks/hr, and `combat_risk` flag
- Research the actual rooftop courses on the wiki and fill in real XP/hr and marks/hr values
- Write a function `load_goal(goal_id: str) -> Goal` that reads and parses the JSON

**Goal JSON structure:**
```json
{
  "id": "full_graceful",
  "name": "Full Graceful Set",
  "description": "Obtain all 6 pieces of the Graceful outfit",
  "requirements": [
    {"type": "skill", "skill": "agility", "level": 60},
    {"type": "item", "item": "marks_of_grace", "quantity": 260}
  ],
  "tasks": [
    {
      "id": "agility_1_to_10",
      "name": "Gnome Stronghold Agility Course",
      "skill": "agility",
      "from_level": 1,
      "to_level": 10,
      "xp_per_hour": 8000,
      "marks_per_hour": 0,
      "combat_risk": false
    }
  ]
}
```

**Deliverable:** Pydantic models for `Goal`, `Requirement`, and `Task`, plus a loader function.

---

### Lesson 3.2: Checking Requirements

**You'll learn:** Comparing data structures, filtering lists, the concept of "met vs unmet" requirements.

**Task:** Write a function `check_requirements(account: Account, goal: Goal) -> list[Requirement]` that:
- Takes the account's current stats and the goal's requirements
- Returns only the **unmet** requirements (skills not at target level yet)
- Use `xp_remaining()` from Chapter 1 to calculate how much XP is needed

**Deliverable:** Given an account and a goal, you can see exactly what's missing.

---

### Lesson 3.3: Building the Plan

**You'll learn:** Algorithm design — selecting the right task based on current level, accumulating totals.

**Task:** Write `generate_plan(account: Account, goal: Goal) -> Plan` in `planner.py`:
1. Check which requirements are unmet
2. For each unmet skill requirement, find the right sequence of tasks:
   - If you're level 1 Agility, you start at the Gnome course, then move to Draynor at 10, etc.
   - Skip tasks for levels you've already passed
3. For each task, calculate: XP needed, estimated time (XP needed / XP per hour), marks earned
4. Return a `Plan` with the ordered task list and totals

**Deliverable:** `generate_plan(account, graceful_goal)` returns a structured plan.

---

### Lesson 3.4: Printing the Plan

**You'll learn:** String formatting, making output human-readable.

**Task:** Add a CLI command `python -m osrs_planner plan <rsn> graceful --mode ironman` that:
- Fetches stats
- Generates the plan
- Prints it nicely:
  ```
  Plan: Full Graceful Set for Walks Unseen
  Current Agility: 1 (0 XP)
  Target: 60 Agility + 260 Marks of Grace

  Step 1: Gnome Stronghold Course (1 -> 10)
    XP needed: 1,154 | ~8.7 min | 0 marks

  Step 2: Draynor Village Rooftop (10 -> 20)
    XP needed: 3,370 | ~22.5 min | ~3 marks
  ...

  Total time: ~X hours
  Marks earned: ~Y / 260 needed
  ```

**Deliverable:** Run the command, see your plan. This is the core product.

---

### Lesson 3.5: Testing the Planner

**You'll learn:** Testing complex logic, creating test fixtures, testing with known inputs/outputs.

**Task:** Write `tests/test_planner.py`:
- Create a fake `Account` with known stats (don't hit the real API in tests)
- Test that a level 1 account gets all tasks
- Test that a level 30 account skips early courses
- Test that a level 60+ account shows "goal already met"

**Deliverable:** Confidence that your planner logic is correct.

---

## Chapter 4: Account Restrictions

**Goal: "It knows my skiller can't do combat and warns me"**

### Lesson 4.1: Filtering by Combat Risk

**You'll learn:** Boolean filtering, guard clauses, warning systems.

**Task:** Enhance `generate_plan()`:
- If `account.is_skiller` is `True`, filter out any task where `combat_risk` is `True`
- If filtering removes tasks that are needed, add a warning to the plan: "This goal requires combat — not available for skillers"
- For Graceful, all tasks are combat-safe, so this is about building the system for future goals

**Deliverable:** Skillers get safe plans. Unsafe goals get clear warnings.

---

### Lesson 4.2: Quest Safety Checking

**You'll learn:** Extending your data model, adding metadata to tasks.

**Task:** Add quest-type tasks to your goal format:
- A quest task has fields like `grants_combat_xp: bool` and `required_combat_level: int`
- When generating a plan for a skiller, automatically exclude quests that grant combat XP
- Surface a message: "Skipped: [Quest Name] — grants Attack XP"

**Deliverable:** The planner is skiller-aware for both skills and quests.

---

## Chapter 5: FastAPI

**Goal: "I can see my plan in a browser"**

### Lesson 5.1: Hello FastAPI

**You'll learn:** What a web framework does, decorators, running a server.

**Task:**
- Add `fastapi` and `uvicorn` to dependencies
- Create `src/osrs_planner/api.py` with a single endpoint: `GET /` returns `{"message": "OSRS Planner API"}`
- Run: `uvicorn osrs_planner.api:app --reload`
- Open `http://localhost:8000` in your browser — see your JSON
- Open `http://localhost:8000/docs` — see the auto-generated docs

**Deliverable:** A running web server. You're a backend developer now.

---

### Lesson 5.2: Stats Endpoint

**You'll learn:** Path parameters, query parameters, connecting your existing code to an API.

**Task:** Add endpoint `GET /accounts/{rsn}/stats?mode=ironman`:
- Call your existing `fetch_stats()` function
- Return the `Account` as JSON (Pydantic does this automatically)
- Test it in the `/docs` Swagger UI

**Deliverable:** Your account stats, in a browser.

---

### Lesson 5.3: Plan Endpoint

**You'll learn:** Combining multiple functions into an API response, error responses.

**Task:** Add endpoint `GET /accounts/{rsn}/plan/{goal_id}?mode=ironman`:
- Fetch stats → load goal → generate plan → return as JSON
- Add error handling: player not found → 404, goal not found → 404
- Add `GET /goals` to list available goal definitions

**Deliverable:** The full planner, accessible from any browser. Use `/docs` to test.

---

## Verification (End-of-Chapter Checks)

After each chapter, you should be able to:

1. **Ch.1:** `pytest tests/test_xp.py -v` — all green. `python -c "from osrs_planner.xp import xp_remaining; print(xp_remaining(0, 99))"` prints `13034431`.
2. **Ch.2:** `python -m osrs_planner stats "Walks Unseen" --mode ironman` — prints real stats.
3. **Ch.3:** `python -m osrs_planner plan "Walks Unseen" graceful --mode ironman` — prints a step-by-step plan with time estimates.
4. **Ch.4:** Same as Ch.3 but skiller-unsafe tasks are filtered out with clear warnings.
5. **Ch.5:** `uvicorn osrs_planner.api:app --reload` → open `http://localhost:8000/docs` → test all endpoints.

---

## How We'll Work Together

- **You write the code.** Claude will explain concepts, suggest approaches, and point you to docs.
- **You get stuck?** Share what you tried, and Claude will help debug and explain what went wrong.
- **Code review:** After you write something, Claude will review it and suggest improvements.
- **One function at a time.** Don't try to build a whole file at once. Write one function, test it, move on.
- **Ask anything.** "What does this error mean?", "How does X work in Python?", "Is this the right approach?" — all fair game.

---

## What We're NOT Building Yet

- Frontend UI (HTMX/Jinja2 — later)
- SQLite persistence (plans are generated on-the-fly for now)
- Wiki scraping (goal data is manual JSON)
- Multiple goal support (one goal at a time for MVP)
- Session planner ("what can I do in 1 hour")
