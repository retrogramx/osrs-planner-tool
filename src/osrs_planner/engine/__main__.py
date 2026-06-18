"""`python -m osrs_planner.engine` — prints the Scurrius plan for a fixture ironman.

A human-eyeball demo over the (70 Att AND 70 Str) OR full-Void worked example, so the
end-to-end story can be seen without reading pytest output. Not used by the web/advisor.

Adaptation note: explicit dst-based edges (3, 4) for Attack/Strength with cond_groups
(4, 5) are required so skill nodes appear in the requires_dag closure and show up in
prereqs_for steps. skill_level atoms are not ref-bearing, so without dst edges they only
appear as cond-tree leaves evaluated by is_unlocked, not as steps in prereqs_for.
"""
from osrs_planner.engine.kg.model import (
    Node, NodeKind, Edge, EdgeType, ConditionGroup, ConditionAtom, Op, AtomType,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Empty, Problem

SCURRIUS = "npc:7221"
ATTACK = "skill:attack"
STRENGTH = "skill:strength"
VOID = "gear_loadout:void"
HELM_MELEE = "item:11665"
VOID_TOP = "item:8839"
VOID_ROBE = "item:8840"
VOID_GLOVES = "item:8842"


def build_fixture() -> InMemoryKGStore:
    nodes = [
        Node(id=SCURRIUS, kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius"),
        Node(id=ATTACK, kind=NodeKind.SKILL, name="Attack", slug="attack"),
        Node(id=STRENGTH, kind=NodeKind.SKILL, name="Strength", slug="strength"),
        Node(id=VOID, kind=NodeKind.GEAR_LOADOUT, name="Full Void", slug="void"),
        Node(id=HELM_MELEE, kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm"),
        Node(id=VOID_TOP, kind=NodeKind.ITEM, name="Void knight top", slug="void-knight-top"),
        Node(id=VOID_ROBE, kind=NodeKind.ITEM, name="Void knight robe", slug="void-knight-robe"),
        Node(id=VOID_GLOVES, kind=NodeKind.ITEM, name="Void knight gloves", slug="void-knight-gloves"),
    ]
    groups = {
        1: ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3]),
        2: ConditionGroup(id=2, op=Op.AND, parent=1, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=ATTACK, threshold=70),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=STRENGTH, threshold=70),
        ]),
        3: ConditionGroup(id=3, op=Op.AND, parent=1, children=[
            ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node=VOID),
        ]),
        # dst-edge cond groups so Attack/Strength enter the requires_dag closure
        4: ConditionGroup(id=4, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=ATTACK, threshold=70),
        ]),
        5: ConditionGroup(id=5, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=STRENGTH, threshold=70),
        ]),
        10: ConditionGroup(id=10, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_MELEE, qty=1),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_TOP, qty=1),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_ROBE, qty=1),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_GLOVES, qty=1),
        ]),
    }
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src=SCURRIUS, dst=None, cond_group=1),
        # Explicit dst edges so skill nodes enter the requires_dag (skill_level not ref-bearing)
        Edge(id=3, type=EdgeType.REQUIRES, src=SCURRIUS, dst=ATTACK, cond_group=4),
        Edge(id=4, type=EdgeType.REQUIRES, src=SCURRIUS, dst=STRENGTH, cond_group=5),
        Edge(id=2, type=EdgeType.REQUIRES, src=VOID, dst=None, cond_group=10),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


def _print_unlock(engine: Engine, state: AccountState) -> None:
    res = engine.is_unlocked(state, SCURRIUS)
    if isinstance(res, Ok):
        print(f"is_unlocked: {res.card.status}")
        for b in res.card.blockers:
            print(f"  blocker: {b.name} [{b.reason}] ({b.status})")
    elif isinstance(res, Empty):
        print(f"is_unlocked: empty ({res.reason.value})")
    else:
        print(f"is_unlocked: problem ({res.kind.value}) {res.message}")


def _print_plan(engine: Engine, state: AccountState) -> None:
    res = engine.prereqs_for(state, SCURRIUS)
    if isinstance(res, Ok):
        print("prereqs_for (ordered):")
        for s in res.card.steps:
            print(f"  - {s.name}: {s.status} ({s.reason})")
    elif isinstance(res, Empty):
        print(f"prereqs_for: empty ({res.reason.value})")
    else:
        print(f"prereqs_for: problem ({res.kind.value}) {res.message}")


def _print_next(engine: Engine, state: AccountState) -> None:
    res = engine.next_steps(state, SCURRIUS)
    if isinstance(res, Ok):
        print("next_steps (frontier):")
        for s in res.card.steps:
            print(f"  - {s.name}: {s.status} ({s.reason})")
    elif isinstance(res, Empty):
        print(f"next_steps: empty ({res.reason.value})")
    else:
        print(f"next_steps: problem ({res.kind.value}) {res.message}")


def main() -> None:
    kg = build_fixture()
    engine = Engine(kg)
    iron = AccountState(
        mode="ironman",
        levels={ATTACK: 75, STRENGTH: 60},
        observable_families={"skill_level", "skill_xp", "item", "gear_loadout"},
    )
    print("=== Gilded Tome engine demo: Scurrius on an ironman (75 Att / 60 Str, no Void) ===")
    _print_unlock(engine, iron)
    _print_plan(engine, iron)
    _print_next(engine, iron)


if __name__ == "__main__":
    main()
