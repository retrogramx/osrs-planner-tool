"""Engine.is_unlocked — verdict + blockers from Kleene evaluation (contract §3.1/§4/§6)."""
import pytest

from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Problem, ProblemKind
from osrs_planner.engine.cards import UnlockCard
from osrs_planner.engine.state import AccountState

# The Task 8 conftest.py exposes by fixture name:
#   scurrius_kg -> InMemoryKGStore with node npc:7221 carrying the
#                  (70 Att AND 70 Str) OR full-Void requires cond_group
#   fresh_main / iron_75atk_60str -> sample AccountStates (optional here;
#   these tests construct AccountState directly via the spine constructor).
# SCURRIUS is the goal node id under test.
SCURRIUS = "npc:7221"


def test_unlocked_main_meets_stat_branch(scurrius_kg):
    state = AccountState(
        mode="main",
        levels={"skill:attack": 75, "skill:strength": 75},
        observable_families={"skill_level"},  # levels are always observable (§6.4)
    )
    eng = Engine(scurrius_kg)
    res = eng.is_unlocked(state, SCURRIUS)

    assert isinstance(res, Ok)
    assert isinstance(res.card, UnlockCard)
    assert res.card.node_id == SCURRIUS
    assert res.card.status == "unlocked"
    assert res.card.blockers == []
    # grounding leash (§7.4): the subject node is in refs.nodes
    assert SCURRIUS in res.refs.nodes
