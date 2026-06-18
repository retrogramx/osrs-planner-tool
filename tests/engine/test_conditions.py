from osrs_planner.engine.kleene import Tri
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.model import (
    AtomType, Op, NodeKind, Node, ConditionAtom, ConditionGroup, Edge, EdgeType,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.conditions import evaluate, atom_satisfied


def _store(nodes=None, edges=None, groups=None):
    # Task 5's InMemoryKGStore expects groups as a dict[int, ConditionGroup];
    # callers pass a list[ConditionGroup], so index it by id here.
    return InMemoryKGStore(
        nodes=list(nodes or []),
        edges=list(edges or []),
        groups={g.id: g for g in (groups or [])},
    )


def test_skill_level_atom_true_false_and_absent_is_false():
    kg = _store(nodes=[Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack")])
    atom = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70)

    met = AccountState(mode="normal", levels={"skill:attack": 70})
    under = AccountState(mode="normal", levels={"skill:attack": 69})
    absent = AccountState(mode="normal")  # skill levels are observable -> absent means level 1 -> FALSE

    assert atom_satisfied(atom, met, kg) is Tri.TRUE
    assert atom_satisfied(atom, under, kg) is Tri.FALSE
    assert atom_satisfied(atom, absent, kg) is Tri.FALSE
