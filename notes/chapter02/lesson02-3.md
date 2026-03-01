# Lesson 2.3: Error Handling

## Files
- `src/osrs_planner/hiscores.py` — added `PlayerNotFoundError`, `HiscoresError`, `try`/`except` handling

---

## What I Learned
- How to handle errors gracefully instead of letting the program crash
- The difference between checking for known problems (`if`) and catching unexpected ones (`try`/`except`)
- How to create custom error classes
- `raise` to stop a function and report an error

## Key Concepts

### Two Approaches to Error Handling

**1. Check for known problems with `if`**
Use this when you can detect the problem before it causes a crash:
```python
if response.status_code == 404:
    raise PlayerNotFoundError("Player not found")
```
You already know it's a 404 — no need for try/except.

**2. Catch unexpected problems with `try`/`except`**
Use this when you don't know IF something will fail:
```python
try:
    response = httpx.get("https://some-url.com")    # might fail
except httpx.HTTPError:
    raise HiscoresError("Cannot reach Hiscores page")
```
The network could go down at any time — you can't check for it in advance.

### `raise` — Stopping and Reporting an Error
```python
raise ValueError("something went wrong")
```
- Stops the function immediately (like `return`, but for errors)
- Nothing after `raise` runs
- The error message shows up in the traceback

### Custom Error Classes
```python
class PlayerNotFoundError(Exception):
    pass

class HiscoresError(Exception):
    pass
```
- Inherit from `Exception` (the base class for all errors)
- `pass` means "nothing else to add" — the name is enough
- Custom names are more descriptive than generic `ValueError`
- Put them in the file that uses them (not in models.py)

### `continue` vs `break` vs `raise`
| Keyword | What it does |
|---|---|
| `continue` | Skip to next loop iteration |
| `break` | Exit the loop entirely |
| `raise` | Stop the function and report an error |
| `return` | Stop the function and send back a value |

### Error Handling Order in fetch_stats
```python
def fetch_stats(rsn, mode):
    # 1. Try the request (catch network errors)
    try:
        response = httpx.get(url)
    except httpx.HTTPError:
        raise HiscoresError("Cannot reach Hiscores page")

    # 2. Check status code (catch 404)
    if response.status_code == 404:
        raise PlayerNotFoundError("Player not found")

    # 3. Only parse if we got here safely
    data = response.json()
```

## Before vs After Error Handling
```
BEFORE (ugly crash):
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

AFTER (clear message):
osrs_planner.hiscores.PlayerNotFoundError: Player not found
```

## When to Use What
- **`if` + `raise`** — you can detect the problem (status codes, invalid input)
- **`try`/`except`** — something might fail unpredictably (network, file I/O)
- **Custom error classes** — when you want descriptive, specific error names
- **Built-in errors** (`ValueError`, `TypeError`) — for generic cases

## References
- **Exceptions**: https://docs.python.org/3/tutorial/errors.html — try/except, raise, custom exceptions
- **Built-in exceptions**: https://docs.python.org/3/library/exceptions.html — ValueError, TypeError, KeyError, etc.
- **Custom exceptions**: https://docs.python.org/3/tutorial/errors.html#user-defined-exceptions — creating your own error classes
- **Inheritance**: https://docs.python.org/3/tutorial/classes.html#inheritance — how `class MyError(Exception)` works
- **httpx exceptions**: https://www.python-httpx.org/exceptions/ — HTTPError and other httpx error types
