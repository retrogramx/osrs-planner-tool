"""End-to-end: the (70 Att AND 70 Str) OR full-Void Scurrius goal on an ironman.

Uses the canonical KG fixture from kg-schema-v1.md's worked example (build_store).
Asserts is_unlocked / prereqs_for / next_steps tell ONE coherent story, modelling
the TRUE OR semantics — no hard skill edges.

Design notes:
- skill_level atoms are NOT ref-bearing (AtomType.SKILL_LEVEL not in _REF_BEARING_ATOMS),
  so skill nodes do NOT enter the requires_dag closure.  Attack/Strength are cond-tree
  leaves evaluated by is_unlocked (where they appear as BLOCKERS on the failing branch)
  but are NOT Steps in prereqs_for/next_steps.
- The Void branch items (item:*) and gear_loadout:void ARE ref-bearing dst-side nodes:
  they appear as both STEPS in prereqs_for and candidates on the next_steps frontier.
- access:scurrius-lair has no requires edges of its own -> unconditionally "satisfied";
  it appears as a Step but is already met for every account.
- Empty(ALREADY_SATISFIED) fires only when every node in the topo closure is
  individually satisfied.  Because the closure contains all three helm alternatives
  (item:11663/11664/11665), every account presented to prereqs_for must own all three
  helms (the OR is evaluated per-node, not as a branch truth value).
"""

import pytest

from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Empty, Problem, ProblemKind, TerminalReason
from osrs_planner.engine.state import AccountState
from tests.engine.fixtures.kg_fixture import (
    build_store,
    iron_75atk_60str_novoid,
    main_full_void,
)

# Canonical node ids (kg-schema-v1.md worked example)
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

VOID_ITEM_LEAVES = {HELM_MAGE, HELM_RANGE, HELM_MELEE, VOID_TOP, VOID_ROBE, VOID_GLOVES}


@pytest.fixture
def kg():
    """Canonical KG store: OR(AND(70 Att, 70 Str), gear_loadout:void) + access edge."""
    return build_store()  # local alias of kg_fixture.build_store / conftest scurrius_kg


@pytest.fixture
def ironman():
    """75 Att / 60 Str, no Void.  Observable so item absence reads as a real FALSE."""
    return iron_75atk_60str_novoid()  # local alias of kg_fixture.iron_75atk_60str_novoid


def test_scurrius_is_locked_with_single_strength_blocker(kg, ironman):
    """Ironman is 10 levels short of the 70 Str branch and owns no Void: locked.

    Exactly ONE Strength blocker surfaces (no duplicate from a mis-modelled hard edge).
    A Full Void Knight gear_loadout blocker also surfaces.
    No cant_verify blockers — item absence is observable.
    """
    engine = Engine(kg)
    res = engine.is_unlocked(ironman, SCURRIUS)

    assert isinstance(res, Ok)
    card = res.card
    assert card.node_id == SCURRIUS
    assert card.status == "locked"
    # the subject node is grounded in refs
    assert SCURRIUS in res.refs.nodes
    # no cant_verify blockers — iron_75atk_60str_novoid has observable_families set
    assert all(b.status != "cant_verify" for b in card.blockers)

    strength_blockers = [b for b in card.blockers if b.node_id == STRENGTH]
    assert len(strength_blockers) == 1, (
        f"expected exactly ONE Strength blocker, got {len(strength_blockers)}: "
        f"{[b.name for b in strength_blockers]}"
    )
    assert strength_blockers[0].status == "satisfiable"
    assert strength_blockers[0].reason == "skill_level"

    void_blockers = [b for b in card.blockers if b.node_id == VOID]
    assert void_blockers, "expected a Full Void Knight gear_loadout blocker"
    assert void_blockers[0].status == "satisfiable"


