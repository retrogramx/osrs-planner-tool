import json
from pathlib import Path
from osrs_planner.models import Goal, Account
from osrs_planner.xp import xp_remaining, level_for_xp


GOALS_DIR = Path(__file__).parent / "goals"


def load_goal(goal_id: str) -> Goal:
    """Load a goal definition from a JSON file."""
    with open(GOALS_DIR / f"{goal_id}.json") as f:
        data = json.load(f)
    return Goal(**data)


def check_requirements(account: Account, goal: Goal):
    current_level = account.skills["agility"].level
    current_xp = account.skills["agility"].xp
    current_marks = 0
    marks_needed = goal.target_marks
    if current_marks == marks_needed:
        return f"Congratulations. Goal achieved!"
    return {
        "current_level": current_level,
        "current_xp": current_xp,
        "marks_needed": marks_needed - current_marks,
        "xp_remaining": xp_remaining(current_xp, 60),
        "levels_remaining": 60 - level_for_xp(current_xp)
    }


def generate_plan(account: Account, goal: Goal) -> list:
    current_level = account.skills["agility"].level
    current_xp = account.skills["agility"].xp
    current_marks = 0
    plan_steps = []
    warning = []
    last_task = None
    
    for task in goal.tasks:
        if current_level >= task.to_level:
            continue
        
        if task.combat_requirement and account.is_skiller:
            warning.append(f"⚠ Skipped: {task.name} (requires combat)")
            continue
        
        if current_level < task.from_level:
            gap_xp = xp_remaining(current_xp, task.from_level)
            gap_hours = gap_xp / last_task.xp_per_hour
            gap_marks = gap_hours * last_task.marks_per_hour
            plan_steps.append({
                "name": last_task.name + " (extended)",
                "from_level": round(current_level),
                "to_level": task.from_level,
                "xp_needed": round(gap_xp),
                "hours_left": round(gap_hours, 1),
                "current_marks": round(current_marks),
                "marks_earned": round(gap_marks)
            })
            current_level = task.from_level
            current_xp = current_xp + gap_xp
            current_marks = current_marks + gap_marks
            
        xp_needed = xp_remaining(current_xp, task.to_level)
        hours_left = xp_needed / task.xp_per_hour
        marks_earned = hours_left * task.marks_per_hour
        marks_remaining = goal.target_marks - current_marks
        
        if marks_earned > marks_remaining:
            marks_earned = marks_remaining
            hours_left = marks_earned / task.marks_per_hour
            xp_needed = hours_left * task.xp_per_hour
        plan_steps.append({
            "name": task.name,
            "from_level": current_level,
            "to_level": task.to_level,
            "xp_needed": round(xp_needed),
            "hours_left": round(hours_left, 1),
            "current_marks": round(current_marks),
            "marks_earned": round(marks_earned)
        })
        last_task = task
        current_level = task.to_level
        current_xp = current_xp + xp_needed
        current_marks = current_marks + marks_earned
        
        if current_marks >= 260:
            break
    return plan_steps, warning
