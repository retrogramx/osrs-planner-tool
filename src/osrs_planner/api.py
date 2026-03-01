from fastapi import FastAPI
from osrs_planner.hiscores import fetch_stats
from osrs_planner.planner import load_goal, generate_plan
from osrs_planner.models import AccountMode


app = FastAPI()


@app.get("/")
def root():
    """Start the server with: uvicorn osrs_planner.api:app --reload"""
    return {"message": "OSRS Planner API"}


@app.get("/accounts/{rsn}/stats")
def get_stats(rsn: str, mode: str = "normal"):
    """GET /accounts/{rsn}/stats?mode=ironman"""
    account = fetch_stats(rsn, AccountMode[mode])
    return account


@app.get("/accounts/{rsn}/plan/{goal_id}")
def get_plan(rsn: str, goal_id: str, mode: str = "normal", skiller: bool = False, pure: bool = False):
    account = fetch_stats(rsn, AccountMode[mode])
    account.is_skiller = skiller
    account.is_pure = pure
    goal = load_goal(goal_id)
    plan_steps, warnings = generate_plan(account, goal)
    return {
        "warnings": warnings,
        "plan": plan_steps
        }
