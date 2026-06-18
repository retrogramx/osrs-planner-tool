import pytest

from osrs_planner.engine.engine import Engine
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.model import (
    Node, Edge, ConditionGroup, ConditionAtom,
    NodeKind, EdgeType, Op, AtomType,
)
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.result import Ok, Empty, Problem, ProblemKind, TerminalReason
from osrs_planner.engine.cards import PlanCard


def _two_layer_kg():
    """goal --requires--> {attack>=40, quest:sub}; quest:sub --requires--> cooking>=20.

    skill:attack and skill:cooking are DAG nodes reached via dst edges (the same
    pattern as test_engine_prereqs._fixture_kg). skill_level atoms carry the
    threshold; the dst edge projects the node into the requires_dag closure so
    topo_order/descendants can reach it.
    """
    nodes = [
        Node(id="quest:goal", kind=NodeKind.QUEST, name="The Goal", slug="goal"),
        Node(id="quest:sub", kind=NodeKind.QUEST, name="The Sub-Quest", slug="sub"),
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
        Node(id="skill:cooking", kind=NodeKind.SKILL, name="Cooking", slug="cooking"),
    ]
    # cond groups carry the scalar constraints
    groups = {
        # goal requires: attack>=40 (cond) via dst edge, and quest:sub (cond) via dst edge
        1: ConditionGroup(
            id=1, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=40),
            ],
        ),
        2: ConditionGroup(
            id=2, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:sub", data={"state": "completed"}),
            ],
        ),
        # quest:sub requires: cooking>=20 (cond) via dst edge
        3: ConditionGroup(
            id=3, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:cooking", threshold=20),
            ],
        ),
    }
    edges = [
        # goal --requires--> skill:attack (with skill_level>=40 cond)
        Edge(id=1, type=EdgeType.REQUIRES, src="quest:goal", dst="skill:attack", cond_group=1),
        # goal --requires--> quest:sub (with quest completed cond)
        Edge(id=2, type=EdgeType.REQUIRES, src="quest:goal", dst="quest:sub", cond_group=2),
        # quest:sub --requires--> skill:cooking (with skill_level>=20 cond)
        Edge(id=3, type=EdgeType.REQUIRES, src="quest:sub", dst="skill:cooking", cond_group=3),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


def _state(**kw):
    # observable skills so absent levels read as FALSE (real), not UNKNOWN
    base = dict(
        mode="main",
        levels={"skill:cooking": 20},
        observable_families={"skill_level", "skill_xp", "quest"},
    )
    base.update(kw)
    return AccountState(**base)


def test_next_steps_returns_only_actionable_frontier():
    kg = _two_layer_kg()
    eng = Engine(kg)
    # Cooking 20 met; Attack not trained; sub not started.
    state = _state()

    res = eng.next_steps(state, "quest:goal")

    assert isinstance(res, Ok)
    card = res.card
    assert isinstance(card, PlanCard)
    assert card.goal_id == "quest:goal"
    frontier_ids = {s.node_id for s in card.steps}
    # attack (no prereqs) and sub (its only prereq, cooking, is done) are actionable;
    # cooking is already satisfied so it is NOT surfaced as a next step.
    assert frontier_ids == {"skill:attack", "quest:sub"}
    assert all(s.status == "satisfiable" for s in card.steps)

    # D8: next_steps must REUSE prereqs_for's Step instances (not rebuild them),
    # so the two reads can never drift. The frontier is a strict subset of the full plan:
    # every frontier step must appear (by value) in prereqs_for's output, never computed
    # independently. We verify this with equality (same field values), not Python object
    # identity — identity across two separate calls is impossible without caching, and the
    # plan's `is` assertion was a spec bug (plan note, non-blocking).
    plan_steps = {s.node_id: s for s in eng.prereqs_for(state, "quest:goal").card.steps}
    assert all(s == plan_steps[s.node_id] for s in card.steps)


def _gated_kg():
    """goal --req--> sub ; sub --req--> quest:gate (completed) ; gate has no prereqs."""
    nodes = [
        Node(id="quest:goal", kind=NodeKind.QUEST, name="The Goal", slug="goal"),
        Node(id="quest:sub", kind=NodeKind.QUEST, name="The Sub-Quest", slug="sub"),
        Node(id="quest:gate", kind=NodeKind.QUEST, name="The Gate Quest", slug="gate"),
    ]
    groups = {
        1: ConditionGroup(
            id=1, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:sub", data={"state": "completed"}),
            ],
        ),
        2: ConditionGroup(
            id=2, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:gate", data={"state": "completed"}),
            ],
        ),
    }
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src="quest:goal", dst=None, cond_group=1),
        Edge(id=2, type=EdgeType.REQUIRES, src="quest:sub", dst=None, cond_group=2),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


def test_next_steps_empty_no_frontier_when_blocked_by_unverifiable_gate():
    kg = _gated_kg()
    eng = Engine(kg)
    # quest family NOT observable and nothing asserted -> quest:gate is UNKNOWN (cant_verify),
    # so quest:sub's prereq is unmet and nothing is immediately doable.
    state = AccountState(mode="main", levels={"skill:dummy": 1})

    res = eng.next_steps(state, "quest:goal")

    assert isinstance(res, Empty)
    assert res.reason == TerminalReason.NO_FRONTIER
    assert res.status == "ok"
    # the subject closure is still named so the Advisor can hedge (§7.4 refs leash)
    assert "quest:sub" in res.refs.nodes or "quest:gate" in res.refs.nodes


def test_next_steps_already_satisfied_goal_is_empty():
    kg = _two_layer_kg()
    eng = Engine(kg)
    # everything the goal needs is met: 40 Attack, 20 Cooking, sub completed.
    state = _state(
        levels={"skill:attack": 40, "skill:cooking": 20},
        quest_state={"quest:sub": "completed"},
    )

    res = eng.next_steps(state, "quest:goal")

    assert isinstance(res, Empty)
    assert res.reason == TerminalReason.ALREADY_SATISFIED


def test_next_steps_unknown_goal_is_problem_not_found():
    kg = _two_layer_kg()
    eng = Engine(kg)
    state = _state()

    res = eng.next_steps(state, "quest:does-not-exist")

    assert isinstance(res, Problem)
    assert res.kind == ProblemKind.NOT_FOUND
    # D7: forwarded verbatim from prereqs_for -> empty Refs, id in the message only.
    assert res.refs.nodes == {} and res.refs.mentions == {}
    assert "quest:does-not-exist" in res.message
