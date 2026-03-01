# Lesson 3.2: Checking Requirements

## Files
- `src/osrs_planner/planner.py` — added `check_requirements()` function

---

## What I Learned
- How to access nested data from existing models (`account.skills["agility"].level`)
- How to reuse functions from earlier chapters (`xp_remaining`, `level_for_xp`)
- Returning a dictionary of useful data instead of just a string message
- Writing comments first to plan what the function should do before coding

## Key Concepts

### Accessing Nested Model Data
```python
account.skills["agility"]          # → Skill(name='Agility', level=20, xp=4560)
account.skills["agility"].level    # → 20
account.skills["agility"].xp      # → 4560
```
- `account.skills` is a dict of Skill objects
- Use `["key"]` to get the Skill, then `.field` to get a specific value
- Chaining works: `account.skills["agility"].level` in one line

### Returning a Dictionary vs a String
```python
# NOT USEFUL — the planner can't do math on a string
return "Requirements not met"

# USEFUL — the planner gets actual numbers to work with
return {
    "current_level": 20,
    "current_xp": 4560,
    "marks_needed": 260,
    "xp_remaining": 269182,
}
```
- Strings are for humans to read
- Dictionaries are for code to use
- Return data that the NEXT function will need

### Reusing Earlier Functions
```python
from osrs_planner.xp import xp_remaining, level_for_xp

xp_remaining(current_xp, 60)        # how much XP to reach level 60?
level_for_xp(current_xp)            # what level is this XP amount?
```
- Functions you built in Chapter 1 are now tools you use in Chapter 3
- This is why we built small, focused functions — they compose together

### Function Parameters vs Fetching Data
```python
# WRONG — don't fetch data inside check_requirements
def check_requirements():
    account = fetch_stats("Walks Unseen", AccountMode.ironman)

# RIGHT — receive data as parameters
def check_requirements(account: Account, goal: Goal):
    # account is already loaded, just use it
```
- The function receives everything it needs as parameters
- The caller is responsible for fetching/loading the data
- This makes the function reusable for any account and any goal

### Hardcoding vs Flexibility
```python
# HARDCODED — works for Graceful only
"xp_remaining": xp_remaining(current_xp, 60)

# FLEXIBLE — works for any goal (future improvement)
"xp_remaining": xp_remaining(current_xp, goal.target_level)
```
- Hardcoding is fine when you only have one goal
- Refactor when you actually need a second goal, not before

## Getting Unstuck — My Toolkit
1. **Read my own notes** — especially pattern comparisons and function breakdowns
2. **Look at code I already wrote** — `fetch_stats` and `load_goal` follow the same patterns
3. **Test small pieces in the terminal** — `python -c "..."` to check values
4. **Write comments first, code second** — plan in plain English before writing Python
5. **Ask specific questions** — "how do I access agility level?" not "I'm stuck"
6. **Read the error message** — the last line usually tells you exactly what's wrong

## My Trial and Error
1. `goal(load_goal)` — tried to call `goal` as a function with `load_goal` as argument. `goal` is data, not a function
2. Returned only strings (`"Requirements met"`) — not useful for the planner, needs actual numbers
3. `level_for_xp(current_level)` — passed a level number instead of an XP amount. `level_for_xp` expects XP
4. Forgot to `print()` the result in the terminal — function returned data but nothing displayed

## The Complete Function
```python
def check_requirements(account: Account, goal: Goal):
    current_level = account.skills["agility"].level
    current_xp = account.skills["agility"].xp
    current_marks = 0
    marks_needed = goal.target_marks
    if current_marks == marks_needed:
        return "Congratulations. Goal achieved!"
    return {
        "current_level": current_level,
        "current_xp": current_xp,
        "marks_needed": marks_needed - current_marks,
        "xp_remaining": xp_remaining(current_xp, 60),
        "levels_remaining": 60 - level_for_xp(current_xp)
    }
```

## References
- **Python dictionaries**: https://docs.python.org/3/tutorial/datastructures.html#dictionaries — creating, accessing, returning dicts
- **Chaining attribute access**: https://docs.python.org/3/reference/expressions.html#attribute-references — `object.field.subfield`
- **Function parameters**: https://docs.python.org/3/tutorial/controlflow.html#defining-functions — how parameters work
- **f-strings**: https://docs.python.org/3/tutorial/inputoutput.html#formatted-string-literals — string formatting
