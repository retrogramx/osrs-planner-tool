# src/osrs_planner/income/filter.py
"""Can-do-now classification for income methods (design §5).

Reuses the engine's condition-evaluator (single source of truth for "does this
account meet this requirement") so income inherits absence-aware UNKNOWN (§6),
boostable-skill semantics, and quest 3-state. Per method we build skill_level /
quest / item ConditionAtoms from method.requirements and fold the per-atom
Kleene verdicts into ONE method-level status:

  doable_now    -- every requirement atom is TRUE.
  future_gated  -- >=1 atom is a hard FALSE (a level below threshold, a quest not
                   done on an observed account). The hard gate DOMINATES any
                   UNKNOWN: you can't do it regardless of the unknowns.
  unverified    -- no hard FALSE, but >=1 atom is UNKNOWN (item ownership the
                   state can't confirm, or a prose item / unresolvable quest).
                   Absence != zero -- never falsely doable.

The requirement check is AUTHORITATIVE; method.stage is a soft hint, ignored here.
"""
from __future__ import annotations

import re

from osrs_planner.engine.conditions import atom_satisfied
from osrs_planner.engine.kg.model import AtomType, ConditionAtom
from osrs_planner.engine.kg.store import KGStore
from osrs_planner.engine.kleene import Tri
from osrs_planner.engine.state import AccountState

# Trailing "(...)" prose on quest refs, e.g. "A Kingdom Divided (for thralls)".
_PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def _skill_id(display_name: str) -> str:
    """A dataset skill DISPLAY name -> its KG node id ("Firemaking"->"skill:firemaking")."""
    return f"skill:{display_name.strip().lower()}"


def _resolve_quest_id(display_name: str, kg: KGStore) -> str | None:
    """Resolve a quest DISPLAY name (with optional prose suffix) to its KG node id.

    Strips the parenthetical suffix and matches a quest node by case-insensitive
    name. Unresolvable -> None (the caller marks it unverified, never a false pass).
    """
    cleaned = _PAREN_SUFFIX.sub("", display_name).strip()
    target = cleaned.casefold()
    for node in kg.nodes.values():
        if node.kind.value == "quest" and node.name.casefold() == target:
            return node.id
    return None


def _build_atoms(method, kg: KGStore) -> tuple[list[tuple[str, ConditionAtom]], list[str]]:
    """(ref_id, atom) pairs for evaluable reqs + a list of unresolvable refs.

    Unresolvable refs (a quest name not in the KG, an item req that isn't an
    item:<n> id) become "unverified" (we can't prove the account lacks them); a
    non-int skill threshold is dropped (advisory, no gate).
    """
    atoms: list[tuple[str, ConditionAtom]] = []
    unresolvable: list[str] = []
    req = method.requirements

    for skill_name, level in req.skills.items():
        if not isinstance(level, int):
            continue  # e.g. {"Combat":"High"} -- advisory, not a numeric gate
        # method.requirements skill keys may already be "skill:<name>" (parsed)
        # OR a display name; normalize to a skill id either way.
        sid = skill_name if str(skill_name).startswith("skill:") else _skill_id(skill_name)
        atoms.append((sid, ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=sid, threshold=level)))

    for quest_ref in req.quests:
        # An already-slugged "quest:<slug>" ref resolves iff its node exists. A ref
        # to a known-missing quest node (e.g. quest:crack-the-clue-iii, absent from
        # the KG) makes kg.node(...) None -> falls to _resolve_quest_id (also None)
        # -> goes to unresolvable -> unverified. DR-3: a missing quest node DEGRADES
        # to unverified gracefully (absence != zero) -- never crashes, never falsely
        # doable. (A display-name ref is resolved by name via _resolve_quest_id.)
        qid = quest_ref if str(quest_ref).startswith("quest:") and kg.node(quest_ref) else _resolve_quest_id(quest_ref, kg)
        if qid is None:
            unresolvable.append(quest_ref)
            continue
        atoms.append((qid, ConditionAtom(atom_type=AtomType.QUEST, ref_node=qid, data={"state": "completed"})))

    for item_ref in req.items:
        if isinstance(item_ref, str) and item_ref.startswith("item:"):
            atoms.append((item_ref, ConditionAtom(atom_type=AtomType.ITEM, ref_node=item_ref, qty=1)))
        else:
            unresolvable.append(item_ref)  # prose ("food", "Rogue equipment")

    return atoms, unresolvable


def classify_method(method, state: AccountState, kg: KGStore) -> tuple[str, dict]:
    """Classify one method's requirements against the account.

    Returns (status, detail) where status in {"doable_now","future_gated",
    "unverified"} and detail = {"missing":[ref...], "unverified":[ref...]}. A hard
    FALSE (missing) dominates an UNKNOWN (unverified).
    """
    atoms, unresolvable = _build_atoms(method, kg)
    missing: list[str] = []
    unverified: list[str] = list(unresolvable)

    for ref_id, atom in atoms:
        verdict = atom_satisfied(atom, state, kg)
        if verdict is Tri.FALSE:
            missing.append(ref_id)
        elif verdict is Tri.UNKNOWN:
            unverified.append(ref_id)

    detail = {"missing": missing, "unverified": unverified}
    if missing:
        return "future_gated", detail
    if unverified:
        return "unverified", detail
    return "doable_now", detail
