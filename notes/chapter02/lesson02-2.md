# Lesson 2.2: Parsing the Hiscores Response

## Files
- `src/osrs_planner/hiscores.py` — `fetch_stats()` function, parsing JSON into Account/Skill models

---

## What I Learned
- How to turn raw JSON data into Pydantic models
- f-strings for building dynamic strings
- Looping through data and building dictionaries
- The difference between **classes** (blueprints) and **variables** (actual data)

## What Was Hard
- Knowing where to put lines of code (inside vs outside functions, before vs after other lines)
- The difference between a class name (`Skill`, `Account`) and a variable holding data (`skill`, `skills`)
- Piecing together multiple concepts at once (loops + dictionaries + Pydantic + function parameters)

---

## Key Concepts

### f-strings — Putting Variables Inside Strings
```python
name = "Adrian"
greeting = f"Hello, {name}!"    # → "Hello, Adrian!"

rsn = "Walks Unseen"
url = f"https://example.com?player={rsn}"
# → "https://example.com?player=Walks Unseen"
```
- The `f` before the quote is what makes it work
- Variables go inside `{}` curly braces
- Without the `f`, it's just a normal string and `{rsn}` stays as literal text

### Enums Have a `.name` Property
```python
AccountMode.ironman.name     # → "ironman"  (the Python name)
AccountMode.ironman.value    # → "IM"       (the value you assigned)
```
- `.name` gives you the left side (the Python identifier)
- `.value` gives you the right side (what you set it to)

### `continue` vs `break` in Loops
```python
for item in my_list:
    if item == "skip_me":
        continue        # skip THIS item, go to next one
    if item == "stop":
        break           # exit the ENTIRE loop right now
    print(item)         # only runs if we didn't continue or break
```

### response.json() — Turning JSON Into a Dictionary
```python
response = httpx.get("https://some-url.com")
data = response.json()    # now data is a Python dict

data["name"]              # access a value by key
data["skills"]            # this is a list of dicts
data["skills"][0]         # first item in the list
data["skills"][0]["name"] # → "Overall"
```

---

## Functions — The Big Picture

### What Goes INSIDE a Function
Everything the function needs to do its job goes inside it. Code runs **top to bottom** inside the function.

```python
def fetch_stats(rsn: str, mode: AccountMode) -> Account:
    # Step 1: Build the URL suffix (needs to happen BEFORE the request)
    suffix = f"_{mode.name}"

    # Step 2: Make the request (uses suffix, so must come AFTER step 1)
    response = httpx.get(f"https://example.com{suffix}?player={rsn}")

    # Step 3: Parse the response (uses response, so must come AFTER step 2)
    data = response.json()

    # Step 4: Build objects (uses data, so must come AFTER step 3)
    skills = {}
    for skill in data["skills"]:
        skills[skill["name"]] = Skill(...)

    # Step 5: Return the result (must be LAST — nothing runs after return)
    return Account(rsn=data["name"], mode=mode, skills=skills)
```

### Order Matters!
You can't use a variable before you create it:
```python
# WRONG — suffix doesn't exist yet when you try to use it
response = httpx.get(f"https://example.com{suffix}")
suffix = "_ironman"

# RIGHT — create suffix first, then use it
suffix = "_ironman"
response = httpx.get(f"https://example.com{suffix}")
```

### What Goes OUTSIDE a Function
- `import` statements (always at the top of the file)
- Constants (like `XP_TABLE`)
- Other function/class definitions
- NOT your working code — that goes inside functions

---

## Loops + Dictionaries — Building Data Step by Step

### The Pattern: Empty Dict → Loop → Fill It Up
```python
skills = {}                      # 1. start with empty dict

for skill in data["skills"]:     # 2. loop through the raw data
    if skill["name"] == "Overall":
        continue                 # 3. skip items you don't want

    # 4. build an object and add it to the dict
    skills[skill["name"].lower()] = Skill(
        name=skill["name"],
        level=skill["level"],
        xp=skill["xp"]
    )

# after the loop, skills is fully populated
```

### What's Happening in Each Iteration
```
Iteration 1: skill = {"name": "Overall", ...}  → continue (skip)
Iteration 2: skill = {"name": "Attack", ...}   → skills["attack"] = Skill(name="Attack", ...)
Iteration 3: skill = {"name": "Defence", ...}  → skills["defence"] = Skill(name="Defence", ...)
... (24 more times)
```