def test_scurrius_prereqs_are_void_branch_not_skill_nodes(kg, ironman):
    """prereqs_for yields Void-branch nodes + access as Steps; skills are NOT steps.

    The OR's stats branch contributes cond-tree leaves only (evaluated by is_unlocked),
    not separate requires-dag nodes.  The step universe is:
      - 6 void item leaves: satisfiable (none owned)
      - gear_loadout:void: satisfiable (incomplete)
      - access:scurrius-lair: satisfied (no requires edges of its own)
    Attack and Strength MUST NOT appear as step node-ids.
    """
    engine = Engine(kg)
    res = engine.prereqs_for(ironman, SCURRIUS)

    assert isinstance(res, Ok)
    steps = res.card.steps
    assert res.card.goal_id == SCURRIUS
    assert steps, "expected prereq steps for the Void branch + access"

    by_node = {s.node_id: s for s in steps}

    # Skills are NOT steps (they are cond-tree leaves, not ref-bearing dst nodes)
    assert ATTACK not in by_node, "Attack must not be a prereq step node"
    assert STRENGTH not in by_node, "Strength must not be a prereq step node"

    # Void item leaves ARE steps (ref-bearing via gear_loadout composition edges)
    for item_id in VOID_ITEM_LEAVES:
        assert item_id in by_node, f"expected {item_id} as a prereq step"
        assert by_node[item_id].status == "satisfiable"

    # gear_loadout:void is a step
    assert VOID in by_node, "gear_loadout:void must be a prereq step"
    assert by_node[VOID].status == "satisfiable"

    # access:scurrius-lair is a step (dst edge from npc:7221), unconditionally satisfied
    assert ACCESS in by_node, "access:scurrius-lair must be a prereq step"
    assert by_node[ACCESS].status == "satisfied"

    # every step's node is grounded in refs
    for s in steps:
        if s.node_id is not None:
            assert s.node_id in res.refs.nodes


def test_scurrius_next_steps_is_void_item_frontier(kg, ironman):
    """next_steps = the Void item leaves (immediately doable: no sub-prereqs of their own)."""
    engine = Engine(kg)
    res = engine.next_steps(ironman, SCURRIUS)

    assert isinstance(res, Ok)
    frontier_ids = {s.node_id for s in res.card.steps}

    # At least one Void item leaf is on the frontier
    assert frontier_ids & VOID_ITEM_LEAVES, (
        f"expected at least one Void item leaf in frontier, got {frontier_ids}"
    )

    # gear_loadout:void is NOT on the frontier (it depends on the item leaves)
    assert VOID not in frontier_ids, "gear_loadout:void should not be on the frontier"

    # frontier is a subset of the unmet prereqs from prereqs_for
    prereqs_res = engine.prereqs_for(ironman, SCURRIUS)
    assert isinstance(prereqs_res, Ok)
    unmet_prereq_ids = {s.node_id for s in prereqs_res.card.steps if s.status != "satisfied"}
    assert frontier_ids <= unmet_prereq_ids, (
        f"frontier {frontier_ids} is not a subset of unmet prereqs {unmet_prereq_ids}"
    )


def test_full_void_unlocks_despite_low_stats(kg):
    """A 60/60 account with full Void is UNLOCKED — the Void branch satisfies the OR.

    This is the regression-lock test: the old mis-modelled fixture (hard skill edges)
    caused a full-Void low-stats account to read as 'locked' because is_unlocked
    AND-folded the hard Attack/Strength dst edges alongside the cond-tree OR.
    With the canonical OR model (no hard skill edges) this must return 'unlocked'.
    """
    engine = Engine(kg)
    state = main_full_void()  # 60/60, full Void (melee helm + top + robe + gloves)
    res = engine.is_unlocked(state, SCURRIUS)
    assert isinstance(res, Ok)
    assert res.card.status == "unlocked", (
        f"full-Void 60/60 account must be unlocked via the Void OR branch, got {res.card.status!r}"
    )


