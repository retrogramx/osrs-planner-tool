"""Engine-level acceptance for build_goals() part 1 (K8 goals 1-3):
Dragon scimitar, fairy rings, Tzhaar-ket-om — through the real Engine.

K8/K1 gates-only stance: single tradeable items are gated by prerequisites only;
owning the final item is the deferred acquisition/cost layer. The goal node IS the
item node (item:4587 / item:6528), requiring only skill/quest gates — no ITEM atom,
no separate gear_loadout node. No self-loop in requires_dag() since the requires
group references skill/quest nodes, not the item node itself.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Problem, ProblemKind

from kg_ingest.builders.goals import build_goals

# Leaf support: the quest/skill nodes referenced by the goal atoms.
# item:4587 and item:6528 are now the GOAL nodes themselves (emitted by build_goals),
# so they do NOT appear in _SUPPORT_NODES — they come from build_goals() directly.
_SUPPORT_NODES = [
    Node(id="quest:monkey-madness-i", kind=NodeKind.QUEST,
         name="Monkey Madness I", slug="monkey-madness-i", data={}),
    Node(id="quest:fairytale-ii-cure-a-queen", kind=NodeKind.QUEST,
         name="Fairytale II - Cure a Queen", slug="fairytale-ii-cure-a-queen", data={}),
    Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={}),
    Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength", data={}),
]
_OBSERVED = {"skill_level", "item", "quest", "achievement_diary"}

_SCIM_GOAL = "item:4587"
_MAUL_GOAL = "item:6528"


def _store() -> InMemoryKGStore:
    nodes, edges, groups = build_goals()
    return InMemoryKGStore(nodes=nodes + _SUPPORT_NODES, edges=edges, groups=groups)


def _card(store, state, node_id):
    return Engine(store).is_unlocked(state, node_id).card


def _status(store, state, node_id) -> str:
    return _card(store, state, node_id).status


def test_dragon_scimitar_met():
    """60 Attack + MM1 completed -> scimitar UNLOCKED (gates-only; no item ownership check)."""
    met = AccountState(mode="normal", levels={"skill:attack": 60},
                       quest_state={"quest:monkey-madness-i": "completed"},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, _SCIM_GOAL) == "unlocked"


def test_dragon_scimitar_unmet_missing_quest():
    """MM1 not started -> scimitar LOCKED (quest blocker)."""
    unmet = AccountState(mode="normal", levels={"skill:attack": 60},
                         quest_state={"quest:monkey-madness-i": "not_started"},
                         observable_families=_OBSERVED)
    assert _status(_store(), unmet, _SCIM_GOAL) == "locked"


def test_dragon_scimitar_unmet_low_attack():
    """59 Attack -> scimitar LOCKED (skill_level blocker)."""
    unmet = AccountState(mode="normal", levels={"skill:attack": 59},
                         quest_state={"quest:monkey-madness-i": "completed"},
                         observable_families=_OBSERVED)
    card = _card(_store(), unmet, _SCIM_GOAL)
    assert card.status == "locked"
    skill_blockers = [b for b in card.blockers if b.reason == "skill_level"]
    assert skill_blockers, f"expected a skill_level blocker, got {card.blockers}"


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
    """60 Strength -> obby maul UNLOCKED (gates-only; no item ownership check)."""
    met = AccountState(mode="normal", levels={"skill:strength": 60},
                       observable_families=_OBSERVED)
    assert _status(_store(), met, _MAUL_GOAL) == "unlocked"


def test_obby_maul_unmet_low_strength():
    """59 Strength -> obby maul LOCKED (skill_level blocker)."""
    unmet = AccountState(mode="normal", levels={"skill:strength": 59},
                         observable_families=_OBSERVED)
    card = _card(_store(), unmet, _MAUL_GOAL)
    assert card.status == "locked"
    skill_blockers = [b for b in card.blockers if b.reason == "skill_level"]
    assert skill_blockers, f"expected a skill_level blocker, got {card.blockers}"


def test_no_unsatisfiable_cycle():
    """Goals reference only skill/quest nodes — no self-loop in requires_dag().
    is_unlocked returns Ok, never Problem(UNSATISFIABLE_CYCLE)."""
    store = _store()
    state = AccountState(mode="normal", observable_families=_OBSERVED)
    for goal in (_SCIM_GOAL, "access:fairy-rings", _MAUL_GOAL):
        res = Engine(store).is_unlocked(state, goal)
        # A self-loop would surface as Problem(UNSATISFIABLE_CYCLE); assert we got Ok.
        if isinstance(res, Problem):
            assert res.kind is not ProblemKind.UNSATISFIABLE_CYCLE, res.message
        assert isinstance(res, Ok)


def test_build_goals_emits_item_goal_nodes():
    """item:4587 and item:6528 ARE the goal nodes (gates-only shape); no separate
    gear_loadout nodes for scimitar/obby maul."""
    nodes, edges, groups = build_goals()
    node_ids = {n.id for n in nodes}
    # The item nodes are now emitted directly as goal nodes.
    assert "item:4587" in node_ids, "Dragon scimitar goal node item:4587 missing"
    assert "item:6528" in node_ids, "Obby maul goal node item:6528 missing"
    # No separate gear_loadout nodes for scimitar / obby maul.
    assert "gear_loadout:dragon-scimitar" not in node_ids
    assert "gear_loadout:obby-maul" not in node_ids
    # All three part-1 goal ids have a dst=None REQUIRES edge.
    goal_ids = {_SCIM_GOAL, "access:fairy-rings", _MAUL_GOAL}
    goal_srcs = {e.src for e in edges if e.type is EdgeType.REQUIRES}
    assert goal_ids <= goal_srcs
    for e in edges:
        if e.type is EdgeType.REQUIRES and e.src in goal_ids:
            assert e.dst is None
            assert e.cond_group in groups


def test_scimitar_goal_has_no_item_atom():
    """K8/K1: item:4587 goal requires only skill/quest gates — no ITEM atom."""
    from osrs_planner.engine.kg.model import AtomType, ConditionAtom
    nodes, edges, groups = build_goals()
    scim_edge = next(e for e in edges
                     if e.type is EdgeType.REQUIRES and e.src == _SCIM_GOAL)
    group = groups[scim_edge.cond_group]
    item_atoms = [c for c in group.children
                  if isinstance(c, ConditionAtom) and c.atom_type is AtomType.ITEM]
    assert not item_atoms, f"scimitar goal must have no ITEM atom, found {item_atoms}"


def test_obby_maul_goal_has_no_item_atom():
    """K8/K1: item:6528 goal requires only skill gates — no ITEM atom."""
    from osrs_planner.engine.kg.model import AtomType, ConditionAtom
    nodes, edges, groups = build_goals()
    maul_edge = next(e for e in edges
                     if e.type is EdgeType.REQUIRES and e.src == _MAUL_GOAL)
    group = groups[maul_edge.cond_group]
    item_atoms = [c for c in group.children
                  if isinstance(c, ConditionAtom) and c.atom_type is AtomType.ITEM]
    assert not item_atoms, f"obby maul goal must have no ITEM atom, found {item_atoms}"


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
