"""KG store interface + in-memory implementation.

KGStore is the read interface the future ingest brick will implement; the engine
only ever depends on this surface. InMemoryKGStore is built from plain lists of
Node/Edge/ConditionGroup (used by tests and the hand-authored fixture).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import networkx as nx

from osrs_planner.engine.kg.model import (
    AtomType,
    ConditionAtom,
    ConditionGroup,
    Edge,
    EdgeType,
    Node,
)

# Edge kind string constants — use these everywhere instead of bare literals.
EDGE_KIND_REQUIRES = "requires"
EDGE_KIND_COND_DEP = "cond_dep"
EDGE_KIND_GRANT_SYNTHETIC = "grant_synthetic"

# atom_types whose ref_node is a real node FK -> projected as 'cond_dep' closure
# edges (kg-schema-v1.md: the requires_dag ref-leaf projection, MUST-FIX gap 1).
# D3: gear_loadout is ref-bearing HERE (it projects a cond_dep to its
# gear_loadout:* node so the loadout's item leaves enter the closure) AND is
# dynamically evaluated in atom_satisfied (recursed against current counts).
# Both are true — they are not in conflict.
_REF_BEARING_ATOMS: frozenset[AtomType] = frozenset(
    {
        AtomType.ITEM,
        AtomType.IS_UNLOCKED,
        AtomType.QUEST,
        AtomType.ACHIEVEMENT_DIARY,
        AtomType.COMBAT_ACHIEVEMENT,
        AtomType.KILL_COUNT,
        AtomType.GEAR_LOADOUT,
    }
)


class KGStore(ABC):
    """Read interface over the knowledge graph."""

    nodes: dict[str, Node]
    edges: list[Edge]
    groups: dict[int, ConditionGroup]

    @abstractmethod
    def node(self, node_id: str) -> Optional[Node]:
        """Return the Node for node_id, or None if not found."""
        ...

    @abstractmethod
    def children_of(self, group_id: int) -> list:
        """Return the children of the given condition group.

        Raises KeyError if group_id is not present (unlike node() which returns None).
        """
        ...

    @abstractmethod
    def composition_of(self, loadout_node_id: str) -> int:
        ...

    @abstractmethod
    def requires_dag(self) -> nx.MultiDiGraph:
        ...

    @abstractmethod
    def descendants(self, goal_id: str) -> set[str]:
        """Return all prerequisite nodes reachable from goal_id in the requires DAG.

        Raises networkx.exception.NetworkXError if goal_id is not in the graph.
        """
        ...

    @abstractmethod
    def topo_order(self, goal_id: str) -> list[str]:
        """Return the goal closure in prerequisite-first order (goal last).

        Raises networkx.exception.NetworkXError if goal_id is not in the graph.
        """
        ...

    @abstractmethod
    def find_cycles(self) -> list[list[str]]:
        ...


class InMemoryKGStore(KGStore):
    def __init__(
        self,
        nodes: list[Node],
        edges: list[Edge],
        groups: dict[int, ConditionGroup],
    ) -> None:
        self.nodes = {n.id: n for n in nodes}
        self.edges = list(edges)
        self.groups = dict(groups)

    def node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def children_of(self, group_id: int) -> list:
        return list(self.groups[group_id].children)

    def composition_of(self, loadout_node_id: str) -> int:
        for e in self.edges:
            if (
                e.type is EdgeType.REQUIRES
                and e.src == loadout_node_id
                and e.dst is None
                and e.cond_group is not None
            ):
                return e.cond_group
        raise KeyError(f"no composition cond_group for loadout {loadout_node_id!r}")

    def _iter_ref_leaves(self):
        """Yield (owner_src, ref_node, group_id) for every ref-bearing atom in any
        cond tree reachable from a requires edge. Walks groups recursively so atoms
        nested under sub-groups are projected too. (kg-schema-v1.md iter_ref_leaves.)"""
        # Map each cond_group id -> ALL requires-edge srcs that reference it.
        # Multiple distinct src nodes may share the same cond_group id; each must
        # get its own cond_dep edges projected (I1 fix: was setdefault → only kept
        # the first owner, silently dropping all subsequent ones).
        owner_of_group: dict[int, list[str]] = {}
        for e in self.edges:
            if e.type is EdgeType.REQUIRES and e.cond_group is not None:
                owner_of_group.setdefault(e.cond_group, []).append(e.src)

        def walk(group_id: int, owner: str, seen: frozenset[int] = frozenset()):
            # I2 fix: guard against cycles in condition-group children.
            if group_id in seen:
                raise ValueError(
                    f"cycle in condition groups at {group_id}"
                )
            seen = seen | {group_id}
            for child in self.groups[group_id].children:
                if isinstance(child, ConditionAtom):
                    if child.atom_type in _REF_BEARING_ATOMS and child.ref_node is not None:
                        yield owner, child.ref_node, group_id
                else:  # a sub-group id (int)
                    yield from walk(int(child), owner, seen)

        for gid, owners in owner_of_group.items():
            for owner in owners:
                yield from walk(gid, owner)

    def requires_dag(self) -> nx.MultiDiGraph:
        dag = nx.MultiDiGraph()
        dag.add_nodes_from(self.nodes.keys())
        # 1) hard prerequisite edges (a->b = a requires b); keep parallels + conditions
        for e in self.edges:
            if e.type is EdgeType.REQUIRES and e.dst is not None:
                dag.add_edge(e.src, e.dst, kind=EDGE_KIND_REQUIRES, cond_group=e.cond_group)
        # 1b) ref-bearing condition leaves -> cond_dep closure edges
        # Skip self-loops: an ITEM atom whose ref_node equals its owner (goal owns
        # itself) carries no topological dependency and must not form a cycle.
        for owner, ref_node, gid in self._iter_ref_leaves():
            if owner != ref_node:
                dag.add_edge(owner, ref_node, kind=EDGE_KIND_COND_DEP, cond_group=gid)
        return dag

    def descendants(self, goal_id: str) -> set[str]:
        return set(nx.descendants(self.requires_dag(), goal_id))

    def topo_order(self, goal_id: str) -> list[str]:
        dag = self.requires_dag()
        closure = {goal_id} | set(nx.descendants(dag, goal_id))
        sub = dag.subgraph(closure)
        return list(reversed(list(nx.topological_sort(sub))))

    def find_cycles(self) -> list[list[str]]:
        """Invariant I1: report all simple cycles of the requires_dag augmented with
        grant-flip synthetics. A 'grants' edge src->dst becomes a cycle-only synthetic
        dst->src (granted depends-on granter). cond_dep edges are already in the dag,
        so a tangle through a grant OR any ref-bearing atom is caught."""
        cyc = self.requires_dag().copy()
        for e in self.edges:
            if e.type is EdgeType.GRANTS and e.dst is not None:
                cyc.add_edge(e.dst, e.src, kind=EDGE_KIND_GRANT_SYNTHETIC)
        return [list(c) for c in nx.simple_cycles(cyc)]
