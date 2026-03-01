# Chapter 4: Account Restrictions

## Files
- `src/osrs_planner/cli.py` — added `--skiller` and `--pure` flags
- `src/osrs_planner/planner.py` — added warnings, gap handling for skipped courses
- `tests/test_planner.py` — updated tests for new return values and gap steps

---

## What I Learned
- How to add boolean flags to argparse (`action="store_true"`)
- How to return multiple values from a function (`return plan_steps, warning`)
- How to unpack multiple return values (`plan, warnings = generate_plan(...)`)
- How to handle gaps when courses are skipped (extended steps)
- How to track the previous task in a loop (`last_task`)
- The importance of questioning your own logic (20-level penalty catch)

## Key Concepts

### Boolean CLI Flags
```python
parser.add_argument("--skiller", action="store_true", help="Account is a level 3 skiller")
parser.add_argument("--pure", action="store_true", help="Account is a 1 Defence pure")
```
- `action="store_true"` → if flag is present, value is `True`. If absent, `False`
- No `=` or value needed: just `--skiller` not `--skiller true`
- Set on the account after fetching: `account.is_skiller = args.skiller`

### Returning Multiple Values
```python
# In the function
return plan_steps, warning

# When calling it
plan_steps, warnings = generate_plan(account, goal)
```
- Python packs multiple values into a **tuple** automatically
- You unpack them with matching variable names
- If you forget to unpack, the whole tuple becomes one variable and things break:
  `TypeError: list indices must be integers or slices, not str`

### Tracking Previous State in a Loop
```python
last_task = None

for task in goal.tasks:
    # ... use last_task for gap calculations ...
    last_task = task    # save for next iteration
```
- Set to `None` before the loop (no previous task yet)
- Update at the end of each iteration
- Use it to reference the previous course's rates when filling gaps

### Gap Handling — When a Course is Skipped
When Canifis is skipped, there's a gap from level 40 to 50 that needs filling:
```python
if current_level < task.from_level:
    gap_xp = xp_remaining(current_xp, task.from_level)
    gap_hours = gap_xp / last_task.xp_per_hour
    gap_marks = gap_hours * last_task.marks_per_hour
    plan_steps.append({
        "name": last_task.name + " (extended)",
        ...
    })
    # UPDATE STATE before continuing to the next course
    current_level = task.from_level
    current_xp = current_xp + gap_xp
    current_marks = current_marks + gap_marks
```
- The player stays at the PREVIOUS course until they can access the NEXT one
- Must update state after the gap so the next course starts from the right place
- `task.from_level` not `task.to_level` — the gap gets you to the START of the next course

### Printing Warnings
```python
# WRONG — prints the raw list object
print(warnings)    # → ['⚠ Skipped: Canifis...']

# RIGHT — loop through and print each one
for warning in warnings:
    print(warning)    # → ⚠ Skipped: Canifis...
```

## Bug I Caught: 20-Level Mark Penalty
- Implemented the penalty: marks drop to 20% when 20+ levels above a course
- But then realized it didn't apply to our scenario:
  - Varrock requires level 30, penalty at level 50
  - Extended step trains from 40 → 50
  - Player hits 50 and IMMEDIATELY switches to Falador
  - Penalty applies for essentially zero time
- **Lesson:** Don't implement features based on theory alone. Think through the actual scenario to see if it matters. Removed the penalty for now.

## My Trial and Error
1. `warning.append(f"Skipped: {['name']}")` → `['name']` is a list literal. Need `task.name`
2. `plan_steps, warnings = generate_plan(...)` → forgot to update all call sites, tests broke
3. `print(warnings)` → printed raw list. Need to loop and print each one
4. `current_xp = current_xp + xp_needed` inside gap block → `xp_needed` didn't exist yet. Use `gap_xp`
5. `current_level = task.to_level` inside gap block → should be `task.from_level` (gap gets you to the start, not end)
6. `plan_steps.append(gap_hours, gap_marks, gap_xp)` → append takes ONE argument (a dict), not three
7. Applied 20-level mark penalty to entire extended step → logically incorrect, removed it

## References
- **argparse action="store_true"**: https://docs.python.org/3/library/argparse.html#action — boolean flags
- **Returning multiple values**: https://docs.python.org/3/tutorial/datastructures.html#tuples-and-sequences — tuple packing/unpacking
- **None type**: https://docs.python.org/3/library/constants.html#None — representing "nothing"
- **list.append()**: https://docs.python.org/3/tutorial/datastructures.html#more-on-lists — adding to lists
