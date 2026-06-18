"""End-to-end: the (70 Att AND 70 Str) OR full-Void Scurrius goal on an ironman.

Builds the hand-authored KG fixture from kg-schema-v1.md's worked example and asserts
is_unlocked / prereqs_for / next_steps tell ONE coherent story.

Adaptation notes (plan vs. real engine):
- skill_level atoms are NOT ref-bearing (AtomType.SKILL_LEVEL not in _REF_BEARING_ATOMS),
  so skill nodes only enter the requires_dag via explicit dst-based edges.  The fixture
  therefore adds two dst-based edges (edges 3 & 4) for Attack/Strength with their own
  single-atom cond groups (4, 5) so the skill nodes appear in prereqs_for's closure.
- Empty(ALREADY_SATISFIED) requires ALL nodes in the closure to be individually satisfied.
  Because the OR has three helm nodes (11663/11664/11665) each individually checked, the
  "done" account must own ALL three helms (not just one) so every node in the topo order
  reads as satisfied.
"""
import pytest

from osrs_planner.engine.kg.model import (
    Node, NodeKind, Edge, EdgeType, ConditionGroup, ConditionAtom, Op, AtomType,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Empty, Problem, ProblemKind, TerminalReason


# ---- Node ids (kg-schema-v1.md worked example) ----
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


@pytest.fixture
def kg():
    """Scurrius requires (70 Att AND 70 Str) OR full-Void; Void composition = AND-of-slots.

    Edges 3 & 4 are explicit dst-based requires edges for Attack/Strength (with cond_groups
    4, 5) so the skill nodes enter the requires_dag closure and appear in prereqs_for steps.
    Groups 4 & 5 mirror the same skill_level thresholds as the OR-branch cond atoms.
    """
    nodes = [
        Node(id=SCURRIUS, kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius"),
        Node(id=ATTACK, kind=NodeKind.SKILL, name="Attack", slug="attack"),
        Node(id=STRENGTH, kind=NodeKind.SKILL, name="Strength", slug="strength"),
        Node(id=VOID, kind=NodeKind.GEAR_LOADOUT, name="Full Void", slug="void"),
        Node(id=HELM_MAGE, kind=NodeKind.ITEM, name="Void mage helm", slug="void-mage-helm"),
        Node(id=HELM_RANGE, kind=NodeKind.ITEM, name="Void ranger helm", slug="void-ranger-helm"),
        Node(id=HELM_MELEE, kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm"),
        Node(id=VOID_TOP, kind=NodeKind.ITEM, name="Void knight top", slug="void-knight-top"),
        Node(id=VOID_ROBE, kind=NodeKind.ITEM, name="Void knight robe", slug="void-knight-robe"),
        Node(id=VOID_GLOVES, kind=NodeKind.ITEM, name="Void knight gloves", slug="void-knight-gloves"),
    ]
    groups = {
        # Scurrius requires-tree: OR( AND(att,str), void )
        1: ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3]),
        2: ConditionGroup(id=2, op=Op.AND, parent=1, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=ATTACK, threshold=70),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=STRENGTH, threshold=70),
        ]),
        3: ConditionGroup(id=3, op=Op.AND, parent=1, children=[
            ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node=VOID),
        ]),
        # dst-edge cond groups for the skill nodes (mirror the OR-branch thresholds)
        4: ConditionGroup(id=4, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=ATTACK, threshold=70),
        ]),
        5: ConditionGroup(id=5, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=STRENGTH, threshold=70),
        ]),
        # Void composition: AND( OR(3 helms), top, robe, gloves )
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
        # Scurrius's requires edge: the constraint IS the tree (dst=None, cond_group=1)
        Edge(id=1, type=EdgeType.REQUIRES, src=SCURRIUS, dst=None, cond_group=1),
        # Explicit dst-based edges so Attack/Strength nodes enter the requires_dag closure
        # (skill_level atoms are not ref-bearing, so cond_dep edges are not projected for them)
        Edge(id=3, type=EdgeType.REQUIRES, src=SCURRIUS, dst=ATTACK, cond_group=4),
        Edge(id=4, type=EdgeType.REQUIRES, src=SCURRIUS, dst=STRENGTH, cond_group=5),
        # Void loadout composition: dst=None requires edge carrying the AND-of-slots tree (cond_group=10)
        Edge(id=2, type=EdgeType.REQUIRES, src=VOID, dst=None, cond_group=10),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


@pytest.fixture
def ironman():
    """75 Att / 60 Str, no Void. Bank plugin present so item absence reads as a real FALSE."""
    return AccountState(
        mode="ironman",
        levels={ATTACK: 75, STRENGTH: 60},
        observable_families={"skill_level", "skill_xp", "item", "gear_loadout"},
    )


