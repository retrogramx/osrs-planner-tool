# Lesson 2.4: Building a CLI

## Files
- `src/osrs_planner/cli.py` — argparse setup, formatted stats output
- `src/osrs_planner/__main__.py` — makes `python -m osrs_planner` work

---

## What I Learned
- How to use `argparse` to read command-line input
- The difference between positional and named arguments
- How `__main__.py` lets you run a package with `python -m`
- String formatting with alignment and commas in f-strings
- Converting strings to enums

## Key Concepts

### argparse — Reading Terminal Input
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description="OSRS Planner Tool")

    # Positional argument (required, no dashes)
    parser.add_argument("rsn", help="Player name to look up")

    # Named argument (optional, double dash, has a default)
    parser.add_argument("--mode", default="normal", help="Account mode")

    # Parse what the user typed
    args = parser.parse_args()

    # Access the values
    args.rsn       # → "Walks Unseen"
    args.mode      # → "ironman"
```
- `argparse` is built into Python — no need to add to dependencies
- Other built-in libraries: `json`, `os`, `sys` (part of the **standard library**)
- Third-party libraries like `httpx`, `pydantic` need to be in `pyproject.toml`

### `__main__.py` — Making a Package Runnable
```python
# src/osrs_planner/__main__.py
from osrs_planner.cli import main

main()
```
- This tiny file lets you run `python -m osrs_planner` from the terminal
- Python looks for `__main__.py` when you use the `-m` flag
- It just calls your `main()` function — all the real logic is in `cli.py`

### Converting Strings to Enums
argparse gives you strings, but `fetch_stats` expects an `AccountMode` enum:
```python
# What argparse gives you
args.mode                    # → "ironman" (a string)

# What fetch_stats needs
AccountMode.ironman          # → an enum value

# How to convert
AccountMode[args.mode]       # → AccountMode.ironman
AccountMode["ironman"]       # → AccountMode.ironman
```
- `EnumClass["name"]` creates an enum from a string matching its Python name
- This is different from `EnumClass("value")` which matches the value ("IM")

### f-string Formatting for Alignment
```python
print(f"{skill.name:<15} Level {skill.level:<5} {skill.xp:>10,} XP")
```

| Format Code | Meaning | Example |
|---|---|---|
| `:<15` | Left-align, pad to 15 chars | `"Attack         "` |
| `:>10` | Right-align, pad to 10 chars | `"         8"` |
| `:>10,` | Right-align, 10 chars, add commas | `"    16,687"` |
| `:<5` | Left-align, pad to 5 chars | `"32   "` |

### Printing Multiple Values
```python
# WRONG — only prints skill.name, the rest does nothing
print(skill.name), skill.level, skill.xp

# RIGHT — all values inside the parentheses
print(skill.name, skill.level, skill.xp)

# BETTER — f-string for full control over formatting
print(f"{skill.name:<15} Level {skill.level}")
```

### Looping Through a Dictionary's Values
```python
# account.skills is a dict like {"attack": Skill(...), "agility": Skill(...)}

# Loop through just the values (the Skill objects)
for skill in account.skills.values():
    print(skill.name, skill.level)

# Loop through keys and values together
for key, skill in account.skills.items():
    print(key, skill.name)
```

## Files Created
- `src/osrs_planner/__main__.py` — 2 lines, makes `python -m` work
- `src/osrs_planner/cli.py` — argparse setup + formatted output

## My Trial and Error
1. `def main(fetch_stats):` → main takes no parameters, it gets input from argparse
2. `print(skill.name), skill.level` → closing paren too early, only prints name
3. `args.mode` is a string, not an enum → needed `AccountMode[args.mode]` to convert

## References
- **argparse**: https://docs.python.org/3/library/argparse.html — command-line argument parsing
- **argparse tutorial**: https://docs.python.org/3/howto/argparse.html — beginner-friendly walkthrough
- **`__main__.py`**: https://docs.python.org/3/library/__main__.html — making packages runnable with `python -m`
- **Format spec mini-language**: https://docs.python.org/3/library/string.html#format-specification-mini-language — `:<15`, `:>10,`, alignment codes
- **print()**: https://docs.python.org/3/library/functions.html#print — printing multiple values, separators
- **Enum access by name**: https://docs.python.org/3/library/enum.html#programmatic-access-to-enumeration-members — `EnumClass["name"]`
