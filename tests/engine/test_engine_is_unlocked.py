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


def test_locked_ironman_or_tree_surfaces_strength_blocker(scurrius_kg):
    state = AccountState(
        mode="ironman",
        levels={"skill:attack": 75, "skill:strength": 60},
        counts={},  # no Void
        observable_families={"skill_level", "item"},  # both real-FALSE here
    )
    eng = Engine(scurrius_kg)
    res = eng.is_unlocked(state, SCURRIUS)

    assert isinstance(res, Ok)
    assert res.card.status == "locked"
    assert res.card.blockers, "a locked node must surface blockers"

    # The cheapest branch (train Strength to 70) is present as a failing skill_level leaf.
    strength_blockers = [
        b
        for b in res.card.blockers
        if b.node_id == "skill:strength" and b.reason == "skill_level"
    ]
    assert strength_blockers, "expected a Strength skill_level blocker"
    sb = strength_blockers[0]
    assert sb.status == "satisfiable"  # not cant_verify, not satisfied
    assert "skill:strength" in res.refs.nodes  # blocker node entered refs (§7.4)

    # No blocker is falsely flagged cant_verify when the family is observable.
    assert all(b.status != "cant_verify" for b in res.card.blockers)


def test_is_unlocked_folds_all_requires_edges(scurrius_kg):
    # D5: Scurrius has TWO requires edges (the access:scurrius-lair prereq edge AND
    # the flagship cond_group edge). The engine must read and fold BOTH, not just one.
    from osrs_planner.engine.kg.model import EdgeType
    req_edges = [
        e for e in scurrius_kg.edges
        if e.type is EdgeType.REQUIRES and e.src == SCURRIUS
    ]
    assert len(req_edges) == 2, "fixture Scurrius must carry two requires edges (D5)"
    # both edges satisfied for the 70/70 main -> the AND-of-edges folds to unlocked
    state = AccountState(
        mode="main",
        levels={"skill:attack": 75, "skill:strength": 75},
        observable_families={"skill_level"},
    )
    res = Engine(scurrius_kg).is_unlocked(state, SCURRIUS)
    assert isinstance(res, Ok)
    assert res.card.status == "unlocked"


def test_unobservable_atom_indeterminate_not_false_locked(scurrius_kg):
    # Strength absent AND not observable AND not asserted -> UNKNOWN (§6), not FALSE.
    state = AccountState(
        mode="main",
        levels={"skill:attack": 75},   # strength deliberately absent
        counts={},                      # no Void -> that branch FALSE
        observable_families={"item"},   # 'skill_level' is NOT observable here
    )
    eng = Engine(scurrius_kg)
    res = eng.is_unlocked(state, SCURRIUS)

    assert isinstance(res, Ok)
    # The whole point of §6: an unverifiable input must NOT read as locked.
    assert res.card.status == "indeterminate"
    assert res.card.status != "locked"

    cant_verify = [b for b in res.card.blockers if b.status == "cant_verify"]
    assert cant_verify, "an UNKNOWN leaf must surface a cant_verify blocker"
    assert any(b.node_id == "skill:strength" for b in cant_verify)
    assert "skill:strength" in res.refs.nodes


def test_missing_node_returns_problem_not_found(scurrius_kg):
    state = AccountState(mode="main", levels={"skill:attack": 75})
    eng = Engine(scurrius_kg)
    res = eng.is_unlocked(state, "npc:does-not-exist")

    assert isinstance(res, Problem)
    assert res.kind == ProblemKind.NOT_FOUND
    # D7: NOT_FOUND carries an EMPTY Refs; the unknown id is named in the message,
    # NOT inside refs.nodes (an unknown id is not a node, so not a NodeRef).
    assert res.refs.nodes == {}
    assert "npc:does-not-exist" in res.message


def test_none_state_returns_problem_missing_state(scurrius_kg):
    eng = Engine(scurrius_kg)
    res = eng.is_unlocked(None, SCURRIUS)  # D4: only state is None is MISSING_STATE

    assert isinstance(res, Problem)
    assert res.kind == ProblemKind.MISSING_STATE
    assert SCURRIUS in res.refs.nodes  # the subject is named even on failure (§7.4)


def test_fresh_valid_account_is_not_missing_state(scurrius_kg):
    # D4: a fresh real account (mode set, empty progress, combat_level == 3) is VALID,
    # not missing — its absent values resolve via the Kleene rule, never MISSING_STATE.
    fresh = AccountState(mode="main")
    res = Engine(scurrius_kg).is_unlocked(fresh, SCURRIUS)
    assert isinstance(res, Ok)
    assert res.card.status in {"locked", "indeterminate"}  # never MISSING_STATE
