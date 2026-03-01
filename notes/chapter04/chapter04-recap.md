# Chapter 4 Recap: Account Restrictions

## What I Built
- CLI flags `--skiller` and `--pure` for account restrictions
- Warning system that tells users when courses are skipped and why
- Gap handling for when a skipped course leaves a level gap
- Extended steps that keep the player at the previous course until the next opens up
- Caught and fixed a 20-level mark penalty that didn't actually apply

## Files Created / Modified
```
osrs-planner-tool/
├── src/
│   └── osrs_planner/
│       ├── cli.py                      # MODIFIED — --skiller, --pure flags, warning output
│       └── planner.py                  # MODIFIED — warnings, gap handling, last_task tracking
└── tests/
    └── test_planner.py                 # MODIFIED — updated for new return values, warning assertions
```

## Python Cheatsheet — New Concepts

### Boolean Flags in argparse
```python
parser.add_argument("--skiller", action="store_true")
# --skiller present   → args.skiller = True
# --skiller absent    → args.skiller = False
```

### Returning and Unpacking Multiple Values
```python
# Return two things
return plan_steps, warning

# Receive two things
plan_steps, warnings = generate_plan(account, goal)
```

### Tracking State Across Loop Iterations
```python
last_task = None
for task in tasks:
    if last_task:
        # use last_task for gap calculations
    last_task = task
```

### Gap Handling Pattern
```
1. Detect gap: current_level < task.from_level
2. Calculate gap: use last_task's rates
3. Append extended step
4. Update state (level, xp, marks)
5. Continue to normal course calculation
```

## Key Lessons Learned

### Think Through the Real Scenario
- I implemented the 20-level mark penalty, but then realized it doesn't apply
- The skiller reaches level 50 at Varrock and immediately switches to Falador
- Penalty applies for essentially zero time → removed it
- **Lesson:** Don't add complexity for scenarios that don't happen

### State Must Be Updated in the Right Place
```
Gap detected → calculate gap → append gap step → UPDATE STATE → calculate next course
```
- If you update state with the wrong variables (`xp_needed` instead of `gap_xp`), everything breaks
- If you set `current_level = task.to_level` instead of `task.from_level`, the next step shows wrong levels
- Order matters — state updates must happen BEFORE the next calculation uses them

### Tests Catch Real Bugs
- Changing `generate_plan` to return two values broke all existing tests
- The skiller test caught that the step count changed from 6 to 7 (added gap step)
- Warning assertions verify both count (`len(warnings) == 1`) and content (`"Canifis" in warnings[0]`)

## Skiller Plan Comparison (Non-Skiller vs Skiller)

### Non-Skiller (~21.1 hrs)
```
Al Kharid (20→30) → Varrock (30→40) → Canifis (40→50) → Falador (50→60) → Seers' (60→70) → Pollnivneach (partial)
```

### Skiller (~23.1 hrs)
```
Al Kharid (20→30) → Varrock (30→40) → Varrock extended (40→50) → Falador (50→60) → Seers' (60→70) → Pollnivneach (partial)
```
- ~2 extra hours for being a skiller
- Misses Canifis's high mark rate (17/hr vs Varrock's 10/hr)
- Compensated by needing more marks from later courses

## Verification
```bash
# All 9 tests pass
pytest tests/ -v

# Skiller plan with warnings
python -m osrs_planner plan "Walks Unseen" --mode ironman --skiller

# Normal plan (no restrictions)
python -m osrs_planner plan "Walks Unseen" --mode ironman
```

## Future Improvements
- **20-level mark penalty (accurate version):** Split extended steps into "before penalty" and "after penalty" segments when the player would cross the 20-level threshold mid-step. Only matters if two consecutive courses are locked.
- **`--marks` CLI flag:** Let the user input how many marks they already have (`--marks 45`) so the plan starts from a non-zero mark count instead of assuming 0.
- **`is_pure` logic:** Add defence-related restrictions to tasks. Some content requires defence levels or grants defence XP.
- **Quest requirements:** Add quest-type tasks with `grants_combat_xp` field. Auto-skip quests that give combat XP for skillers, with clear warnings.
- **Auto-detect skiller:** If all combat stats are level 1, automatically set `is_skiller=True` instead of requiring the flag.
- **Warning for impossible goals:** If ALL courses for a level range are locked (e.g., a hypothetical goal where every course requires combat), warn the user that the goal is impossible for their account type.
- **Diary bonuses:** Add diary-modified rates for Seers', Pollnivneach, Rellekka, and Ardougne as optional flags (`--kandarin-diary`, etc.).
