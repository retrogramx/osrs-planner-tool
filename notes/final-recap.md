# OSRS Planner Tool — Final Project Recap

## What I Built
A Python tool that works backwards from end goals to produce step-by-step training plans for Old School RuneScape accounts. Given an account's current stats and restrictions, it figures out what's needed and in what order.

## The Numbers
- **5 chapters**, **17 lessons**
- **9 passing tests**
- **11 Python files** (7 source, 2 test, 1 config, 1 JSON)
- **3 API endpoints**
- **1 CLI tool** with 2 commands

## Project Structure
```
osrs-planner-tool/
├── pyproject.toml
├── src/
│   └── osrs_planner/
│       ├── __init__.py              # Package marker
│       ├── __main__.py              # python -m entry point
│       ├── xp.py                    # XP table + math functions
│       ├── models.py                # Pydantic models (Account, Skill, Task, Goal)
│       ├── hiscores.py              # Fetch stats from Jagex API
│       ├── planner.py               # Plan generation engine
│       ├── cli.py                   # Command-line interface
│       ├── api.py                   # FastAPI web endpoints
│       └── goals/
│           └── full_graceful.json   # Graceful goal definition
├── tests/
│   ├── test_xp.py                   # 6 XP function tests
│   └── test_planner.py              # 3 planner tests
└── notes/
    ├── chapter01/                   # Lessons 1.1–1.6 + recap
    ├── chapter02/                   # Lessons 2.1–2.4 + recap
    ├── chapter03/                   # Lessons 3.1–3.5 + recap
    ├── chapter04/                   # Lesson 4.1 + recap
    ├── chapter05/                   # Lessons 5.1–5.3 + recap
    └── final-recap.md               # This file
```

## What Each File Does
| File | Purpose | Key Functions/Classes |
|---|---|---|
| `xp.py` | XP math | `xp_for_level()`, `level_for_xp()`, `xp_remaining()` |
| `models.py` | Data shapes | `AccountMode`, `Skill`, `Account`, `Task`, `Goal` |
| `hiscores.py` | API calls | `fetch_stats()`, `PlayerNotFoundError`, `HiscoresError` |
| `planner.py` | Plan engine | `load_goal()`, `check_requirements()`, `generate_plan()` |
| `cli.py` | Terminal UI | `main()` with `stats` and `plan` commands |
| `api.py` | Web API | 3 GET endpoints |

## Commands
```bash
# Look up player stats
python -m osrs_planner stats "Walks Unseen" --mode ironman

# Generate a plan
python -m osrs_planner plan "Walks Unseen" --mode ironman --skiller

# Start the web API
uvicorn osrs_planner.api:app --reload

# Run tests
pytest tests/ -v
```

## Chapter-by-Chapter Summary

### Chapter 1: Project Setup & XP Math
- Created project skeleton with `pyproject.toml` and `src/` layout
- Built `XP_TABLE` with all 99 level thresholds
- Wrote 3 XP utility functions
- Created Pydantic models for `Skill`, `Account`, `AccountMode`
- First test suite with 6 tests

### Chapter 2: Talking to the Hiscores
- Made HTTP requests to Jagex's hiscores API with `httpx`
- Parsed JSON responses into Pydantic models
- Added error handling (`PlayerNotFoundError`, `HiscoresError`)
- Built CLI with `argparse` for formatted stat display

### Chapter 3: The Planner Engine
- Designed `Task` and `Goal` models
- Created JSON goal definition for Full Graceful (9 rooftop courses)
- Built `generate_plan()` — the core algorithm
- Implemented partial course calculation (stop at 260 marks)
- Added formatted plan output to CLI
- Wrote 3 planner tests with fake accounts

### Chapter 4: Account Restrictions
- Added `--skiller` and `--pure` CLI flags
- Implemented warning system for skipped courses
- Built gap handling for when courses are unavailable
- Investigated 20-level mark penalty (removed — doesn't apply to current scenario)

### Chapter 5: FastAPI
- Created web API with 3 endpoints
- Stats and plan accessible from any browser
- Auto-generated Swagger documentation
- Rounded API values for clean output

## Python Concepts I Learned
| Concept | Where I Used It |
|---|---|
| Lists & indexing | `XP_TABLE`, `plan_steps` |
| Dictionaries | `skills = {}`, step data, API responses |
| Functions & return | Every file |
| for loops | Parsing skills, generating plans |
| if/elif/else | CLI commands, skip conditions |
| continue/break | Filtering courses, stopping at 260 marks |
| try/except | Network error handling |
| raise | Custom exceptions |
| Classes (Pydantic) | All data models |
| Enums | `AccountMode` |
| Imports | Every file |
| f-strings | URLs, CLI output, warnings |
| Type hints | All function signatures |
| pathlib | Finding JSON files |
| json module | Loading goal definitions |
| argparse | CLI argument parsing |
| Decorators | FastAPI endpoints |
| enumerate | Numbered step output |
| sum | Total hours/marks |
| round | Clean API values |
| list.append | Building plan steps |
| Tuple unpacking | `plan, warnings = generate_plan(...)` |

## Patterns I Keep Using
1. **Empty collection → Loop → Fill → Return** (fetch_stats, generate_plan)
2. **Parameter in, result out** (functions receive data, don't fetch their own)
3. **Write comments first, code second** (when stuck)
4. **Test in terminal with `python -c`** (quick verification)
5. **Read the error message** (last line tells you what's wrong)

## My Recurring Mistakes (and What I Learned)
| Mistake Pattern | Lesson |
|---|---|
| `Class.field` instead of `variable.field` | Classes are blueprints, variables hold data |
| `[]` instead of `()` or vice versa | `[]` indexes, `()` calls/creates |
| Using a value before creating it | Python runs top to bottom |
| `return` inside a loop | Exits the function, not just the loop |
| Forgetting `print()` | Evaluating isn't displaying |
| Missing `import` | Functions don't exist until imported |
| `==` with booleans | `if flag:` not `if flag == True:` |

## Future Improvements
- `--marks` flag to input current mark count
- Auto-detect skiller from combat stats
- Quest safety checking (grants_combat_xp field)
- More goal definitions (99 Fishing, Fire Cape, etc.)
- Diary bonus rates for courses
- Frontend UI (HTMX/Jinja2)
- SQLite persistence for saved plans
- 20-level mark penalty (accurate split calculation)
