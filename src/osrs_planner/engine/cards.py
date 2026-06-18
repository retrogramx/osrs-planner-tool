# src/osrs_planner/engine/cards.py
"""Public, JSON-serializable return cards for the goal engine.

Convention: internal KG/state/eval types are @dataclass; the public cards the
Engine returns (inside Ok.card of the Result envelope) are pydantic BaseModels
so they project cleanly to JSON / LLM tool-schemas. See contract §5.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class NodeRef(BaseModel):
    """Card-layer twin of result.NodeRef (a node the card points at)."""

    id: str
    kind: str
    name: str


class ReferencedAtom(BaseModel):
    """A typed scalar the Engine actually read, so the grounding check can
    verify numbers the Advisor states (contract §5.6, the "scalar leash")."""

    atom_type: str
    ref_node: Optional[str] = None
    threshold: Optional[int] = None
    qty: Optional[int] = None
    state: Optional[str] = None
    is_partial: bool = False


class Step(BaseModel):
    """One ordered plan line / blocker leaf.

    reason: the failing atom_type (e.g. 'SKILL_LEVEL') or the literal 'satisfied'.
    status: 'satisfiable' | 'impossible_for_mode' | 'satisfied' | 'cant_verify'.
    """

    node_id: Optional[str] = None
    name: str
    reason: str
    status: str


class UnlockCard(BaseModel):
    """Answer to is_unlocked: a status verdict + the failing leaves.

    status: 'unlocked' | 'locked' | 'indeterminate'.
    An UNKNOWN (cant_verify) leaf surfaces here as a blocker Step (§6).
    """

    node_id: str
    status: str
    blockers: list[Step] = Field(default_factory=list)


class PlanCard(BaseModel):
    """Answer to prereqs_for / next_steps: an ordered plan + the scalars read.

    steps are in topo order (full closure for prereqs_for; the immediately-doable
    frontier subset for next_steps). referenced_atoms is the §5.6 scalar leash.
    """

    goal_id: str
    steps: list[Step] = Field(default_factory=list)
    referenced_atoms: list[ReferencedAtom] = Field(default_factory=list)
