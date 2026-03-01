# Lesson 5.1: Hello FastAPI

## Files
- `pyproject.toml` — added `fastapi` and `uvicorn` dependencies
- `src/osrs_planner/api.py` — created with root endpoint

---

## What I Learned
- What a web framework does — turns Python functions into web endpoints
- How to create a FastAPI application
- What decorators are (`@app.get("/")`)
- How to run a development server with uvicorn
- Swagger UI — free auto-generated API documentation

## Key Concepts

### FastAPI Basics
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "OSRS Planner API"}
```
- `app = FastAPI()` — creates the web application
- `@app.get("/")` — a **decorator** that says "when someone visits `/`, run this function"
- Return a dictionary → FastAPI converts it to JSON automatically

### Two New Dependencies
- **FastAPI** — the web framework
- **uvicorn** — the server that runs it
- Both are third-party → add to `pyproject.toml` dependencies

### Running the Server
```bash
uvicorn osrs_planner.api:app --reload
```
- `osrs_planner.api` — the module path to your file
- `:app` — the FastAPI instance name
- `--reload` — auto-restart when you save changes (dev only)

### Swagger UI
- Visit `http://localhost:8000/docs` to see auto-generated API documentation
- Can test endpoints directly from the browser with "Try it out"
- Updates automatically as you add more endpoints

## References
- **FastAPI**: https://fastapi.tiangolo.com/tutorial/first-steps/ — getting started
- **Uvicorn**: https://www.uvicorn.org/ — ASGI server
- **Decorators**: https://docs.python.org/3/glossary.html#term-decorator — what `@` means in Python
- **Swagger UI**: https://swagger.io/tools/swagger-ui/ — interactive API documentation
