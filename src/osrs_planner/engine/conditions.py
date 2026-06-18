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


def _done_membership(family: str, ref_node: str, state: AccountState) -> Tri:
    """Binary 'ref_node in state.done', honoring the absence-aware UNKNOWN rule.

    D6: presence of the value in the relevant state dict is 'known'; the
    observed-vs-UNKNOWN decision for an ABSENT value routes through
    family_is_observed (the single source of the §6 rule).

    Present in done  -> TRUE (a manually-confirmed value is present here too).
    Absent + family observed -> real FALSE (we'd have seen it if it were done).
    Absent + family unobservable -> UNKNOWN (can't tell; never a false 'locked').
    """
    if ref_node in state.done:
        return Tri.TRUE
    if family_is_observed(family, state, manually_asserted=False):
        return Tri.FALSE
    return Tri.UNKNOWN


def _ordered_state(family: str, ref_node: str, required: str,
                   observed: dict, state: AccountState) -> Tri:
    """3-state ordered comparison via QUEST_STATE_ORDER (reused for quest + diary).

    Satisfied iff order[current] >= order[required]. Absent value:
      family observable -> treat as 'not_started' (order 0) = real comparison;
      family unobservable -> UNKNOWN.
    """
    have = observed.get(ref_node)
    if have is None:
        # D6: an absent value is a real not_started only if the family is observed
        # (or manually asserted); otherwise it is genuinely UNKNOWN.
        if family_is_observed(family, state, manually_asserted=False):
            have = "not_started"
        else:
            return Tri.UNKNOWN
    return from_bool(QUEST_STATE_ORDER[have] >= QUEST_STATE_ORDER[required])


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

    if at is AtomType.IS_UNLOCKED:
        return _done_membership("is_unlocked", atom.ref_node, state)

    if at is AtomType.COMBAT_ACHIEVEMENT:
        return _done_membership("combat_achievement", atom.ref_node, state)

    if at is AtomType.QUEST:
        return _ordered_state("quest", atom.ref_node, atom.data["state"],
                              state.quest_state, state)

    if at is AtomType.ACHIEVEMENT_DIARY:
        return _ordered_state("achievement_diary", atom.ref_node, atom.data["state"],
                              state.diary_state, state)

    if at is AtomType.KILL_COUNT:
        if atom.ref_node in state.kc:
            return from_bool(state.kc[atom.ref_node] >= (atom.threshold or 0))
        # absence != zero (could be below the Hiscores tracking cutoff); D6 routes
        # the observed-vs-UNKNOWN decision through family_is_observed.
        if family_is_observed("kill_count", state, manually_asserted=False):
            return from_bool(0 >= (atom.threshold or 0))
        return Tri.UNKNOWN

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
