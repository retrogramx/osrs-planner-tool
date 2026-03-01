# Chapter 3 Recap: The Planner Engine

## What I Built
- Pydantic models for goals and tasks (`Task`, `Goal`)
- A JSON goal definition with all 9 rooftop agility courses
- A goal loader that reads JSON into Pydantic models
- A requirements checker that compares account stats to a goal
- A planner engine that generates step-by-step plans with time/marks estimates
- A `plan` CLI command with formatted output
- Partial course calculation so the plan doesn't overshoot
- Skiller filtering to skip combat-required courses
- Test suite with 3 planner tests using fake accounts (no API calls)

## Files Created / Modified
```
osrs-planner-tool/
├── src/
│   └── osrs_planner/
│       ├── models.py                   # MODIFIED — added Task, Goal
│       ├── planner.py                  # NEW — load_goal, check_requirements, generate_plan
│       ├── cli.py                      # MODIFIED — added plan command
│       └── goals/
│           └── full_graceful.json      # NEW — Graceful goal with 9 rooftop courses
└── tests/
    ├── test_xp.py                      # (unchanged from Ch.1)
    └── test_planner.py                 # NEW — 3 tests for generate_plan
```

## Python Cheatsheet — New Concepts

### Reading JSON Files
```python
import json
from pathlib import Path

GOALS_DIR = Path(__file__).parent / "goals"

with open(GOALS_DIR / "full_graceful.json") as f:
    data = json.load(f)
```

### Dictionary Unpacking
```python
data = {"id": "full_graceful", "name": "Full Graceful Set"}
Goal(**data)    # same as Goal(id="full_graceful", name="Full Graceful Set")
```

### Tracking State in a Loop
```python
current_marks = 0
for task in tasks:
    marks_earned = calculate()
    current_marks = current_marks + marks_earned    # running total
```

### Multiple Commands in CLI
```python
if args.command == "stats":
    # handle stats
elif args.command == "plan":
    # handle plan
```

### enumerate — Numbered Loops
```python
for i, step in enumerate(plan_steps, 1):
    print(f"Step {i}. {step['name']}")
```

### sum — Totaling Values
```python
total = sum(step["hours_left"] for step in plan_steps)
```

### Partial Calculations
```python
if marks_earned > marks_remaining:
    marks_earned = marks_remaining
    hours_left = marks_earned / task.marks_per_hour
    xp_needed = hours_left * task.xp_per_hour
```

### Number Formatting
```python
f"{value:,.0f}"     # commas, no decimals → 8,803
f"{value:.1f}"      # one decimal → 0.7
f"{value:.0f}"      # no decimals → 7
```

### Testing with Fake Data
```python
# Create a fake account — no API call needed
account = Account(
    rsn="TestPlayer",
    mode=AccountMode.normal,
    skills={"agility": Skill(name="Agility", level=1, xp=0)},
    is_skiller=True
)
goal = load_goal("full_graceful")
plan = generate_plan(account, goal)

# Assert on length, content, and absence
assert len(plan) == 6
assert plan[0]["from_level"] == 1
for step in plan:
    assert "Canifis" not in step["name"]
```

## Key Lessons Learned

### The Same Pattern Everywhere
| Function | Get Data | Process | Build | Return |
|---|---|---|---|---|
| `fetch_stats` | HTTP request | Loop + skip Overall | `skills = {}` | `Account(...)` |
| `load_goal` | Open JSON file | `json.load()` | `Goal(**data)` | `Goal` |
| `generate_plan` | Account + Goal | Loop + skip + calculate | `plan_steps = []` | `list` |

### Functions Receive Data, They Don't Fetch It
```python
# WRONG — function reaches out for its own data
def generate_plan():
    account = fetch_stats("Walks Unseen", ...)

# RIGHT — data is passed in as parameters
def generate_plan(account: Account, goal: Goal):
    # just use what was given
```

### Write Comments First
When stuck, write what the function should do in plain English before writing Python. Then replace comments with code one at a time.

### Classes vs Variables — The Recurring Theme
| Class (Blueprint) | Variable (Data) |
|---|---|
| `Task` | `task` (loop item) |
| `Goal` | `goal` (parameter) |
| `Account` | `account` (parameter) |
| `Skill` | `skill` (loop item) |

### Order of Operations in the Loop
```
1. Skip conditions (continue)      → filter out courses
2. Calculate full course values     → xp, hours, marks
3. Adjust for partial course        → cap marks if over target
4. Append step to plan              → save the step
5. Update state variables           → level, xp, marks
6. Check stop condition (break)     → exit if done
```

## Common Mistakes This Chapter
| Mistake | Fix |
|---|---|
| `Task.to_level` (class) | `task.to_level` (loop variable) |
| `goal(load_goal)` — calling data as function | `goal.target_marks` — access fields |
| `Goal(data[goal_id])` — wrong key | `Goal(**data)` — unpack the whole dict |
| `json.loads` for files | `json.load` (no s) for file objects |
| `open(Path)` — the library itself | `open(GOALS_DIR / f"{goal_id}.json")` — actual path |
| `return` inside loop | `return` after loop (unless breaking early) |
| `marks_earned >= 260` | `current_marks >= 260` — check total, not one step |
| `step['name'] ['from_level']` | `{step['name']} ({step['from_level']})` — separate expressions |

## Verification
```bash
# All 9 tests pass
pytest tests/ -v

# Stats command still works
python -m osrs_planner stats "Walks Unseen" --mode ironman

# Plan command works
python -m osrs_planner plan "Walks Unseen" --mode ironman
```

Output:
```
=====================================
Plan: Full Graceful Set for Walks Unseen
Current Agility: Level 20 (4,560 XP)
Target: 260 Marks of Grace
=====================================
Step 1. Al Kharid Rooftop Course (20 → 30)
  XP needed: 8,803
  Time left: ~0.7 hrs
  Marks: ~7
=====================================
Step 2. Varrock Rooftop Course (30 → 40)
  XP needed: 23,861
  Time left: ~1.7 hrs
  Marks: ~17
=====================================
...
 Total time: ~21.1 hrs left
 Total marks: ~260/260

Good luck, adventurer!
```
