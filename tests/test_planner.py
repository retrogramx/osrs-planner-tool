from osrs_planner.models import Account, AccountMode, Skill
from osrs_planner.planner import load_goal, generate_plan


def test_level_1_agility():
    account = Account(
    rsn="TestPlayer",
    mode=AccountMode.normal,
    skills={"agility": Skill(name="Agility", level=1, xp=0)}
    )
    goal = load_goal("full_graceful")
    plan, warnings = generate_plan(account, goal)
    assert len(plan) == 7


def test_level_30_agility():
    account = Account(
    rsn="TestPlayer2",
    mode=AccountMode.normal,
    skills={"agility": Skill(name="Agility", level=30, xp=13363)}
    )
    goal = load_goal("full_graceful")
    plan, warnings = generate_plan(account, goal)
    assert plan[0]["from_level"] == 30
    assert len(plan) == 5


def test_skiller():
    account = Account(
    rsn="TestPlayer3",
    mode=AccountMode.normal,
    skills={"agility": Skill(name="Agility", level=1, xp=0)},
    is_skiller = True
    )
    goal = load_goal("full_graceful")
    plan, warnings = generate_plan(account, goal)
    assert len(plan) == 7
    for step in plan:
        assert "Canifis" not in step["name"]
    assert len(warnings) == 1
    assert "Canifis" in warnings[0]
