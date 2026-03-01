# Lesson 3.3: Building the Plan

## Files
- `src/osrs_planner/planner.py` — added `generate_plan()` function

---

## What I Learned
- How to simulate a multi-step process with a loop (tracking state as you go)
- Updating variables inside a loop to carry state between iterations
- Using `continue` for multiple skip conditions
- Using `break` to stop a loop early
- The difference between a class name (`Task`) and a loop variable (`task`)
- `.append()` to add items to a list

## Key Concepts

### Simulating a Process — Tracking State in a Loop
Unlike `fetch_stats` where each loop iteration is independent, `generate_plan` builds on the previous step. Each course changes the player's level, XP, and marks:

```python
current_level = 20
current_xp = 4560
current_marks = 0

for task in goal.tasks:
    # ... calculate and append step ...

    # UPDATE STATE for next iteration
    current_level = task.to_level
    current_xp = current_xp + xp_needed
    current_marks = current_marks + marks_earned
```

Without these updates, every course would think the player is still level 20 with 0 marks.

### Multiple Skip Conditions
```python
for task in goal.tasks:
    # Skip 1: already past this course
    if current_level >= task.to_level:
        continue
    # Skip 2: skiller can't do combat courses
    if task.combat_requirement and account.is_skiller:
        continue
    # Only reaches here if NEITHER skip triggered
```

### Stopping Early with break
```python
if current_marks >= 260:
    break    # exit the loop, we have enough marks
```
- Use `>=` not `==` — marks will almost never land exactly on 260
- Check the TOTAL (`current_marks`), not the amount from one step (`marks_earned`)

### list.append() — Adding Items to a List
```python
plan_steps = []
plan_steps.append({"name": "Al Kharid", ...})    # [step1]
plan_steps.append({"name": "Varrock", ...})       # [step1, step2]
plan_steps.append({"name": "Falador", ...})       # [step1, step2, step3]
```
- `.append()` adds one item to the end of the list
- Different from dict: `my_dict["key"] = value` vs `my_list.append(value)`

### Class vs Variable (Again!)
```python
# WRONG — Task is the blueprint class
if current_level > Task.to_level:

# RIGHT — task is the current item from the loop
if current_level > task.to_level:
```
- Capital `Task` = the class definition
- Lowercase `task` = the actual data you're looping through
- This came up in Chapter 2 with `Skill` vs `skill` too

### Boolean Shorthand
```python
# Verbose — works but unnecessary
if task.combat_requirement == True and account.is_skiller == True:

# Clean — booleans are already True/False
if task.combat_requirement and account.is_skiller:
```

### >= vs > for Skip Conditions
```python
# WRONG — Draynor (to_level=20) still shows for a level 20 player
if current_level > task.to_level:

# RIGHT — level 20 means you've completed Draynor
if current_level >= task.to_level:
```

## The Pattern: Empty Collection → Loop → Fill → Return
This pattern keeps showing up:

| Function | Collection | Loop Through | Fill With | Return |
|---|---|---|---|---|
| `fetch_stats` | `skills = {}` | `data["skills"]` | `Skill(...)` objects | `Account(...)` |
| `generate_plan` | `plan_steps = []` | `goal.tasks` | step dictionaries | `plan_steps` |

## My Trial and Error
1. `Task.to_level` → used class name instead of loop variable `task.to_level`
2. `task.combat_requirement == True` → verbose, cleaned to `task.combat_requirement`
3. `current_xp - xp_remaining(...)` → overcomplicated, `xp_remaining()` already gives the answer
4. `if marks_earned >= 260` → checked one course's marks, not the running total `current_marks`
5. `return plan_steps` inside the loop → returned after first course, needed to be after the loop
6. `current_marks = []` → marks is a number not a list, keep it as `0` and add to it

## Known Limitation
The last course in the plan shows the FULL course even if you only need a fraction of it to reach 260 marks. Could be refined later to calculate a partial course.

## References
- **list.append()**: https://docs.python.org/3/tutorial/datastructures.html#more-on-lists — adding items to lists
- **break statement**: https://docs.python.org/3/tutorial/controlflow.html#break-and-continue-statements — exiting loops early
- **Comparison operators**: https://docs.python.org/3/library/stdtypes.html#comparisons — `>=`, `>`, `==`, etc.
- **Boolean operations**: https://docs.python.org/3/library/stdtypes.html#boolean-operations-and-or-not — `and`, `or`, `not`
- **Truthiness**: https://docs.python.org/3/library/stdtypes.html#truth-value-testing — why `if my_bool:` works without `== True`
