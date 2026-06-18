"""Recursive three-valued (Kleene) condition evaluation over the KG.

evaluate(group_id, state, kg) folds a condition_group tree via kleene.
atom_satisfied(atom, state, kg) tests one leaf, honoring the absence-aware
UNKNOWN rule (kg-schema-v1 atom semantics; engine-advisor-contract section 6).
"""
from __future__ import annotations

from osrs_planner.engine.kleene import Tri, k_and, k_or, k_not, from_bool
from osrs_planner.engine.kg.model import AtomType, Op, ConditionAtom
from osrs_planner.engine.kg.store import KGStore
from osrs_planner.engine.state import AccountState, QUEST_STATE_ORDER, family_is_observed


def atom_satisfied(atom: ConditionAtom, state: AccountState, kg: KGStore) -> Tri:
    at = atom.atom_type

    if at is AtomType.SKILL_LEVEL:
        # skill levels are observable for any tracked account -> absent = level 1 = real FALSE
        return from_bool(state.levels.get(atom.ref_node, 1) >= (atom.threshold or 0))

    if at is AtomType.SKILL_XP:
        return from_bool(state.xp.get(atom.ref_node, 0) >= (atom.threshold or 0))

    if at is AtomType.COMBAT_LEVEL:
        # engine-derived scalar, always present (defaults to 3) -> never UNKNOWN
        return from_bool(state.combat_level >= (atom.threshold or 0))

    if at is AtomType.QUEST_POINTS:
        return from_bool(state.qp >= (atom.threshold or 0))

    if at is AtomType.COMBAT_ACHIEVEMENT_POINTS:
        return from_bool(state.ca_points >= (atom.threshold or 0))

    if at is AtomType.ITEM:
        # items observable via the bank feed -> absent = 0 owned = real FALSE
        return from_bool(state.counts.get(atom.ref_node, 0) >= (atom.qty or 1))

    if at is AtomType.ACCOUNT_TYPE:
        # mode is always known for a loaded account -> never UNKNOWN
        return from_bool(state.mode == atom.data.get("value"))

    raise NotImplementedError(f"atom_satisfied: {at!r} not implemented")


def evaluate(group_id: int, state: AccountState, kg: KGStore) -> Tri:
    """Recursively evaluate a condition_group, folding children via Kleene."""
    group = kg.groups[group_id]
    values: list[Tri] = []
    for child in kg.children_of(group_id):
        if isinstance(child, ConditionAtom):
            values.append(atom_satisfied(child, state, kg))
        else:  # a child condition_group id (int)
            values.append(evaluate(child, state, kg))

    if group.op is Op.AND:
        return k_and(values)
    if group.op is Op.OR:
        return k_or(values)
    # NOT -> exactly one child (enforced by schema invariant I5)
    return k_not(values[0])
