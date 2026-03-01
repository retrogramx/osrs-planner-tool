# Chapter 2 Recap: Talking to the Hiscores

## What I Built
- A function that fetches real player stats from Jagex's servers
- Custom error handling for missing players and network failures
- A CLI command that displays formatted stats in the terminal
- Two new files: `hiscores.py` and `cli.py` plus `__main__.py`

## Files Created / Modified
```
osrs-planner-tool/
├── pyproject.toml                      # Added httpx dependency
├── src/
│   └── osrs_planner/
│       ├── __init__.py
│       ├── __main__.py                 # NEW — makes python -m work
│       ├── xp.py                       # (unchanged from Ch.1)
│       ├── models.py                   # (unchanged from Ch.1)
│       ├── hiscores.py                 # NEW — fetch_stats, error classes
│       └── cli.py                      # NEW — argparse, formatted output
└── tests/
    └── test_xp.py                      # (unchanged from Ch.1)
```

## Python Cheatsheet — New Concepts

### HTTP Requests with httpx
```python
import httpx

response = httpx.get("https://some-url.com")
response.status_code       # 200 = success, 404 = not found
response.text              # raw response as string
response.json()            # parse JSON into a Python dict
```

### f-strings
```python
name = "Adrian"
f"Hello, {name}!"                          # → "Hello, Adrian!"
f"https://example.com?player={rsn}"        # variables in URLs
f"{skill.name:<15} Level {skill.level}"    # with alignment formatting
```

### Dictionaries — Building and Accessing
```python
# Create empty and fill in a loop
skills = {}
skills["attack"] = Skill(name="Attack", level=1, xp=8)

# Access values
data["name"]           # get a value by key
data["skills"][0]      # first item of a list inside a dict

# Loop through
for skill in account.skills.values():    # loop through values only
    print(skill.name)
```

### Error Handling
```python
# Check for known problems
if response.status_code == 404:
    raise PlayerNotFoundError("Player not found")

# Catch unexpected problems
try:
    response = httpx.get(url)
except httpx.HTTPError:
    raise HiscoresError("Cannot reach Hiscores page")

# Custom error classes
class PlayerNotFoundError(Exception):
    pass
```

### argparse
```python
parser = argparse.ArgumentParser(description="My Tool")
parser.add_argument("rsn")                              # positional (required)
parser.add_argument("--mode", default="normal")         # named (optional)
args = parser.parse_args()
args.rsn       # the value the user typed
args.mode      # the value after --mode (or the default)
```

### Enum Access
```python
AccountMode.ironman          # direct access
AccountMode.ironman.name     # → "ironman" (the Python name)
AccountMode.ironman.value    # → "IM" (the assigned value)
AccountMode["ironman"]       # create from string (matches .name)
```

### String Formatting
```python
f"{value:<15}"      # left-align, 15 chars wide
f"{value:>10}"      # right-align, 10 chars wide
f"{value:>10,}"     # right-align, 10 chars, commas (16,687)
```

## Key Lessons Learned

### Order Matters in Functions
- Build variables BEFORE using them (suffix before URL)
- Python runs top to bottom — you can't use what doesn't exist yet

### Classes vs Variables
- `Skill` = the blueprint (class) — used to CREATE objects
- `skill` = actual data (variable) — one item from a loop
- `skills` = the dictionary you're building
- `Skill(name="Attack", ...)` = creating an object FROM the blueprint
- Don't use class names where variable names belong: `skills=skills` not `skills=[Skill]`

### Standard Library vs Third-Party
- **Standard library** (built-in): `argparse`, `json`, `os`, `sys` — just import
- **Third-party** (install): `httpx`, `pydantic` — add to pyproject.toml dependencies

### `__main__.py`
- Tiny file that makes `python -m your_package` work
- Just imports and calls your main function

## Common Mistakes This Chapter
| Mistake | Fix |
|---|---|
| `response.status_code` without print | `print(response.status_code)` |
| `print(a), b, c` — paren closes too early | `print(a, b, c)` — all inside parens |
| `Account = data["name"]` — overwrites the class | Use a different variable name |
| `{mode}` in URL — prints enum repr | Use `{suffix}` built from `mode.name` |
| `args.mode` is a string, not an enum | `AccountMode[args.mode]` to convert |
| Suffix built AFTER request uses it | Build suffix FIRST, then make request |
| `Skill[skill]` — indexing not creating | `Skill(name=..., level=..., xp=...)` |

## Verification
```
python -m osrs_planner "Walks Unseen" --mode ironman
```
Output:
```
Username: Walks Unseen (IM)
Attack          Level 1              8 XP
Defence         Level 1              0 XP
Agility         Level 20         4,560 XP
Woodcutting     Level 32        16,687 XP
... (all 24 skills)
```
