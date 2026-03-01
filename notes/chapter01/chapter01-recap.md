# Chapter 1 Recap: Project Setup & XP Math

## What I Built
- A real Python project I can import and test
- An XP lookup table with 3 utility functions
- Pydantic data models for OSRS accounts and skills
- A test suite with 6 passing tests

## Files Created
```
osrs-planner-tool/
├── pyproject.toml                      # Project config & dependencies
├── src/
│   └── osrs_planner/
│       ├── __init__.py                 # Makes it a package
│       ├── xp.py                       # XP_TABLE, xp_for_level, level_for_xp, xp_remaining
│       └── models.py                   # AccountMode, Skill, Account
└── tests/
    └── test_xp.py                      # 6 tests for XP functions
```

## Python Cheatsheet

### Project Setup
| Command | What it does |
|---|---|
| `python3 -m venv venv` | Create virtual environment |
| `source venv/bin/activate` | Activate it |
| `pip install -e .` | Install your package in editable mode |
| `pytest tests/ -v` | Run tests (verbose) |

### Syntax
```python
# Variables & constants
my_var = 10              # regular variable (lowercase)
MY_CONSTANT = 99         # constant (ALL_CAPS) — convention, not enforced

# Number readability
13_034_431               # underscores ignored by Python, same as 13034431

# Functions
def my_func(x: int) -> int:    # type hints on param and return
    return x + 1

# Lists
my_list = [0, 83, 174]
my_list[0]               # → 0 (first item, zero-indexed)
my_list[-1]              # → 174 (last item — negative wraps around)

# Dictionaries
my_dict = {"key": "value"}
my_dict["key"]           # → "value"

# Loops
for i in range(0, 99):   # i goes 0, 1, 2, ... 98
    if something:
        break            # exit loop early

# Imports
from osrs_planner.xp import xp_for_level    # from package.module import thing
```

### Indentation Rules
- Python uses indentation to define blocks (not braces `{}`)
- Everything under `def`, `for`, `if`, `class` must be indented
- Same indent level = same block
- Misplaced indentation changes behavior (e.g., `return` inside vs after a loop)

### Pydantic
```python
from pydantic import BaseModel
from enum import Enum

class AccountMode(Enum):         # fixed set of valid values
    normal = "normal"
    ironman = "ironman"

class Skill(BaseModel):          # auto-validates data
    name: str
    level: int
    xp: int

class Account(BaseModel):
    rsn: str
    mode: AccountMode
    skills: dict[str, Skill]
    is_skiller: bool = False     # default value — field is optional
```

### Testing
```python
# tests/test_xp.py
from osrs_planner.xp import xp_for_level

def test_level_1():                          # function name starts with test_
    assert xp_for_level(1) == 0              # assert checks if True, fails if False
```

### Key Concepts
- **`[]` vs `()`** — square brackets index into lists/dicts, parentheses call functions
- **`==` vs `=`** — double equals compares, single equals assigns
- **Test behavior, not internals** — test `xp_for_level(1)`, not `XP_TABLE[0]`
- **`src/` layout** — forces proper install, prevents silent import bugs
- **`__init__.py`** — empty file that makes a directory a Python package

## Style & Organization Tips

### File Organization
- `tests/` goes at the project root, NOT inside `src/` — tests aren't part of your application code
- `__init__.py` should be empty — no `#fill in` or placeholder comments
- TOML files don't use indentation under section headers — align to the left margin
- Add blank lines between TOML sections for readability

### Comments
- Use single `#`, not `##` — double hash has no special meaning in Python
- Use **docstrings** (not end-of-line comments) to document functions:
  ```python
  # Bad
  def xp_for_level(level: int) -> int:    ## tells you the xp for a level
      return XP_TABLE[level - 1]

  # Good
  def xp_for_level(level: int) -> int:
      """Return the minimum XP required for a given level."""
      return XP_TABLE[level - 1]
  ```
- Inline comments on model fields are fine for learning, but good names + type hints often make them unnecessary

### Formatting
- Use 4 spaces per indent level (Python standard)
- Two blank lines between top-level definitions (functions, classes)
- One blank line between methods inside a class
- Function/variable names are `lowercase_with_underscores` (PEP 8)
- Constants are `ALL_CAPS_WITH_UNDERSCORES`
- No trailing whitespace at the end of lines
- Closing brackets (`]`, `)`) align with the start of the line that opened them

## Verification
```
pytest tests/test_xp.py -v                    # 6 passed
python -c "from osrs_planner.xp import xp_remaining; print(xp_remaining(0, 99))"   # 13034431
```
