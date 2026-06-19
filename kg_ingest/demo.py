"""`python -m kg_ingest.demo` — human-eyeball end-to-end story over the REAL KG.

Loads the committed kg/*.json through JsonKGStore and prints is_unlocked /
prereqs_for / next_steps for each golden goal (spec §3 / K8). Visual sanity check,
not used by the web/advisor.
"""
from __future__ import annotations

import pathlib

from osrs_planner.engine.engine import Engine
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.result import Ok, Empty
from osrs_planner.engine.state import AccountState

KG_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "kg")

GOALS = [
    ("Dragon scimitar", "item:4587"),
    ("Barrows gloves", "item:7462"),
    ("Fairy rings", "access:fairy-rings"),
    ("Tzhaar-ket-om", "item:6528"),
    ("Voidwaker", "item:27690"),
    ("Full Infinity", "gear_loadout_goal:infinity"),
]

OBSERVABLE = {"skill_level", "skill_xp", "combat_level", "quest", "item",
              "achievement_diary", "combat_achievement", "is_unlocked",
              "gear_loadout", "kill_count", "account_type", "clue_scrolls",
              "combat_achievement_points"}


def _illustrative_account() -> AccountState:
    return AccountState(
        mode="main",
        levels={"skill:attack": 60, "skill:strength": 60},
        quest_state={"quest:monkey-madness-i": "completed"},
        counts={"item:4587": 1, "item:7462": 1, "item:6528": 1},
        observable_families=set(OBSERVABLE))


def _print_goal(engine: Engine, label: str, goal_id: str, state: AccountState) -> None:
    print(f"=== {label} ({goal_id}) ===")
    unlock = engine.is_unlocked(state, goal_id)
    if isinstance(unlock, Ok):
        print(f"  is_unlocked: {unlock.card.status}")
        for b in unlock.card.blockers:
            print(f"    blocker: {b.name} [{b.reason}] ({b.status})")
    elif isinstance(unlock, Empty):
        print(f"  is_unlocked: empty ({unlock.reason.value})")
    else:
        print(f"  is_unlocked: problem ({unlock.kind.value}) {unlock.message}")
    plan = engine.prereqs_for(state, goal_id)
    if isinstance(plan, Ok):
        print(f"  prereqs_for: {len(plan.card.steps)} steps")
    elif isinstance(plan, Empty):
        print(f"  prereqs_for: empty ({plan.reason.value})")
    else:
        print(f"  prereqs_for: problem ({plan.kind.value}) {plan.message}")
    nxt = engine.next_steps(state, goal_id)
    if isinstance(nxt, Ok):
        print(f"  next_steps: {len(nxt.card.steps)} on the frontier")
    elif isinstance(nxt, Empty):
        print(f"  next_steps: empty ({nxt.reason.value})")
    else:
        print(f"  next_steps: problem ({nxt.kind.value}) {nxt.message}")


def run_demo() -> None:
    engine = Engine(JsonKGStore.from_dir(KG_DIR))
    state = _illustrative_account()
    print("=== Gilded Tome KG demo: golden goals on a mid-game main ===")
    for label, goal_id in GOALS:
        _print_goal(engine, label, goal_id, state)


if __name__ == "__main__":
    run_demo()
