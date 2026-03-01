# Lesson 3.4: Printing the Plan

## Files
- `src/osrs_planner/cli.py` — added `plan` command with formatted output
- `src/osrs_planner/planner.py` — added partial course calculation to `generate_plan()`

---

## What I Learned
- How to add multiple commands to a CLI with `if`/`elif`
- `enumerate()` for numbered loops
- `sum()` for totaling up values from a list
- Partial course calculation — only train as long as needed
- Formatting numbers with `:.1f`, `:,.0f` in f-strings

## Key Concepts

### Multiple CLI Commands with if/elif
```python
args = parser.parse_args()

if args.command == "stats":
    # handle stats
elif args.command == "plan":
    # handle plan
```
- `elif` = "else if" — checks another condition if the first was false
- Parse args FIRST, then check the command
- Each block has its own setup (fetch account, load goal, etc.)
- Variables created inside one block don't exist in the other

### enumerate() — Numbered Loops
```python
# Without enumerate — no step numbers
for step in plan_steps:
    print(step['name'])

# With enumerate — adds a counter
for i, step in enumerate(plan_steps, 1):
    print(f"Step {i}. {step['name']}")
# Step 1. Al Kharid Rooftop Course
# Step 2. Varrock Rooftop Course
```
- `enumerate(list, 1)` — the `1` means start counting from 1 (default is 0)
- Gives you TWO variables: `i` (the counter) and `step` (the item)

### sum() — Totaling Values
```python
total_hours = sum(step["hours_left"] for step in plan_steps)
total_marks = sum(step["marks_earned"] for step in plan_steps)
```
- `sum()` adds up all the values
- The expression inside is a **generator** — it loops and pulls out one value from each step
- Like a compressed for loop: "for each step, give me hours_left, then add them all up"

### Number Formatting in f-strings
| Code | Meaning | Example |
|---|---|---|
| `:,.0f` | Commas, no decimals | `8803` → `8,803` |
| `:.1f` | One decimal place | `0.7335` → `0.7` |
| `:.0f` | No decimal places | `7.335` → `7` |
| `:,` | Commas (integers) | `4560` → `4,560` |

### Partial Course Calculation
When you'd earn more marks than needed, calculate a fraction:
```python
marks_remaining = goal.target_marks - current_marks
if marks_earned > marks_remaining:
    marks_earned = marks_remaining
    hours_left = marks_earned / task.marks_per_hour
    xp_needed = hours_left * task.xp_per_hour
```
- Calculate how many marks you ACTUALLY need
- Work backwards: marks → hours → XP
- This goes BEFORE `plan_steps.append()` so the step gets the corrected values

### Accessing Dictionary Values in f-strings
```python
# Use single quotes inside since the f-string uses double quotes
print(f"Step {i}. {step['name']} ({step['from_level']} → {step['to_level']})")

# WRONG — chaining keys together
print(f"{step['name'] ['from_level'] ['→']}")

# RIGHT — each is a separate {expression}
print(f"{step['name']} ({step['from_level']} → {step['to_level']})")
```

## My Trial and Error
1. `plan_steps.index(0)`, `plan_steps.index(1)` — tried to manually index each step. The loop variable `step` already gives you each one
2. `step['name'] ['from_level'] ['→']` — chained keys together. Each value needs its own `{step['key']}` in the f-string
3. `generate_plan(args.command, account)` — passed the command string instead of account and goal objects
4. `account` didn't exist in the `elif` block — each block needs its own `fetch_stats` call
5. `python src/osrs_planner/cli.py` — ran the file directly instead of `python -m osrs_planner`
6. Forgot quotes around `"Walks Unseen"` — argparse saw `Unseen` as a separate argument

## References
- **enumerate()**: https://docs.python.org/3/library/functions.html#enumerate — numbered loops
- **sum()**: https://docs.python.org/3/library/functions.html#sum — adding up values
- **Generator expressions**: https://docs.python.org/3/tutorial/classes.html#generator-expressions — `x for x in list` syntax
- **if/elif/else**: https://docs.python.org/3/tutorial/controlflow.html#if-statements — branching logic
- **Format spec**: https://docs.python.org/3/library/string.html#format-specification-mini-language — number formatting codes
- **argparse subcommands**: https://docs.python.org/3/library/argparse.html#sub-commands — proper way to handle multiple commands (future improvement)
