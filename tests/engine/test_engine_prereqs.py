# tests/engine/test_engine_prereqs.py
from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Empty, Problem, ProblemKind, TerminalReason
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.model import (
    Node, Edge, ConditionGroup, ConditionAtom,
    NodeKind, EdgeType, Op, AtomType,
)


def _fixture_kg():
    """A 3-node prereq chain:
       npc:scur --requires--> access:scur-lair --requires--> quest:rfd (state=completed)
                                and             --requires--> skill:attack >= 50
    Goal closure of npc:scur = {access:scur-lair, quest:rfd, skill:attack}.
    """
    nodes = [
        Node(id="npc:scur", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius"),
        Node(id="access:scur-lair", kind=NodeKind.ACCESS, name="Scurrius' Lair", slug="scurrius-lair"),
        Node(id="quest:rfd", kind=NodeKind.QUEST, name="Recipe for Disaster", slug="recipe-for-disaster"),
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
    ]
    # cond groups (one per requires edge that carries a leaf)
    groups = {
        1: ConditionGroup(id=1, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.IS_UNLOCKED, ref_node="access:scur-lair"),
        ]),
        2: ConditionGroup(id=2, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:rfd",
                          data={"state": "completed"}),
        ]),
        3: ConditionGroup(id=3, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=50),
        ]),
    }
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src="npc:scur", dst="access:scur-lair", cond_group=1),
        Edge(id=2, type=EdgeType.REQUIRES, src="access:scur-lair", dst="quest:rfd", cond_group=2),
        Edge(id=3, type=EdgeType.REQUIRES, src="access:scur-lair", dst="skill:attack", cond_group=3),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


def _partial_state():
    """Attack done, quest + access not — so the goal is NOT yet satisfied."""
    return AccountState(
        mode="main",
        levels={"skill:attack": 70},
        quest_state={"quest:rfd": "not_started"},
        observable_families={"skill_level", "quest", "is_unlocked"},
    )


def test_prereqs_for_unknown_node_is_not_found():
    eng = Engine(_fixture_kg())
    res = eng.prereqs_for(_partial_state(), "npc:does-not-exist")
    assert isinstance(res, Problem)
    assert res.kind is ProblemKind.NOT_FOUND
    # D7: NOT_FOUND carries an EMPTY Refs; the id is named in the message, not refs.
    assert res.refs.nodes == {} and res.refs.mentions == {}
    assert "npc:does-not-exist" in res.message


def test_prereqs_for_none_state_is_missing_state():
    eng = Engine(_fixture_kg())
    res = eng.prereqs_for(None, "npc:scur")  # D4: only state is None is MISSING_STATE
    assert isinstance(res, Problem)
    assert res.kind is ProblemKind.MISSING_STATE
    assert "npc:scur" in res.refs.nodes


def test_prereqs_for_fresh_valid_account_is_not_missing_state():
    # D4: a fresh real account (mode set, empty progress, combat_level == 3) is VALID;
    # it must NOT be MISSING_STATE — it flows into the normal closure/plan path.
    eng = Engine(_fixture_kg())
    res = eng.prereqs_for(AccountState(mode="main"), "npc:scur")
    assert not (isinstance(res, Problem) and res.kind is ProblemKind.MISSING_STATE)


def _cyclic_kg():
    """A:requires->B, B:requires->A. find_cycles() must report it."""
    nodes = [
        Node(id="a", kind=NodeKind.ACCESS, name="A", slug="a"),
        Node(id="b", kind=NodeKind.ACCESS, name="B", slug="b"),
    ]
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src="a", dst="b"),
        Edge(id=2, type=EdgeType.REQUIRES, src="b", dst="a"),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups={})


def test_prereqs_for_cycle_is_unsatisfiable_cycle():
    eng = Engine(_cyclic_kg())
    state = AccountState(mode="main", done={"x"})  # non-empty so we pass the missing_state guard
    res = eng.prereqs_for(state, "a")
    assert isinstance(res, Problem)
    assert res.kind is ProblemKind.UNSATISFIABLE_CYCLE
    # cycle nodes are surfaced for the Advisor (§4: refs ⊆ touched nodes)
    assert "a" in res.refs.mentions or "a" in res.refs.nodes
