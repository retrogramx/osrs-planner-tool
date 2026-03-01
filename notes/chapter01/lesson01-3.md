# Lesson 1.3: Your First Test

## Files
- `tests/test_xp.py` — first 3 tests for `xp_for_level()`

---

## pytest Basics
- Test files must start with `test_` (e.g., `test_xp.py`) — that's how pytest finds them
- Test functions must also start with `test_` (e.g., `def test_level_1():`)
- Run tests with `pytest tests/test_xp.py -v` — the `-v` flag means verbose (shows each test name and pass/fail)
- Tests live in `tests/` at the project root, NOT inside `src/` — tests aren't part of your application code

## assert
- `assert expression` — if the expression is `True`, the test passes. If `False`, it fails.
- `assert xp_for_level(1) == 0` — "I assert that calling xp_for_level with 1 gives back 0"
- `==` is comparison (is this equal?), `=` is assignment (set this variable)

## Imports in Tests
- Use the same import style as any other Python file: `from osrs_planner.xp import xp_for_level`
- Import the **function**, not the raw data — test behavior, not internals
- If you test `XP_TABLE[0] == 0` directly, you're just checking the list, not your function

## My Trial and Error

**Attempt 1:** `import xp_for_level, XP_TABLE from xp.py` — wrong syntax. Python imports are `from module import thing`, not the other way around. Also no `.py` in import paths.

**Attempt 2:** Imported `xp_for_level` correctly but used `XP_TABLE[0]` in asserts — tested the raw list instead of the function. Also forgot to import `XP_TABLE`.

**Attempt 3:** `assert xp_for_level(1) == 0` — correct! Tests the function's behavior.

## Why Test the Function, Not the List?
- The function is your **public interface** — it's what other code will call
- If you later change how the data is stored (e.g., calculate XP instead of a list), the tests still work
- Tests should verify **what** your code does, not **how** it does it internally

## References
- **pytest**: https://docs.pytest.org/en/stable/getting-started.html — getting started guide
- **assert statement**: https://docs.python.org/3/reference/simple_stmts.html#the-assert-statement — how assert works
- **Python imports**: https://docs.python.org/3/tutorial/modules.html — `from module import thing` syntax