def test_already_satisfied_goal_is_empty(kg):
    """An account that owns all Void pieces (all 3 helms + top + robe + gloves) is fully done.

    Empty(ALREADY_SATISFIED) requires EVERY node in the topo closure to be individually
    satisfied.  The closure contains item:11663, item:11664, and item:11665 (all three
    helm alternatives from the OR sub-group) — so all three must be owned, even though
    only one helm is required at runtime by the OR evaluation.  Owning only one helm
    leaves the other two as 'satisfiable', keeping the result as Ok (not Empty).

    access:scurrius-lair has no requires edges -> unconditionally satisfied for all
    accounts; no explicit access grant is needed.
    Skills (Attack/Strength) are NOT in the closure (no hard dst edges) -> not checked.
    """
    # All 3 helms + body + legs + hands = every item in the closure is owned
    done_account = AccountState(
        mode="normal",
        counts={
            HELM_MAGE: 1, HELM_RANGE: 1, HELM_MELEE: 1,
            VOID_TOP: 1, VOID_ROBE: 1, VOID_GLOVES: 1,
        },
        observable_families={"skill_level", "item", "quest", "achievement_diary"},
    )
    engine = Engine(kg)

    unlocked = engine.is_unlocked(done_account, SCURRIUS)
    assert isinstance(unlocked, Ok) and unlocked.card.status == "unlocked"

    prereqs = engine.prereqs_for(done_account, SCURRIUS)
    assert isinstance(prereqs, Empty), (
        f"expected Empty(ALREADY_SATISFIED), got {type(prereqs).__name__}"
    )
    assert prereqs.reason == TerminalReason.ALREADY_SATISFIED


def test_missing_node_is_a_problem(kg, ironman):
    engine = Engine(kg)
    res = engine.is_unlocked(ironman, "npc:does-not-exist")
    assert isinstance(res, Problem)
    assert res.kind == ProblemKind.NOT_FOUND


def test_coherent_story_across_three_reads(kg, ironman):
    """The three reads agree: locked <=> has unmet prereqs <=> Void items on the frontier.

    Blocker story (is_unlocked): Strength is a cond-tree BLOCKER (not a step).
    Step story (prereqs_for): Void items + gear_loadout + access are STEPS (not skills).
    Frontier story (next_steps): Void item leaves are immediately doable.

    Cross-read invariant: frontier ⊆ unmet prereqs.
    Honest distinction: Strength in blockers but NOT in prereq step-ids.
    A Void item (e.g. Void melee helm) appears in BOTH the step list and the frontier.
    """
    engine = Engine(kg)
    unlocked = engine.is_unlocked(ironman, SCURRIUS)
    prereqs = engine.prereqs_for(ironman, SCURRIUS)
    nxt = engine.next_steps(ironman, SCURRIUS)

    assert isinstance(unlocked, Ok) and unlocked.card.status == "locked"
    assert isinstance(prereqs, Ok) and isinstance(nxt, Ok)

    locked_blocker_ids = {b.node_id for b in unlocked.card.blockers}
    step_ids = {s.node_id for s in prereqs.card.steps}
    unmet_prereq_ids = {s.node_id for s in prereqs.card.steps if s.status != "satisfied"}
    frontier_ids = {s.node_id for s in nxt.card.steps}

    # Strength is a BLOCKER (cond-tree leaf) but NOT a prereq step
    assert STRENGTH in locked_blocker_ids, "Strength must appear as a blocker"
    assert STRENGTH not in step_ids, "Strength must NOT be a prereq step node"

    # A Void item leaf appears as both a step and on the frontier
    sample_void_item = HELM_MELEE
    assert sample_void_item in step_ids, f"{sample_void_item} must be a prereq step"
    assert sample_void_item in frontier_ids, f"{sample_void_item} must be on the frontier"

    # frontier ⊆ unmet_prereqs (subset invariant)
    assert frontier_ids <= unmet_prereq_ids, (
        f"frontier {frontier_ids} is not a subset of unmet prereqs {unmet_prereq_ids}"
    )