### Adding to a Dictionary
```python
my_dict = {}                     # empty
my_dict["key1"] = "value1"       # now {"key1": "value1"}
my_dict["key2"] = "value2"       # now {"key1": "value1", "key2": "value2"}
```
- `my_dict["key"] = value` adds a new entry (or overwrites an existing one)

---

## Classes vs Variables — My Biggest Confusion

This was the hardest part. Here's the difference:

### Classes Are Blueprints
```python
Skill           # the blueprint — tells Python what a Skill looks like
AccountMode     # the blueprint — the set of valid modes
Account         # the blueprint — tells Python what an Account looks like
```

### Variables Hold Actual Data
```python
skill           # one item from the loop (a dict from the API)
skills          # the dictionary you're building
mode            # the specific mode passed into the function (e.g., AccountMode.ironman)
rsn             # the specific player name passed in (e.g., "Walks Unseen")
```

### Creating an Object FROM a Blueprint
```python
# Use the CLASS NAME + parentheses + actual values
Skill(name="Attack", level=1, xp=8)        # creates one Skill object
Account(rsn="Walks Unseen", mode=mode, skills=skills)   # creates one Account object
```

### Common Mistakes I Made
```python
# WRONG — Skill is the class, not data
skills=[Skill]
skills=[str, Skill]

# RIGHT — skills is the variable holding the dict you built
skills=skills

# WRONG — AccountMode is the whole enum class
mode=AccountMode

# RIGHT — mode is the parameter that was passed in
mode=mode

# WRONG — .name is for enums, data is a dict
rsn=data.name

# RIGHT — use square brackets for dicts
rsn=data["name"]
```

---

## My Trial and Error

### Building the URL
1. Hardcoded URL → needed to use f-string with `{rsn}` and `{suffix}`
2. Used `{mode}` directly → enum prints as `AccountMode.ironman`, not `"ironman"`
3. Built suffix AFTER the request → Python runs top to bottom, need suffix first
4. Got it: build suffix with if/else, then use it in f-string

### Building the Skills Dictionary
1. `Skill.name("{name}", ...)` → wrong syntax for creating objects
2. `Skill[skill]` → `[]` is indexing, `()` is creating
3. `Skill()` with nothing inside → need to pass actual values
4. Got it: `Skill(name=skill["name"], level=skill["level"], xp=skill["xp"])`

### The Return Statement
1. `return response.json()` → returns raw dict, not an Account
2. `Account(rsn=data.name, ...)` → data is a dict, use `data["name"]`
3. `mode=AccountMode.suffix` → suffix is a variable, not an enum member
4. `skills=[Skill]` → that's the type, not the data
5. Got it: `Account(rsn=data["name"], mode=mode, skills=skills)`

---

## The Complete Function
```python
def fetch_stats(rsn: str, mode: AccountMode) -> Account:
    if mode == AccountMode.normal:
        suffix = ""
    else:
        suffix = f"_{mode.name}"
    response = httpx.get(f"https://secure.runescape.com/m=hiscore_oldschool{suffix}/index_lite.json?player={rsn}")
    data = response.json()
    skills = {}

    for skill in data["skills"]:
        if skill["name"] == "Overall":
            continue
        skills[skill["name"].lower()] = Skill(name=skill["name"], level=skill["level"], xp=skill["xp"])
    return Account(rsn=data["name"], mode=mode, skills=skills)
```

## Quick Reference: Symbols Cheatsheet
| Symbol | Meaning | Example |
|---|---|---|
| `()` | Call a function or create an object | `Skill(name="Attack")`, `print("hi")` |
| `[]` | Index into a list or dict | `data["name"]`, `XP_TABLE[0]` |
| `{}` | Inside f-strings: insert variable | `f"hello {name}"` |
| `{}` | Create a dict | `skills = {}` |
| `=` | Assign a value | `x = 5` |
| `==` | Compare two values | `if x == 5:` |
| `.` | Access a property or method | `mode.name`, `response.json()` |

## References
- **f-strings**: https://docs.python.org/3/tutorial/inputoutput.html#formatted-string-literals — putting variables in strings
- **Enum .name and .value**: https://docs.python.org/3/library/enum.html#enum.Enum.name — accessing enum properties
- **Dictionaries**: https://docs.python.org/3/tutorial/datastructures.html#dictionaries — creating, accessing, looping
- **for loops**: https://docs.python.org/3/tutorial/controlflow.html#for-statements — looping through data
- **continue statement**: https://docs.python.org/3/tutorial/controlflow.html#break-and-continue-statements — skipping loop iterations
- **str.lower()**: https://docs.python.org/3/library/stdtypes.html#str.lower — converting strings to lowercase
