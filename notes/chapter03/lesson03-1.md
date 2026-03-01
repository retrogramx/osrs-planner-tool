# Lesson 3.1: Defining a Goal in JSON

## Files
- `src/osrs_planner/models.py` — added `Task` and `Goal` models
- `src/osrs_planner/goals/full_graceful.json` — Graceful goal definition with 9 rooftop courses
- `src/osrs_planner/planner.py` — `load_goal()` function

---

## What I Learned
- How to design Pydantic models for a real-world problem (Task, Goal)
- How to create and structure a JSON data file
- How to load a JSON file into Pydantic models using `json` and `pathlib`
- The `**` unpacking operator for dictionaries
- Naming things well matters — clear field names make code readable

## Key Concepts

### Designing Models — Think About What the Planner Needs
Before writing code, think about what data each model needs:
- **Task** — one step the player can do (a rooftop course). Needs: name, skill, level range, rates, restrictions.
- **Goal** — the overall target. Needs: id, name, description, what to collect, and a list of tasks.

### JSON Files
- JSON is just data — no Python code, no logic
- Uses `true`/`false` (lowercase), not `True`/`False`
- No underscores in numbers (`12000` not `12_000`)
- No trailing commas after the last item
- Structure should match your Pydantic models

### Reading a JSON File
```python
import json

with open("path/to/file.json") as f:
    data = json.load(f)       # turns the file contents into a Python dict
```
- `open()` opens the file
- `with` automatically closes it when done
- `json.load(f)` reads from a file (not a string)
- `json.loads(s)` reads from a string (different function!)

### pathlib — Finding Files Relative to Your Code
```python
from pathlib import Path

GOALS_DIR = Path(__file__).parent / "goals"
```
- `__file__` → the path to the current Python file
- `.parent` → go up one directory
- `/ "goals"` → append a folder name to the path
- This works no matter where you run the command from

### `**` Dictionary Unpacking
```python
data = {"id": "full_graceful", "name": "Full Graceful Set", "target_marks": 260}

# These two are identical:
Goal(id="full_graceful", name="Full Graceful Set", target_marks=260)
Goal(**data)
```
- `**data` unpacks the dictionary into keyword arguments
- Only works when the dict keys match the model's field names exactly
- Pydantic handles nested models automatically — it built all 9 `Task` objects from the JSON without a loop

### Naming Conventions
- Keep field names descriptive: `xp_per_hour` not `xp_rate`, `marks_per_hour` not `drop_rate`
- Use `list[Task]` not `dict[int, Task]` when you don't need key-based lookup
- Use `str` for ids like `"full_graceful"` not `int` — slugs are more readable than numbers
- Don't shadow Python builtins — use `task_type` not `type`
- Simpler names are better: `tasks` not `list_of_tasks`

### File Naming for Goal Definitions
- Name the JSON file to match the goal id: `full_graceful.json` for id `"full_graceful"`
- Then loading is simple: `GOALS_DIR / f"{goal_id}.json"`
- No conversion logic needed — the id IS the filename

## The Complete Function
```python
import json
from pathlib import Path
from osrs_planner.models import Goal


GOALS_DIR = Path(__file__).parent / "goals"


def load_goal(goal_id: str) -> Goal:
    """Load a goal definition from a JSON file."""
    with open(GOALS_DIR / f"{goal_id}.json") as f:
        data = json.load(f)
    return Goal(**data)
```

## Pattern Comparison: load_goal vs fetch_stats
| Step | fetch_stats | load_goal |
|---|---|---|
| Build the path | URL from rsn + mode | File path from goal_id |
| Get raw data | `httpx.get(url)` | `open(file_path)` |
| Turn into dict | `response.json()` | `json.load(f)` |
| Build model | `Account(rsn=..., mode=..., skills=...)` | `Goal(**data)` |
| Return it | `return Account(...)` | `return Goal(...)` |

Same pattern, different data source. Recognizing these patterns makes new code easier to write.

## My Trial and Error
1. `with open(Path) as f:` → `Path` is the library, not a file path. Need `GOALS_DIR / f"{goal_id}.json"`
2. `goal_id = "full_graceful.json"` at module level → should be a function parameter, not hardcoded
3. `json.loads(Path(...).read_text())` → overcomplicating it. `json.load(f)` with the open file is simpler
4. `Goal(data[goal_id])` → `data` doesn't have a key called `"full_graceful"`. `data` IS the goal. Use `Goal(**data)`

## References & Further Reading
- **JSON format**: https://www.json.org — official spec, short and simple
- **Python `json` module**: https://docs.python.org/3/library/json.html — `json.load()`, `json.loads()`, `json.dump()`
- **Python `pathlib`**: https://docs.python.org/3/library/pathlib.html — `Path`, `.parent`, `/` operator for building paths
- **Python `with` statement**: https://docs.python.org/3/reference/compound_stmts.html#the-with-statement — automatic resource cleanup
- **`__file__` variable**: https://docs.python.org/3/reference/import.html#file__ — how Python tracks where a module lives
- **Pydantic models**: https://docs.pydantic.dev/latest/concepts/models/ — BaseModel, nested models, validation
- **`**kwargs` unpacking**: https://docs.python.org/3/tutorial/controlflow.html#unpacking-argument-lists — how `**dict` works
- **PEP 8 style guide**: https://peps.python.org/pep-0008/ — naming conventions, spacing rules
