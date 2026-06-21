# src/osrs_planner/profile.py
"""The Profile contract + assembly: search a player -> mirror (skills) + one
goal's engine-computed status. Composes existing bricks per request. The single
seam every consumer (API, future plugin) hangs off."""
from __future__ import annotations

import os
from pydantic import BaseModel, Field

from osrs_planner.account.detect import detect_account_type
from osrs_planner.account.temple import fetch_collection_log
from osrs_planner.hiscores import fetch_stats
from osrs_planner.engine.engine import Engine
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.result import Ok, Empty

# A skill-gated KG goal (blockers are observable skill levels). Confirmed/tuned in Task 5.
DEFAULT_GOAL_NODE = "quest:cold-war"

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_KG = JsonKGStore.from_dir(os.path.join(_REPO, "kg"))   # loaded once at import

class SkillEntry(BaseModel):
    name: str
    level: int
    xp: int

class GoalStep(BaseModel):
    label: str                 # "Agility", "Recipe for Disaster", ...
    status: str                # "met" | "unmet" | "unknown"

class GoalStatus(BaseModel):
    node_id: str
    label: str                 # the goal's display name
    status: str                # "met" | "blocked" | "unknown"
    steps: list[GoalStep] = Field(default_factory=list)

class Profile(BaseModel):
    rsn: str
    account_type: str          # AccountMode.name: "normal" | "ironman" | "hardcore_ironman" | "ultimate_ironman"
    total_level: int
    skills: list[SkillEntry]
    goals: list[GoalStatus]
    clog_synced: bool = True

_STEP_STATUS = {"satisfied": "met", "satisfiable": "unmet",
                "cant_verify": "unknown", "impossible_for_mode": "unmet"}
_CARD_STATUS = {"unlocked": "met", "locked": "blocked", "indeterminate": "unknown"}

def _goal_label(goal_id: str) -> str:
    try:
        return _KG.get_node(goal_id).name
    except Exception:
        return goal_id

def _goal_status(goal_id: str, result) -> GoalStatus:
    label = _goal_label(goal_id)
    if isinstance(result, Ok):
        card = result.card
        steps = [GoalStep(label=b.name, status=_STEP_STATUS.get(b.status, "unknown"))
                 for b in card.blockers]
        return GoalStatus(node_id=goal_id, label=label, status=_CARD_STATUS[card.status], steps=steps)
    if isinstance(result, Empty):
        return GoalStatus(node_id=goal_id, label=label, status="met", steps=[])
    # Problem: surface the message, mark unknown
    return GoalStatus(node_id=goal_id, label=label, status="unknown",
                      steps=[GoalStep(label=getattr(result, "message", "could not evaluate"), status="unknown")])

def build_profile(rsn: str, goal_id: str = DEFAULT_GOAL_NODE) -> Profile:
    mode = detect_account_type(rsn)                       # AccountMode; raises PlayerNotFoundError if nowhere
    account = fetch_stats(rsn, mode)                      # Account
    try:
        clog = fetch_collection_log(rsn)["obtained"]
        clog_synced = True
    except Exception:
        clog, clog_synced = set(), False
    levels = {f"skill:{n.lower()}": s.level for n, s in account.skills.items() if n != "Overall"}
    xp = {f"skill:{n.lower()}": s.xp for n, s in account.skills.items() if n != "Overall"}
    state = AccountState(mode=mode.name, levels=levels, xp=xp,
                         clog_obtained=clog, observable_families={"skill_level", "skill_xp"})
    result = Engine(_KG).is_unlocked(state, goal_id)
    total = account.skills["Overall"].level if "Overall" in account.skills \
        else sum(s.level for n, s in account.skills.items())
    skills = [SkillEntry(name=n, level=s.level, xp=s.xp)
              for n, s in account.skills.items() if n != "Overall"]
    return Profile(rsn=rsn, account_type=mode.name, total_level=total,
                   skills=skills, goals=[_goal_status(goal_id, result)], clog_synced=clog_synced)
