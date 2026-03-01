# Lesson 1.2: The XP Table

## Files
- `src/osrs_planner/xp.py` — `XP_TABLE` list and `xp_for_level()` function

---

## Python Lists
- A list is an ordered collection: `[0, 83, 174, ...]`
- Lists are **zero-indexed** — the first item is at position `[0]`, not `[1]`
- Negative indices wrap around: `[-1]` gives the last item, `[-2]` second to last, etc.
- Constants (values that never change) use `ALL_CAPS` naming by convention: `XP_TABLE`, not `xp_table`

## Number Formatting
- Commas in a list would be interpreted as separators: `11,805,606` → three values `11`, `805`, `606`
- Use **underscores** for readability instead: `11_805_606` — Python ignores them

## Type Hints
- `def xp_for_level(level: int) -> int:` breaks down as:
  - `level: int` — parameter named `level`, should be an integer
  - `-> int` — the function returns an integer
  - Python doesn't enforce these — they're documentation for humans (and tools like Pydantic later)

## Functions
- `def function_name(parameter):` — defines a function that takes an input
- The parameter is a **variable** you can use inside the function body
- `return` sends a value back to the caller — `return` with nothing gives `None`

## Indexing vs Calling
- `XP_TABLE[9]` — **square brackets** = indexing into a list (get item at position 9)
- `some_function(9)` — **parentheses** = calling a function with an argument
- You can't index into a number: `99[0]` doesn't work
- You can't call a number: `99()` doesn't work

## My Trial and Error

**Attempt 1:** `xp_for_level = [0 - 98]` — Python evaluated `0 - 98` as math (-98), not a range. Also reused the function name as a variable.

**Attempt 2:** `level(XP_TABLE[0,98])` — Used `level()` with parentheses (tried to call a number as a function). Also passed two indices to a list, which doesn't work.

**Attempt 3:** `return XP_TABLE[n - 1]` — Logic was right! But used `n` instead of the actual parameter name `level`.

**Attempt 4:** `return XP_TABLE[level - 1]` — correct!

## Edge Case Discovered
- `xp_for_level(0)` returns `13034431` (level 99's XP) because `XP_TABLE[0-1]` = `XP_TABLE[-1]` = last item
- Level 0 doesn't exist in OSRS, but the function silently returns a wrong answer instead of an error
- Will address this in Lesson 1.4 (edge cases)

## References
- **Python lists**: https://docs.python.org/3/tutorial/introduction.html#lists — indexing, slicing, negative indices
- **Numeric literals**: https://docs.python.org/3/reference/lexical_analysis.html#integer-literals — underscores in numbers
- **Type hints**: https://docs.python.org/3/library/typing.html — type annotation basics
- **Defining functions**: https://docs.python.org/3/tutorial/controlflow.html#defining-functions — `def`, parameters, `return`
- **PEP 8 naming**: https://peps.python.org/pep-0008/#naming-conventions — ALL_CAPS for constants