def test_scurrius_is_locked_with_strength_blocker(kg, ironman):
    """Ironman is 10 levels short of the 70 Str branch and owns no Void: locked, not indeterminate."""
    engine = Engine(kg)
    res = engine.is_unlocked(ironman, SCURRIUS)

    assert isinstance(res, Ok)
    card = res.card
    assert card.node_id == SCURRIUS
    assert card.status == "locked"
    # the subject node is grounded in refs
    assert SCURRIUS in res.refs.nodes
    # the failing strength leaf is surfaced as a blocker, none are cant_verify
    blocker_reasons = {b.reason for b in card.blockers}
    assert "skill_level" in blocker_reasons
    assert all(b.status != "cant_verify" for b in card.blockers)
    strength_blocker = [b for b in card.blockers if b.node_id == STRENGTH]
    assert strength_blocker, "expected a Strength blocker step"
    assert strength_blocker[0].status == "satisfiable"


def test_scurrius_prereqs_are_ordered_and_account_typed(kg, ironman):
    """prereqs_for yields a Step per prereq with done/satisfiable status, ordered.

    The engine projects the full requires-closure: both skill AND Void-branch nodes appear.
    Attack 70 is met (75 >= 70) -> satisfied; Strength 70 is not (60 < 70) -> satisfiable.
    Void items are also in steps as satisfiable (no Void owned).
    """
    engine = Engine(kg)
    res = engine.prereqs_for(ironman, SCURRIUS)

    assert isinstance(res, Ok)
    steps = res.card.steps
    assert res.card.goal_id == SCURRIUS
    assert steps, "expected at least the stat prereqs"
    by_node = {s.node_id: s for s in steps}
    # Attack 70 is met (75) -> satisfied; Strength 70 is not (60) -> satisfiable
    assert ATTACK in by_node and by_node[ATTACK].status == "satisfied"
    assert STRENGTH in by_node and by_node[STRENGTH].status == "satisfiable"
    # every step's node is grounded
    for s in steps:
        if s.node_id is not None:
            assert s.node_id in res.refs.nodes


def test_scurrius_next_steps_is_the_doable_frontier(kg, ironman):
    """next_steps = the prereqs whose own prereqs are all satisfied (immediately doable)."""
    engine = Engine(kg)
    res = engine.next_steps(ironman, SCURRIUS)

    assert isinstance(res, Ok)
    frontier = {s.node_id for s in res.card.steps if s.status != "satisfied"}
    # Strength (a bare skill leaf, no sub-prereqs) is doable right now
    assert STRENGTH in frontier


def test_already_satisfied_goal_is_empty(kg):
    """An ironman with 70/70 AND all Void pieces is fully done -> Empty(ALREADY_SATISFIED).

    All three helm nodes (HELM_MAGE/HELM_RANGE/HELM_MELEE) must be owned because each node
    is individually checked by prereqs_for's all_done guard (the OR is evaluated per-node,
    not as a branch truth value). Any unowned item in the closure keeps the state as Ok.
    """
    done_iron = AccountState(
        mode="ironman",
        levels={ATTACK: 99, STRENGTH: 99},
        counts={
            HELM_MAGE: 1, HELM_RANGE: 1, HELM_MELEE: 1,
            VOID_TOP: 1, VOID_ROBE: 1, VOID_GLOVES: 1,
        },
        observable_families={"skill_level", "skill_xp", "item", "gear_loadout"},
    )
    engine = Engine(kg)

    unlocked = engine.is_unlocked(done_iron, SCURRIUS)
    assert isinstance(unlocked, Ok) and unlocked.card.status == "unlocked"

    prereqs = engine.prereqs_for(done_iron, SCURRIUS)
    assert isinstance(prereqs, Empty)
    assert prereqs.reason == TerminalReason.ALREADY_SATISFIED


def test_missing_node_is_a_problem(kg, ironman):
    engine = Engine(kg)
    res = engine.is_unlocked(ironman, "npc:does-not-exist")
    assert isinstance(res, Problem)
    assert res.kind == ProblemKind.NOT_FOUND


def test_coherent_story_across_three_reads(kg, ironman):
    """The three reads must agree: locked <=> has prereqs <=> Strength on the frontier."""
    engine = Engine(kg)
    unlocked = engine.is_unlocked(ironman, SCURRIUS)
    prereqs = engine.prereqs_for(ironman, SCURRIUS)
    nxt = engine.next_steps(ironman, SCURRIUS)

    assert isinstance(unlocked, Ok) and unlocked.card.status == "locked"
    assert isinstance(prereqs, Ok) and isinstance(nxt, Ok)

    # the locked blocker, the unsatisfied prereq, and the frontier all point at Strength
    locked_nodes = {b.node_id for b in unlocked.card.blockers}
    unmet_prereqs = {s.node_id for s in prereqs.card.steps if s.status == "satisfiable"}
    frontier = {s.node_id for s in nxt.card.steps if s.status != "satisfied"}
    assert STRENGTH in locked_nodes
    assert STRENGTH in unmet_prereqs
    assert STRENGTH in frontier

    # next_steps is a subset of prereqs_for (the same Step universe, filtered)
    assert frontier <= unmet_prereqs
