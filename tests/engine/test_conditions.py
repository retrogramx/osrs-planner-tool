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


def test_skill_xp_atom():
    kg = _store(nodes=[Node(id="skill:slayer", kind=NodeKind.SKILL, name="Slayer", slug="slayer")])
    atom = ConditionAtom(atom_type=AtomType.SKILL_XP, ref_node="skill:slayer", threshold=100_000)
    assert atom_satisfied(atom, AccountState(mode="normal", xp={"skill:slayer": 100_000}), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal", xp={"skill:slayer": 99_999}), kg) is Tri.FALSE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE  # absent xp = 0


def test_combat_level_atom_reads_derived_scalar():
    kg = _store()
    atom = ConditionAtom(atom_type=AtomType.COMBAT_LEVEL, threshold=100)
    assert atom_satisfied(atom, AccountState(mode="normal", combat_level=100), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal", combat_level=99), kg) is Tri.FALSE
    # default combat_level=3 always exists -> never UNKNOWN
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_quest_points_and_ca_points_atoms():
    kg = _store()
    qp = ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)
    cap = ConditionAtom(atom_type=AtomType.COMBAT_ACHIEVEMENT_POINTS, threshold=500)
    assert atom_satisfied(qp, AccountState(mode="normal", qp=32), kg) is Tri.TRUE
    assert atom_satisfied(qp, AccountState(mode="normal", qp=31), kg) is Tri.FALSE
    assert atom_satisfied(cap, AccountState(mode="normal", ca_points=500), kg) is Tri.TRUE
    assert atom_satisfied(cap, AccountState(mode="normal", ca_points=499), kg) is Tri.FALSE


def test_item_atom_qty_observable_absent_is_false():
    kg = _store(nodes=[Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top")])
    atom = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839", qty=2)
    assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8839": 2}), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8839": 1}), kg) is Tri.FALSE
    # items are observable (bank feed) -> absent = 0 owned = FALSE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_item_atom_qty_defaults_to_one():
    kg = _store(nodes=[Node(id="item:8842", kind=NodeKind.ITEM, name="Void gloves", slug="void-gloves")])
    atom = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8842")  # qty None -> 1
    assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8842": 1}), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_account_type_atom_matches_mode():
    kg = _store()
    atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "ironman"})
    assert atom_satisfied(atom, AccountState(mode="ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_is_unlocked_atom_done_membership_and_unobservable_absent_is_unknown():
    kg = _store(nodes=[Node(id="access:fairy-rings", kind=NodeKind.ACCESS,
                            name="Fairy rings", slug="fairy-rings")])
    atom = ConditionAtom(atom_type=AtomType.IS_UNLOCKED, ref_node="access:fairy-rings")

    has = AccountState(mode="normal", done={"access:fairy-rings"})
    # access is engine-derived/unobservable; absent + not asserted -> UNKNOWN (not a false locked)
    absent = AccountState(mode="normal")
    # but if the family IS observed, absence is a real FALSE
    observed = AccountState(mode="normal", observable_families={"is_unlocked"})

    assert atom_satisfied(atom, has, kg) is Tri.TRUE
    assert atom_satisfied(atom, absent, kg) is Tri.UNKNOWN
    assert atom_satisfied(atom, observed, kg) is Tri.FALSE


def test_combat_achievement_atom_binary_in_done():
    kg = _store(nodes=[Node(id="ca:scurrius:smashing-the-rat", kind=NodeKind.COMBAT_ACHIEVEMENT,
                            name="Smashing the Rat", slug="scurrius:smashing-the-rat")])
    atom = ConditionAtom(atom_type=AtomType.COMBAT_ACHIEVEMENT, ref_node="ca:scurrius:smashing-the-rat")
    done = AccountState(mode="normal", done={"ca:scurrius:smashing-the-rat"})
    absent = AccountState(mode="normal")  # per-task CAs unobservable on Hiscores -> UNKNOWN
    observed = AccountState(mode="normal", observable_families={"combat_achievement"})
    assert atom_satisfied(atom, done, kg) is Tri.TRUE
    assert atom_satisfied(atom, absent, kg) is Tri.UNKNOWN
    assert atom_satisfied(atom, observed, kg) is Tri.FALSE
