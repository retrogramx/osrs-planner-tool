"""The deterministic Engine — public reads over the KG + one AccountState snapshot.

Contract: every method returns a Result (§4); refs ⊆ nodes touched this turn (§7.4).
This task implements is_unlocked (§3.1); prereqs_for/next_steps land in later tasks.
"""
from __future__ import annotations

from typing import Optional

from osrs_planner.engine.kg.store import KGStore
from osrs_planner.engine.kg.model import Edge, EdgeType, AtomType, ConditionAtom
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kleene import Tri, k_and
from osrs_planner.engine.conditions import evaluate, atom_satisfied
from osrs_planner.engine.result import (
    Ok,
    Empty,
    Problem,
    ProblemKind,
    TerminalReason,
    Result,
    Refs,
    NodeRef,
)
from osrs_planner.engine import cards
from osrs_planner.engine.cards import PlanCard, Step, ReferencedAtom


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
    def _requires_edges(self, node_id: str) -> list[Edge]:
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
                if edge.dst is not None:
                    dst_tri = self._node_verdict(edge.dst, state)
                    if dst_tri is not Tri.TRUE:
                        # the prerequisite node itself is not unlocked -> surface it as a leaf
                        refs_nodes.setdefault(edge.dst, self._noderef(edge.dst))
                        blockers.append(self._dst_step(edge.dst, dst_tri))

        card = cards.UnlockCard(
            node_id=node_id,
            status=status,
            blockers=blockers,
        )
        return Ok(card=card, refs=Refs(nodes=refs_nodes))

    def _collect_failures(
        self, group_id: int, state: AccountState, refs_nodes: dict[str, NodeRef]
    ) -> list[cards.Step]:
        """Walk the cond tree; record every non-TRUE *leaf* as a failing/unverifiable Step.

        - FALSE leaf            -> status 'satisfiable'  (or 'impossible_for_mode' for a
                                   false account_type atom that prunes its branch, §5.3b)
        - UNKNOWN leaf          -> status 'cant_verify'  (Kleene; never a false 'locked', §6)
        Each ref-bearing leaf's ref_node enters refs_nodes (the grounding leash, §7.4).
        """
        steps: list[cards.Step] = []
        for child in self.kg.children_of(group_id):
            if isinstance(child, ConditionAtom):
                tri = atom_satisfied(child, state, self.kg)
                if tri is Tri.TRUE:
                    continue
                if child.ref_node is not None:
                    refs_nodes.setdefault(child.ref_node, self._noderef(child.ref_node))
                steps.append(self._leaf_step(child, tri))
            else:  # a sub-group id (int)
                steps.extend(self._collect_failures(int(child), state, refs_nodes))
        return steps

    def _leaf_step(self, atom: ConditionAtom, tri: Tri) -> cards.Step:
        if tri is Tri.UNKNOWN:
            status = "cant_verify"
        elif atom.atom_type == AtomType.ACCOUNT_TYPE:
            # a false account_type atom is a hard mode wall, not a trainable gap (§5.3b)
            status = "impossible_for_mode"
        else:
            status = "satisfiable"
        name = atom.ref_node
        if atom.ref_node is not None:
            n = self.kg.node(atom.ref_node)
            if n is not None:
                name = n.name
        return cards.Step(
            node_id=atom.ref_node,
            name=name if name is not None else atom.atom_type.value,
            reason=atom.atom_type.value,
            status=status,
        )

    def _dst_step(self, dst_id: str, tri: Tri) -> cards.Step:
        """A prerequisite NODE (D5 edge.dst) that is itself not unlocked -> a Step.

        'is_unlocked' is the reason family (the dst is gated by its own requires);
        UNKNOWN -> cant_verify, otherwise satisfiable.
        """
        n = self.kg.node(dst_id)
        return cards.Step(
            node_id=dst_id,
            name=n.name if n is not None else dst_id,
            reason="is_unlocked",
            status="cant_verify" if tri is Tri.UNKNOWN else "satisfiable",
        )

    # -- prereqs_for helpers -----------------------------------------------
    def _atoms_referencing(self, node_id: str) -> list:
        """Every condition atom (in any requires cond_group across the KG) whose
        ref_node is node_id — i.e. how a PARENT references this prereq (quest state,
        is_unlocked, skill_level threshold, …). This is the account-meets-prereq test,
        not the prereq's own downstream requires (Defect 5)."""
        out = []
        for e in self.kg.edges:
            if e.type is EdgeType.REQUIRES and e.cond_group is not None:
                for atom in self._iter_group_atoms(e.cond_group):
                    if atom.ref_node == node_id:
                        out.append(atom)
        return out

    def _account_meets_tri(self, state: AccountState, node_id: str) -> Tri:
        """AND-fold of every atom that references node_id (does the ACCOUNT meet it?).
        No referencing atom (e.g. the goal itself, or a bare dst node) -> delegate to
        _node_verdict so a node-type prereq reads as 'is it itself unlocked' (D5),
        including bare dst-only edges that carry no cond_group."""
        refs = self._atoms_referencing(node_id)
        if refs:
            return k_and([atom_satisfied(a, state, self.kg) for a in refs])
        # node-type prereq with no referencing atom: delegate to _node_verdict (D5)
        # so that bare dst-only requires edges (no cond_group) are also folded in.
        return self._node_verdict(node_id, state)

    def _step_status_for(self, state: AccountState, node_id: str) -> tuple[str, str]:
        """Map whether the ACCOUNT meets a prereq to a Step (status, reason). §5.2 vocab:
        satisfied | satisfiable | cant_verify (UNKNOWN) | impossible_for_mode."""
        tri = self._account_meets_tri(state, node_id)
        if tri is Tri.TRUE:
            return ("satisfied", "satisfied")
        if tri is Tri.UNKNOWN:
            return ("cant_verify", self._first_reason(state, node_id, Tri.UNKNOWN))
        # FALSE -> not yet met but reachable; impossible_for_mode is set elsewhere
        # (only via Unacquirable / pruned account_type branch — not computed in v1 here).
        return ("satisfiable", self._first_reason(state, node_id, Tri.FALSE))

    def _iter_atoms_for(self, node_id: str):
        for e in self.kg.edges:
            if e.type is EdgeType.REQUIRES and e.src == node_id and e.cond_group is not None:
                yield from self._iter_group_atoms(e.cond_group)

    def _iter_group_atoms(self, group_id: int):
        for child in self.kg.children_of(group_id):
            if isinstance(child, ConditionAtom):
                yield child
            else:  # int sub-group id
                yield from self._iter_group_atoms(int(child))

    def _first_reason(self, state: AccountState, node_id: str, want: Tri) -> str:
        # name the atom (referencing the prereq) whose verdict is `want` (FALSE/UNKNOWN)
        for atom in self._atoms_referencing(node_id):
            if atom_satisfied(atom, state, self.kg) is want:
                return atom.atom_type.value
        for atom in self._iter_atoms_for(node_id):
            if atom_satisfied(atom, state, self.kg) is want:
                return atom.atom_type.value
        return "requires"

    # -- §3.2 reads -------------------------------------------------------
    def prereqs_for(self, state: Optional[AccountState], node_id: str) -> "Result[PlanCard]":
        # §10: guard source ∈ dag before descendants()
        node = self.kg.node(node_id)
        if node is None:
            # D7: NOT_FOUND carries an EMPTY Refs; the unknown id is named in the
            # message only (an unknown id is not a node, so it cannot be a NodeRef).
            return Problem(
                kind=ProblemKind.NOT_FOUND,
                refs=Refs(),
                message=f"no node with id {node_id!r}",
            )
        # D4: MISSING_STATE only when there is no account at all (state is None);
        # a fresh valid account (mode set, empty progress, combat_level == 3) is NOT missing.
        if state is None:
            return Problem(
                kind=ProblemKind.MISSING_STATE,
                refs=Refs(nodes={node_id: self._noderef(node_id)}),
                message=f"no account state to evaluate {node_id!r}",
            )
        # I1: cycles fail the build; guard at runtime so a bad fixture fails closed (§10).
        cycles = self.kg.find_cycles()
        cycle_nodes = {n for cyc in cycles for n in cyc}
        closure = self.kg.descendants(node_id)
        relevant = cycle_nodes & (closure | {node_id})
        if relevant:
            cyc_refs = {nid: self._noderef(nid) for nid in relevant}
            return Problem(
                kind=ProblemKind.UNSATISFIABLE_CYCLE,
                refs=Refs(mentions=cyc_refs),
                message=f"prereq cycle: {sorted(relevant)}",
            )
        goal_ref = {node_id: self._noderef(node_id)}
        # Already satisfied = the goal's own requires fold is TRUE AND the account meets
        # every prereq. prereq_ids is PREREQS-FIRST (D1: reversed topological_sort).
        goal_tri = self._node_verdict(node_id, state)  # the goal's own requires fold (D5)
        prereq_ids = self.kg.topo_order(node_id)        # prerequisites BEFORE the goal (D1)
        prereq_ids = [pid for pid in prereq_ids if pid != node_id]
        all_done = all(self._account_meets_tri(state, pid) is Tri.TRUE for pid in prereq_ids)
        if goal_tri is Tri.TRUE and all_done:
            return Empty(refs=Refs(nodes=goal_ref), reason=TerminalReason.ALREADY_SATISFIED)
        steps: list[Step] = []
        refs_nodes = dict(goal_ref)
        ref_atoms: list[ReferencedAtom] = []
        seen_atoms: set[tuple] = set()

        for pid in prereq_ids:                       # prereqs-first order (D1), goal excluded
            pnode = self.kg.node(pid)
            status, reason = self._step_status_for(state, pid)   # account-meets-prereq (Defect 5)
            steps.append(Step(node_id=pid,
                              name=(pnode.name if pnode else pid),
                              reason=reason,
                              status=status))
            refs_nodes[pid] = self._noderef(pid)

        # referenced_atoms = every atom the Engine read across the goal's + prereqs' requires
        # trees (the goal's own atoms reference the top-level prereqs, so include node_id).
        for owner in [node_id] + prereq_ids:
            for atom in self._iter_atoms_for(owner):
                key = (atom.atom_type.value, atom.ref_node, atom.threshold, atom.qty)
                if key in seen_atoms:
                    continue
                seen_atoms.add(key)
                partial = (atom.atom_type.value == "quest"
                           and atom.data.get("state", "completed") != "completed")
                ref_atoms.append(ReferencedAtom(
                    atom_type=atom.atom_type.value,
                    ref_node=atom.ref_node,
                    threshold=atom.threshold,
                    qty=atom.qty,
                    state=atom.data.get("state"),
                    is_partial=partial,
                ))

        return Ok(
            card=PlanCard(goal_id=node_id, steps=steps, referenced_atoms=ref_atoms),
            refs=Refs(nodes=refs_nodes),
        )

    def next_steps(self, state: Optional[AccountState], node_id: str) -> "Result[PlanCard]":
        """The frontier subset of prereqs_for: prerequisites whose OWN prerequisites
        are all already satisfied (immediately-doable). Contract §3.1.

        - Reuses prereqs_for so the two reads share Step instances (contract §5.2).
        - A prereq is on the frontier iff it is not yet satisfied AND every node in
          its own requires-closure is satisfied for the account.
        - impossible_for_mode / cant_verify prereqs are never actionable, and any
          prereq blocked behind such a node stays off the frontier.
        - Nothing actionable -> Empty(NO_FRONTIER) (a success state, §4).
        """
        base = self.prereqs_for(state, node_id)
        # Propagate Problem (NOT_FOUND / MISSING_STATE / ...) and the
        # ALREADY_SATISFIED terminal verbatim — same preconditions as prereqs_for.
        if not isinstance(base, Ok):
            return base

        plan = base.card
        # refs live on the Ok envelope, NOT on PlanCard (see Task 9 cards.py).
        base_refs = base.refs

        # Which prereq node-ids are already satisfied?
        satisfied = {s.node_id for s in plan.steps if s.status == "satisfied"}

        frontier: list[Step] = []
        for step in plan.steps:
            if step.status == "satisfied":
                continue
            if step.status != "satisfiable":
                # impossible_for_mode or cant_verify is not actionable now.
                continue
            if step.node_id is None:
                # ref-less accumulator atom: actionable only if it has no node-prereqs,
                # which by construction it does not (no closure to gate it).
                frontier.append(step)
                continue
            # A prereq is actionable iff every node in its own requires-closure is already satisfied.
            own_prereqs = self.kg.descendants(step.node_id)
            if all(p in satisfied for p in own_prereqs):
                frontier.append(step)

        if not frontier:
            return Empty(refs=base_refs, reason=TerminalReason.NO_FRONTIER)

        # Reuse the parent envelope's refs/referenced_atoms (subset is still grounded;
        # every frontier node is already in base_refs). §7.4 refs ⊆ touched-this-turn.
        return Ok(
            card=PlanCard(
                goal_id=plan.goal_id,
                steps=frontier,
                referenced_atoms=plan.referenced_atoms,
            ),
            refs=base_refs,
        )
