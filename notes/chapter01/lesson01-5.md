# Lesson 1.5: Your First Pydantic Model

## Files
- `src/osrs_planner/models.py` — `AccountMode` enum and `Skill` model

---

## Enums
- An enum is a fixed set of valid values — like account types in OSRS
- Import `Enum` from Python's standard library: `from enum import Enum`
- Define as a class with each value as a class attribute:
  ```python
  class AccountMode(Enum):
      normal = "normal"
      ironman = "ironman"
  ```
- Prevents invalid values — you can't accidentally use `"iroman"` (typo) if it's not in the enum

## Pydantic Models
- Pydantic models are classes that **validate their own data**
- Import `BaseModel` from pydantic: `from pydantic import BaseModel`
- Define fields using type hints:
  ```python
  class Skill(BaseModel):
      name: str
      level: int
      xp: int
  ```
- Create instances like: `Skill(name="agility", level=50, xp=101333)`
- Pydantic checks types automatically — passing `level="not a number"` raises a `ValidationError`
- Error messages are clear and tell you exactly what's wrong

## Why Pydantic?
- Catches bad data immediately instead of letting it cause bugs later
- Models serve as documentation — the fields and types describe the data shape
- Will integrate directly with FastAPI later (Chapter 5) — same models for validation and API responses

## REPL
- Stands for **Read-Eval-Print Loop**
- What you get when you run `python` with no file — an interactive scratchpad
- `python -c "..."` is a quick way to run a one-liner without entering the full REPL

## References
- **Enum**: https://docs.python.org/3/library/enum.html — defining fixed sets of values
- **Pydantic models**: https://docs.pydantic.dev/latest/concepts/models/ — BaseModel, fields, validation
- **Pydantic validation errors**: https://docs.pydantic.dev/latest/concepts/models/#model-methods-and-properties — what happens with bad data
- **Python REPL**: https://docs.python.org/3/tutorial/interpreter.html — interactive interpreter basics
