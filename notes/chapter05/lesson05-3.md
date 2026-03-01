# Lesson 5.3: Plan Endpoint

## Files
- `src/osrs_planner/api.py` — added `GET /accounts/{rsn}/plan/{goal_id}` endpoint
- `src/osrs_planner/planner.py` — added `round()` to plan step values

---

## What I Learned
- Multiple path parameters in one endpoint (`{rsn}` and `{goal_id}`)
- Boolean query parameters (`skiller: bool = False`)
- Returning structured JSON responses with labeled keys
- Using `round()` to clean up decimal values
- Query parameters do NOT go in the `@app.get()` path

## Key Concepts

### Multiple Path Parameters
```python
@app.get("/accounts/{rsn}/plan/{goal_id}")
def get_plan(rsn: str, goal_id: str, mode: str = "normal", skiller: bool = False):
```
- Two path params: `rsn` and `goal_id`
- Two query params: `mode` and `skiller` (have defaults)

### Query Params Stay Out of the Path
```python
# WRONG — query params in the path cause 404
@app.get("/accounts/{rsn}/plan/{goal_id}?mode={mode}&skiller={skiller}")

# RIGHT — only path params in the path
@app.get("/accounts/{rsn}/plan/{goal_id}")
```
- FastAPI auto-creates query params from function arguments with defaults
- The `?key=value` part is handled for you

### Returning Labeled JSON
```python
# UNCLEAR — anonymous lists
return plan_steps, warnings    # → [[], []]

# CLEAR — labeled dictionary
return {
    "warnings": warnings,
    "plan": plan_steps
}
```
- Returning a tuple gives an unlabeled array
- Returning a dict gives a labeled JSON object
- Put warnings first so they appear at the top

### Rounding API Values
```python
round(0.7335833, 1)    # → 0.7 (1 decimal)
round(8803.456)        # → 8803 (nearest integer)
```
- Round in `generate_plan` before appending to `plan_steps`
- Affects both CLI and API output since they share the same function

## My Trial and Error
1. `@app.get("/accounts/{rsn}/plan/{goal_id}?mode=ironman&skiller=true")` → 404 error. Query params don't go in the path
2. `fetch_stats(rsn, AccountMode[mode], skiller, pure)` → `fetch_stats` only takes 2 args. Set skiller/pure on account after fetching
3. `return plan_steps, warnings` → warnings at the bottom as anonymous list. Changed to labeled dict

## References
- **FastAPI path params**: https://fastapi.tiangolo.com/tutorial/path-params/ — multiple path variables
- **FastAPI query params**: https://fastapi.tiangolo.com/tutorial/query-params/ — optional parameters
- **round()**: https://docs.python.org/3/library/functions.html#round — rounding numbers
- **FastAPI response model**: https://fastapi.tiangolo.com/tutorial/response-model/ — controlling response structure
