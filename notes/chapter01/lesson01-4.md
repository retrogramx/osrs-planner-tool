# Lesson 1.4: XP Calculator Functions

## Files
- `src/osrs_planner/xp.py` — added `level_for_xp()` and `xp_remaining()`
- `tests/test_xp.py` — added 3 more tests (6 total)

---

## Functions Calling Functions
- Functions can use other functions you've already built
- `xp_remaining` uses `xp_for_level` internally — no need to re-index `XP_TABLE`
- Build small, focused functions and compose them together

## for Loops
- `for i in range(0, 99):` — loops with `i` going from 0 to 98
- The loop body is everything indented under the `for` line
- `return` inside a loop exits the function immediately — the loop stops

## Indentation Matters
- Python uses indentation to define code blocks — not braces `{}` like other languages
- Code under `for` is the loop body
- Code under `if` is the conditional body
- `return 99` indented under `for` = runs inside the loop (every iteration)
- `return 99` at the same level as `for` = runs after the loop finishes

## Variable Naming
- Don't reuse your parameter name as a loop variable — `for xp in range(...)` shadows the `xp` parameter, and you lose access to the input
- Use `i` (for index) when looping through indices

## Searching a Sorted List
- Walk through `XP_TABLE` with a loop
- When you find a threshold greater than your XP, the previous level is your answer
- If the loop finishes without finding one, you've met all thresholds (level 99)

## Common Mistakes
- `XP_TABLE(0, 98, 1)` — lists use `[]` for indexing, `()` is for calling functions. Use `range()` for generating numbers.
- `XP_TABLE[current_xp, target_level]` — lists take ONE index, not two
- `current_xp - target_level` — subtracting a level from XP mixes different units. Use `xp_for_level()` to convert level to XP first.
- `return xp()` — `xp` is a number, not a function. Numbers can't be called with `()`.
- `i = XP_TABLE - 1` — can't subtract a number from a list

## My Trial and Error

### xp_remaining
- **Attempt 1:** `return XP_TABLE[current_xp, target_level]` — tried two indices in a list
- **Attempt 2:** `return XP_TABLE[current_xp - target_level]` — math on indices, wildly out of bounds
- **Attempt 3:** `return current_xp - target_level` — subtracted a level number from XP (different units)
- **Attempt 4:** `return current_xp - xp_for_level` — forgot to call the function with `()`
- **Attempt 5:** `return current_xp - xp_for_level(target_level)` — subtraction order was backwards (negative result)
- **Attempt 6:** `return xp_for_level(target_level) - current_xp` — correct!

### level_for_xp
- **Attempt 1:** `if current_xp == 0: return xp()` — used global variable, tried to call a number
- **Attempt 2:** `for xp in XP_TABLE(0, 98, 1)` — tried to call list as function, shadowed parameter name
- **Attempt 3:** Loop with `return i - 1` and second `if` returning 99 inside loop — off by one, and early return on first iteration
- **Attempt 4:** Used `for/else` with `return i - 1` — `else` works but unnecessary, still off by one
- **Attempt 5:** Fixed to `return i` but `return 99` was indented inside the loop — ran on first iteration
- **Attempt 6:** `return i` inside loop, `return 99` after loop — correct!

## Edge Cases Discovered
- `xp_for_level(0)` returns level 99's XP due to negative indexing (from Lesson 1.2)
- `level_for_xp(83)` should return 2 (exactly on boundary = you've reached that level)
- `xp_remaining` when you already exceed the target returns a negative number — could handle later

## References
- **for loops**: https://docs.python.org/3/tutorial/controlflow.html#for-statements — `for`, `range()`, loop control
- **range()**: https://docs.python.org/3/library/stdtypes.html#range — generating sequences of numbers
- **break and continue**: https://docs.python.org/3/tutorial/controlflow.html#break-and-continue-statements — loop control flow
- **Indentation**: https://docs.python.org/3/reference/lexical_analysis.html#indentation — how Python uses whitespace
