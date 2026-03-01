# Lesson 5.2: Stats Endpoint

## Files
- `src/osrs_planner/api.py` — added `GET /accounts/{rsn}/stats` endpoint

---

## What I Learned
- Path parameters (`{rsn}` in the URL becomes a function argument)
- Query parameters (function arguments with defaults become `?key=value`)
- FastAPI auto-converts Pydantic models to JSON

## Key Concepts

### Path Parameters
```python
@app.get("/accounts/{rsn}/stats")
def get_stats(rsn: str):
```
- `{rsn}` in the URL path → function parameter `rsn`
- Every `{thing}` in the path must have a matching function parameter
- FastAPI extracts the value from the URL automatically

### Query Parameters
```python
def get_stats(rsn: str, mode: str = "normal"):
```
- Parameters with defaults become query parameters
- Accessed via `?mode=ironman` in the URL
- If not provided, uses the default value

### Path vs Query — How FastAPI Decides
- In the `@app.get()` path → **path parameter** (required, part of the URL)
- NOT in the path, but in the function → **query parameter** (optional, after `?`)

### Pydantic → JSON Automatically
```python
account = fetch_stats(rsn, AccountMode[mode])
return account    # FastAPI converts the Account model to JSON
```
- No need to manually convert — just return the Pydantic object
- This is why we used Pydantic from Chapter 1 — it pays off here

## My Trial and Error
1. `return fetch_stats` → returned the function itself, not the result. Need `return account`
2. Set `is_skiller = "skiller"` → booleans, not strings. Not needed for stats endpoint anyway

## References
- **Path parameters**: https://fastapi.tiangolo.com/tutorial/path-params/ — URL variables
- **Query parameters**: https://fastapi.tiangolo.com/tutorial/query-params/ — optional URL params
