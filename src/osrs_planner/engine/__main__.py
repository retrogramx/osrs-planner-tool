"""`python -m osrs_planner.engine` — prints the Scurrius plan for a fixture ironman.

A human-eyeball demo over the (70 Att AND 70 Str) OR full-Void worked example, so the
end-to-end story can be seen without reading pytest output. Not used by the web/advisor.

The fixture uses the CANONICAL OR model (no hard skill edges).  skill_level atoms are
not ref-bearing, so Attack/Strength appear as cond-tree leaf BLOCKERS in is_unlocked
but NOT as Steps in prereqs_for/next_steps.  The step universe is the Void branch:
gear_loadout:void + its six item leaves + access:scurrius-lair (unconditionally satisfied).

Expected output for a 75 Att / 60 Str ironman with no Void:
  is_unlocked: locked
    blocker: Strength [skill_level] (satisfiable)
    blocker: Full Void Knight [gear_loadout] (satisfiable)
  prereqs_for: 8 steps (6 void items + loadout + access)
  next_steps: 6 void item leaves (frontier — no sub-prereqs)
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
HELM_MAGE = "item:11663"
HELM_RANGE = "item:11664"
HELM_MELEE = "item:11665"
VOID_TOP = "item:8839"
VOID_ROBE = "item:8840"
VOID_GLOVES = "item:8842"
ACCESS = "access:scurrius-lair"


def build_fixture() -> InMemoryKGStore:
    """Inline demo fixture — same OR structure as the canonical test fixture (build_store).

    No hard skill edges: Attack/Strength are cond-tree leaves only, NOT dst-based
    requires edges, so they appear as blockers (is_unlocked) but NOT as steps
    (prereqs_for/next_steps).  The Void branch items are the actionable steps.
    """
    nodes = [
        Node(id=SCURRIUS, kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius"),
        Node(id=ATTACK, kind=NodeKind.SKILL, name="Attack", slug="attack"),
        Node(id=STRENGTH, kind=NodeKind.SKILL, name="Strength", slug="strength"),
        Node(id=VOID, kind=NodeKind.GEAR_LOADOUT, name="Full Void Knight", slug="void"),
        Node(id=HELM_MAGE, kind=NodeKind.ITEM, name="Void mage helm", slug="void-mage-helm"),
        Node(id=HELM_RANGE, kind=NodeKind.ITEM, name="Void ranger helm", slug="void-ranger-helm"),
        Node(id=HELM_MELEE, kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm"),
        Node(id=VOID_TOP, kind=NodeKind.ITEM, name="Void knight top", slug="void-knight-top"),
        Node(id=VOID_ROBE, kind=NodeKind.ITEM, name="Void knight robe", slug="void-knight-robe"),
        Node(id=VOID_GLOVES, kind=NodeKind.ITEM, name="Void knight gloves",
             slug="void-knight-gloves"),
        Node(id=ACCESS, kind=NodeKind.ACCESS, name="Scurrius Lair Access",
             slug="scurrius-lair"),
    ]
    groups = {
        # Scurrius flagship: OR( AND(70 Att, 70 Str), gear_loadout:void )
        1: ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3]),
        2: ConditionGroup(id=2, op=Op.AND, parent=1, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=ATTACK, threshold=70),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=STRENGTH, threshold=70),
        ]),
        3: ConditionGroup(id=3, op=Op.AND, parent=1, children=[
            ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node=VOID),
        ]),
        # gear_loadout:void composition: AND( OR(3 helms), top, robe, gloves )
        10: ConditionGroup(id=10, op=Op.AND, parent=None, children=[
            11,
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_TOP, qty=1),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_ROBE, qty=1),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_GLOVES, qty=1),
        ]),
        11: ConditionGroup(id=11, op=Op.OR, parent=10, children=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_MAGE, qty=1),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_RANGE, qty=1),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_MELEE, qty=1),
        ]),
    }
    edges = [
        # Scurrius flagship condition (dst=None: the constraint IS the tree)
        Edge(id=1, type=EdgeType.REQUIRES, src=SCURRIUS, dst=None, cond_group=1),
        # Scurrius also requires lair access (dst-only, no cond_group)
        Edge(id=2, type=EdgeType.REQUIRES, src=SCURRIUS, dst=ACCESS, cond_group=None),
        # gear_loadout:void composition
        Edge(id=3, type=EdgeType.REQUIRES, src=VOID, dst=None, cond_group=10),
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
