# Chapter 5 Recap: FastAPI

## What I Built
- A web API with 3 endpoints serving real OSRS data
- Stats lookup accessible from any browser
- Plan generator accessible from any browser
- Auto-generated interactive API documentation (Swagger UI)

## Files Created / Modified
```
osrs-planner-tool/
├── pyproject.toml                      # MODIFIED — added fastapi, uvicorn
├── src/
│   └── osrs_planner/
│       ├── api.py                      # NEW — 3 endpoints
│       └── planner.py                  # MODIFIED — round() on values
```

## API Endpoints
| Method | Path | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/accounts/{rsn}/stats?mode=ironman` | Player stats |
| GET | `/accounts/{rsn}/plan/{goal_id}?mode=ironman&skiller=true` | Generate plan |

## Python Cheatsheet — New Concepts

### FastAPI Decorators
```python
@app.get("/path/{param}")
def my_function(param: str, query: str = "default"):
    return {"key": "value"}
```

### Path vs Query Parameters
```python
@app.get("/accounts/{rsn}/stats")
def get_stats(rsn: str, mode: str = "normal"):
#              ↑ path param    ↑ query param
#              (in URL path)   (after ? in URL)
```

### round()
```python
round(0.7335, 1)    # → 0.7
round(8803.5)       # → 8804
```

## Key Lessons Learned

### Pydantic Pays Off
- Models defined in Chapter 1 work directly with FastAPI
- `return account` auto-converts to JSON — no manual conversion
- Same models for validation, CLI, and API

### Reusing Existing Code
- `api.py` is only ~30 lines because all logic already exists
- `fetch_stats`, `load_goal`, `generate_plan` — just call them
- The API is a thin layer on top of your existing functions

### Path Decorators Only Get Paths
```python
# WRONG — 404 error
@app.get("/path?query=value")

# RIGHT
@app.get("/path")
def func(query: str = "value"):
```

## Verification
```bash
# Start server
uvicorn osrs_planner.api:app --reload

# Test in browser
http://localhost:8000                          # health check
http://localhost:8000/docs                     # Swagger UI
http://localhost:8000/accounts/Walks%20Unseen/stats?mode=ironman
http://localhost:8000/accounts/Walks%20Unseen/plan/full_graceful?mode=ironman&skiller=true

# All tests still pass
pytest tests/ -v
```

## References
- **FastAPI tutorial**: https://fastapi.tiangolo.com/tutorial/ — full beginner walkthrough
- **FastAPI path params**: https://fastapi.tiangolo.com/tutorial/path-params/
- **FastAPI query params**: https://fastapi.tiangolo.com/tutorial/query-params/
- **Uvicorn**: https://www.uvicorn.org/ — ASGI server documentation
- **OpenAPI/Swagger**: https://swagger.io/specification/ — the API spec standard FastAPI uses
