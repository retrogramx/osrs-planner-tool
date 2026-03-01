# Lesson 2.1: Your First HTTP Request

## Files
- `pyproject.toml` — added `httpx` dependency
- `src/osrs_planner/hiscores.py` — initial HTTP request to hiscores API

---

## What I Learned
- How programs talk to the internet using **HTTP requests**
- The difference between a **website URL** (returns HTML for browsers) and an **API endpoint** (returns JSON for programs)
- How to use the `httpx` library to make GET requests from Python

## Key Concepts

### HTTP Basics
- **GET request** — asking a server "give me this data" (like loading a web page)
- **Status code** — a number the server sends back to tell you what happened:
  - `200` = success, here's your data
  - `404` = not found (e.g., player doesn't exist)
- **Response body** — the actual data that comes back (HTML, JSON, etc.)

### Website vs API
- **Website URL:** `https://secure.runescape.com/m=hiscore_oldschool_ironman/hiscorepersonal?user1=Walks+Unseen`
  - Returns an HTML page designed for humans in a browser
- **API URL:** `https://secure.runescape.com/m=hiscore_oldschool_ironman/index_lite.json?player=Walks+Unseen`
  - Returns raw JSON data designed for programs
  - This is what tools like RuneLite and WiseOldMan use

### httpx Basics
```python
import httpx

response = httpx.get("https://some-url.com")
response.status_code    # HTTP status code (200, 404, etc.)
response.text           # response body as a string
```

### print()
- Writing `response.status_code` by itself evaluates the value but doesn't display it
- You need `print(response.status_code)` to actually see it in the terminal

## What the Hiscores API Returns
```json
{
  "name": "Walks Unseen",
  "skills": [
    {"id": 0, "name": "Overall", "rank": 1249495, "level": 119, "xp": 29275},
    {"id": 17, "name": "Agility", "rank": 730309, "level": 20, "xp": 4560},
    ...
  ],
  "activities": [
    {"id": 0, "name": "Grid Points", "rank": -1, "score": 0},
    ...
  ]
}
```
- Each skill has: `id`, `name`, `rank`, `level`, `xp`
- `rank: -1` means unranked in that skill
- Activities include boss kills, clue scrolls, etc.

## What I Did
1. Added `httpx` to `pyproject.toml` dependencies
2. Ran `pip install -e .` to reinstall with the new dependency
3. Created `hiscores.py` with a GET request to the hiscores API
4. Printed the status code (`200`) and response body (JSON with all stats)

## Gotchas
- `response.status_code` alone doesn't print anything — need `print()`
- The API URL looks unfamiliar but it's the official Jagex endpoint

## References
- **httpx**: https://www.python-httpx.org/ — modern HTTP client for Python
- **HTTP status codes**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status — what 200, 404, 500, etc. mean
- **HTTP GET requests**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/GET — how GET requests work
- **JSON format**: https://www.json.org — the data format APIs use
- **OSRS Hiscores API**: https://runescape.wiki/w/Application_programming_interface#Hiscores — wiki docs on the endpoint
