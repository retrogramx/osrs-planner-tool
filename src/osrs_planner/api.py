import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from osrs_planner.hiscores import fetch_stats, PlayerNotFoundError, HiscoresError
from osrs_planner.planner import load_goal, generate_plan
from osrs_planner.models import AccountMode
from osrs_planner.profile import build_profile


app = FastAPI()


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


@app.get("/accounts/{rsn}/profile")
def get_profile(rsn: str):
    try:
        return build_profile(rsn)
    except PlayerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Account '{rsn}' not found on Hiscores")
    except HiscoresError:
        raise HTTPException(status_code=502, detail="Hiscores is unreachable right now — try again")


_WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web")
app.mount("/", StaticFiles(directory=_WEB, html=True), name="web")
