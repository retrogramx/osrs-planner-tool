"""Engine-level acceptance for build_goals() part 1 (K8 goals 1-3):
Dragon scimitar, fairy rings, Tzhaar-ket-om — through the real Engine.

B2 two-node pattern: the "wield item X" goals are SEPARATE gear_loadout:<slug>
nodes whose ITEM atom references the item:<id> LEAF (built by build_supporting in
the full pipeline). The goal node is therefore distinct from the item node — no
self-loop in requires_dag(), so the reverted engine raises no UNSATISFIABLE_CYCLE.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Problem, ProblemKind

from kg_ingest.builders.goals import build_goals

# Leaf support: the quest/skill nodes referenced by the goal atoms PLUS the two
# item leaves (item:4587 / item:6528) that build_supporting would mint — they are
# referenced by the gear_loadout goals' ITEM atoms (B2).
_SUPPORT_NODES = [
    Node(id="quest:monkey-madness-i", kind=NodeKind.QUEST,
         name="Monkey Madness I", slug="monkey-madness-i", data={}),
    Node(id="quest:fairytale-ii-cure-a-queen", kind=NodeKind.QUEST,
         name="Fairytale II - Cure a Queen", slug="fairytale-ii-cure-a-queen", data={}),
    Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={}),
    Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength", data={}),
    Node(id="item:4587", kind=NodeKind.ITEM, name="Dragon scimitar",
         slug="dragon-scimitar", data={"tradeable": True}),
    Node(id="item:6528", kind=NodeKind.ITEM, name="Tzhaar-ket-om",
         slug="tzhaar-ket-om", data={"tradeable": True}),
]
_OBSERVED = {"skill_level", "item", "quest", "achievement_diary"}

_SCIM_GOAL = "gear_loadout:dragon-scimitar"
_MAUL_GOAL = "gear_loadout:obby-maul"


def _store() -> InMemoryKGStore:
    nodes, edges, groups = build_goals()
    return InMemoryKGStore(nodes=nodes + _SUPPORT_NODES, edges=edges, groups=groups)


def _card(store, state, node_id):
    return Engine(store).is_unlocked(state, node_id).card


def _status(store, state, node_id) -> str:
    return _card(store, state, node_id).status


def test_dragon_scimitar_met():
    met = AccountState(mode="normal", levels={"skill:attack": 60},
                       counts={"item:4587": 1},
                       quest_state={"quest:monkey-madness-i": "completed"},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, _SCIM_GOAL) == "unlocked"


def test_dragon_scimitar_unmet_missing_quest():
    unmet = AccountState(mode="normal", levels={"skill:attack": 60},
                         counts={"item:4587": 1},
                         quest_state={"quest:monkey-madness-i": "not_started"},
                         observable_families=_OBSERVED)
    assert _status(_store(), unmet, _SCIM_GOAL) == "locked"


def test_dragon_scimitar_unmet_low_attack():
    unmet = AccountState(mode="normal", levels={"skill:attack": 59},
                         counts={"item:4587": 1},
                         quest_state={"quest:monkey-madness-i": "completed"},
                         observable_families=_OBSERVED)
    assert _status(_store(), unmet, _SCIM_GOAL) == "locked"


def test_dragon_scimitar_unmet_not_owned_blocks_on_item_leaf():
    """The goal references item:4587 as a LEAF (B2): when not owned, the blocker is
    an ITEM atom pointing at item:4587 — proving the goal node != the item node."""
    unmet = AccountState(mode="normal", levels={"skill:attack": 60},
                         counts={},
                         quest_state={"quest:monkey-madness-i": "completed"},
                         observable_families=_OBSERVED)
    card = _card(_store(), unmet, _SCIM_GOAL)
    assert card.status == "locked"
    item_blockers = [b for b in card.blockers
                     if b.reason == "item" and b.node_id == "item:4587"]
    assert item_blockers, f"expected an ITEM blocker on item:4587, got {card.blockers}"


def test_fairy_rings_met():
    met = AccountState(mode="normal",
                       quest_state={"quest:fairytale-ii-cure-a-queen": "in_progress"},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, "access:fairy-rings") == "unlocked"


def test_fairy_rings_met_when_completed():
    met = AccountState(mode="normal",
                       quest_state={"quest:fairytale-ii-cure-a-queen": "completed"},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, "access:fairy-rings") == "unlocked"


def test_fairy_rings_unmet_not_started():
    unmet = AccountState(mode="normal",
                         quest_state={"quest:fairytale-ii-cure-a-queen": "not_started"},
                         observable_families=_OBSERVED)
    assert _status(_store(), unmet, "access:fairy-rings") == "locked"


def test_obby_maul_met():
    met = AccountState(mode="normal", levels={"skill:strength": 60},
                       counts={"item:6528": 1}, observable_families=_OBSERVED)
    assert _status(_store(), met, _MAUL_GOAL) == "unlocked"


def test_obby_maul_unmet_low_strength():
    unmet = AccountState(mode="normal", levels={"skill:strength": 59},
                         counts={"item:6528": 1}, observable_families=_OBSERVED)
    assert _status(_store(), unmet, _MAUL_GOAL) == "locked"


def test_obby_maul_unmet_not_owned_blocks_on_item_leaf():
    unmet = AccountState(mode="normal", levels={"skill:strength": 60},
                         counts={}, observable_families=_OBSERVED)
    card = _card(_store(), unmet, _MAUL_GOAL)
    assert card.status == "locked"
    item_blockers = [b for b in card.blockers
                     if b.reason == "item" and b.node_id == "item:6528"]
    assert item_blockers, f"expected an ITEM blocker on item:6528, got {card.blockers}"


def test_no_unsatisfiable_cycle():
    """The B2 separate-node model has no owner==ref_node self-loop, so the reverted
    engine (no self-loop skip) detects NO cycle and is_unlocked never returns a
    Problem(UNSATISFIABLE_CYCLE). Querying every goal succeeds with an Ok card."""
    store = _store()
    state = AccountState(mode="normal", observable_families=_OBSERVED)
    for goal in (_SCIM_GOAL, "access:fairy-rings", _MAUL_GOAL):
        res = Engine(store).is_unlocked(state, goal)
        # A self-loop would surface as Problem(UNSATISFIABLE_CYCLE); assert we got Ok.
        if isinstance(res, Problem):
            assert res.kind is not ProblemKind.UNSATISFIABLE_CYCLE, res.message
        assert isinstance(res, Ok)


def test_build_goals_emits_three_goal_nodes_and_edges():
    nodes, edges, groups = build_goals()
    node_ids = {n.id for n in nodes}
    goal_ids = {_SCIM_GOAL, "access:fairy-rings", _MAUL_GOAL}
    assert goal_ids <= node_ids
    # The goal nodes do NOT carry the item ids — the items are referenced as leaves.
    assert "item:4587" not in node_ids
    assert "item:6528" not in node_ids
    goal_srcs = {e.src for e in edges if e.type is EdgeType.REQUIRES}
    assert goal_ids <= goal_srcs
    for e in edges:
        if e.type is EdgeType.REQUIRES and e.src in goal_ids:
            assert e.dst is None
            assert e.cond_group in groups


def test_skill_atoms_carry_boostable_field():
    """K6 field-guard: every SKILL_LEVEL atom in build_goals must carry data['boostable'].
    This field is the 'boostable carried' invariant (K6/§6.1); the engine verdict stays
    strict — boostable is a flag for the suggestion layer, not the evaluator."""
    from osrs_planner.engine.kg.model import AtomType, ConditionAtom
    nodes, edges, groups = build_goals()
    for group in groups.values():
        for child in group.children:
            if isinstance(child, ConditionAtom) and child.atom_type is AtomType.SKILL_LEVEL:
                assert "boostable" in (child.data or {}), (
                    f"SKILL_LEVEL atom ref_node={child.atom_type!r} "
                    f"ref={child.ref_node!r} is missing data['boostable'] (K6)"
                )
