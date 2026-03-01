# Lesson 3.5: Testing the Planner

## Files
- `tests/test_planner.py` — 3 tests for `generate_plan()`

---

## What I Learned
- How to create fake data for testing instead of hitting a real API
- Testing the number of steps in a plan with `len()`
- Testing what's IN the data, not just how much
- Checking that something is NOT present with `not in`

## Key Concepts

### Fake Accounts for Testing
Don't call `fetch_stats` in tests — create accounts directly:
```python
account = Account(
    rsn="TestPlayer",
    mode=AccountMode.normal,
    skills={"agility": Skill(name="Agility", level=1, xp=0)}
)
```
- Fast — no network request
- Reliable — doesn't depend on internet or real player data
- Controllable — you pick the exact stats you want to test

### Testing How Many Steps
```python
plan = generate_plan(account, goal)
assert len(plan) == 7
```
- `len(list)` returns how many items are in a list
- Tests that the right number of courses are included

### Testing What's IN the Plan
```python
# First step starts at level 30
assert plan[0]["from_level"] == 30

# Access specific steps by index
plan[0]     # first step
plan[-1]    # last step
```

### Testing What's NOT in the Plan
```python
for step in plan:
    assert "Canifis" not in step["name"]
```
- `not in` checks that a string doesn't contain a substring
- Loop through all steps to make sure NONE of them have it

### Using Realistic Test Data
```python
# Level 30 has 13,363 XP — use the real value
skills={"agility": Skill(name="Agility", level=30, xp=13363)}
```
- Use actual XP values from your XP table so the math is correct
- `xp_for_level(30)` → `13363`

## The Tests
```python
# Test 1: Fresh account — 7 steps (stops at 260 marks)
def test_level_1_agility():
    assert len(plan) == 7

# Test 2: Level 30 — skips Draynor and Al Kharid
def test_level_30_agility():
    assert plan[0]["from_level"] == 30
    assert len(plan) == 5

# Test 3: Skiller — Canifis filtered out
def test_skiller():
    assert len(plan) == 6
    for step in plan:
        assert "Canifis" not in step["name"]
```

## What Makes a Good Test
- **Test behavior, not internals** — assert on the plan output, not on private variables
- **Use known inputs** — fake accounts with specific levels let you predict the result
- **Check multiple things** — both length AND content (e.g., first step's from_level AND total steps)
- **Test edge cases** — skiller, high level, fresh account are all different scenarios
- **No network calls** — tests should be fast and work offline

## References
- **pytest**: https://docs.pytest.org/en/stable/getting-started.html — test framework basics
- **len()**: https://docs.python.org/3/library/functions.html#len — counting items in a list
- **assert**: https://docs.python.org/3/reference/simple_stmts.html#the-assert-statement — test assertions
- **not in**: https://docs.python.org/3/reference/expressions.html#membership-test-operations — checking membership
- **List indexing**: https://docs.python.org/3/tutorial/introduction.html#lists — `plan[0]`, `plan[-1]`
