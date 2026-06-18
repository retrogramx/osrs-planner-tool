"""The deterministic Engine — public reads over the KG + one AccountState snapshot.

Contract: every method returns a Result (§4); refs ⊆ nodes touched this turn (§7.4).
This task implements is_unlocked (§3.1); prereqs_for/next_steps land in later tasks.
"""
from __future__ import annotations

from typing import Optional

from osrs_planner.engine.kg.store import KGStore
from osrs_planner.engine.kg.model import EdgeType, Op, AtomType, ConditionAtom
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kleene import Tri, k_and
from osrs_planner.engine.conditions import evaluate, atom_satisfied
from osrs_planner.engine.result import (
    Ok,
    Problem,
    ProblemKind,
    Result,
    Refs,
    NodeRef,
)
from osrs_planner.engine import cards


def _is_state_absent(state: Optional[AccountState]) -> bool:
    """A WHOLLY-absent account -> Problem(MISSING_STATE).

    D4: MISSING_STATE fires ONLY when there is no account at all (state is None).
    A fresh real account (mode set, empty progress dicts, combat_level == 3) is a
    VALID account, not missing — its absent values resolve to FALSE/UNKNOWN via the
    absence-aware Kleene rule, never MISSING_STATE.
    """
    return state is None


class Engine:
    def __init__(self, kg: KGStore):
        self.kg = kg

    # -- helpers ----------------------------------------------------------
    def _requires_edges(self, node_id: str) -> list:
        """ALL of node_id's `requires` edges (D5: a node may have many; folded as AND).

        Each edge contributes (cond_group, dst): the edge is satisfied iff its
        cond_group (if any) is TRUE AND its dst node (if non-NULL) is itself unlocked.
        """
        return [
            edge
            for edge in self.kg.edges
            if edge.type == EdgeType.REQUIRES and edge.src == node_id
        ]

    def _edge_verdict(self, edge, state: AccountState) -> Tri:
        """D5: a single requires edge is satisfied iff its cond_group (if any) is TRUE
        AND its dst node (if non-NULL) is itself unlocked (recursive)."""
        parts: list[Tri] = []
        if edge.cond_group is not None:
            parts.append(evaluate(edge.cond_group, state, self.kg))
        if edge.dst is not None:
            parts.append(self._node_verdict(edge.dst, state))
        return k_and(parts) if parts else Tri.TRUE

    def _node_verdict(self, node_id: str, state: AccountState) -> Tri:
        """Fold ALL of a node's requires edges as an AND (D5)."""
        edges = self._requires_edges(node_id)
        if not edges:
            return Tri.TRUE  # unconditional => unlocked
        return k_and([self._edge_verdict(e, state) for e in edges])

    def _noderef(self, node_id: str) -> NodeRef:
        n = self.kg.node(node_id)
        if n is None:
            return NodeRef(id=node_id, kind="", name=node_id)
        return NodeRef(id=n.id, kind=n.kind.value, name=n.name)

    # -- §3.1 reads -------------------------------------------------------
    def is_unlocked(self, state: Optional[AccountState], node_id: str) -> Result[cards.UnlockCard]:
        # D7: NOT_FOUND carries an EMPTY Refs; the unknown id is named in the message.
        node = self.kg.node(node_id)
        if node is None:
            return Problem(
                kind=ProblemKind.NOT_FOUND,
                refs=Refs(),
                message=f"node {node_id!r} not found",
            )
        # D4: MISSING_STATE only when there is no account at all (state is None).
        if _is_state_absent(state):
            return Problem(
                kind=ProblemKind.MISSING_STATE,
                refs=Refs(nodes={node_id: self._noderef(node_id)}),
                message=f"no account state to evaluate {node_id!r}",
            )

        refs_nodes = {node_id: self._noderef(node_id)}
        # D5: fold ALL of the node's requires edges as an AND.
        edges = self._requires_edges(node_id)
        verdict = self._node_verdict(node_id, state)

        status = {
            Tri.TRUE: "unlocked",
            Tri.FALSE: "locked",
            Tri.UNKNOWN: "indeterminate",
        }[verdict]

        blockers: list[cards.Step] = []
        if verdict is not Tri.TRUE:
            for edge in edges:
                if edge.cond_group is not None:
                    blockers.extend(
                        self._collect_failures(edge.cond_group, state, refs_nodes)
                    )
                if edge.dst is not None and self._node_verdict(edge.dst, state) is not Tri.TRUE:
                    # the prerequisite node itself is not unlocked -> surface it as a leaf
                    refs_nodes.setdefault(edge.dst, self._noderef(edge.dst))
                    blockers.append(self._dst_step(edge.dst, state))

        card = cards.UnlockCard(
            node_id=node_id,
            status=status,
            blockers=blockers,
        )
        return Ok(card=card, refs=Refs(nodes=refs_nodes))

    def _collect_failures(
        self, group_id: int, state: AccountState, refs_nodes: dict
    ) -> list[cards.Step]:
        # Filled in Step 4. Empty for now so Step 1 (no blockers) passes.
        return []

    def _dst_step(self, dst_id: str, state: AccountState) -> cards.Step:
        """A prerequisite NODE (D5 edge.dst) that is itself not unlocked -> a Step.

        'is_unlocked' is the reason family (the dst is gated by its own requires);
        UNKNOWN -> cant_verify, otherwise satisfiable.
        """
        tri = self._node_verdict(dst_id, state)
        n = self.kg.node(dst_id)
        return cards.Step(
            node_id=dst_id,
            name=n.name if n is not None else dst_id,
            reason="is_unlocked",
            status="cant_verify" if tri is Tri.UNKNOWN else "satisfiable",
        )

    def prereqs_for(self, state: AccountState, node_id: str) -> Result[cards.PlanCard]:
        raise NotImplementedError  # later task

    def next_steps(self, state: AccountState, node_id: str) -> Result[cards.PlanCard]:
        raise NotImplementedError  # later task
