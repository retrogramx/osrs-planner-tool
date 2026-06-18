"""KG store interface + in-memory implementation.

KGStore is the read interface the future ingest brick will implement; the engine
only ever depends on this surface. InMemoryKGStore is built from plain lists of
Node/Edge/ConditionGroup (used by tests and the hand-authored fixture).
"""

from __future__ import annotations

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


class KGStore:
    """Read interface over the knowledge graph."""

    nodes: dict[str, Node]
    edges: list[Edge]
    groups: dict[int, ConditionGroup]

    def node(self, node_id: str) -> Optional[Node]:
        raise NotImplementedError

    def children_of(self, group_id: int) -> list:
        raise NotImplementedError

    def composition_of(self, loadout_node_id: str) -> int:
        raise NotImplementedError

    def requires_dag(self) -> nx.MultiDiGraph:
        raise NotImplementedError

    def descendants(self, goal_id: str) -> set[str]:
        raise NotImplementedError

    def topo_order(self, goal_id: str) -> list[str]:
        raise NotImplementedError

    def find_cycles(self) -> list[list[str]]:
        raise NotImplementedError


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
        # map each cond_group id -> the requires-edge src that owns its tree
        owner_of_group: dict[int, str] = {}
        for e in self.edges:
            if e.type is EdgeType.REQUIRES and e.cond_group is not None:
                owner_of_group.setdefault(e.cond_group, e.src)

        def walk(group_id: int, owner: str):
            for child in self.groups[group_id].children:
                if isinstance(child, ConditionAtom):
                    if child.atom_type in _REF_BEARING_ATOMS and child.ref_node is not None:
                        yield owner, child.ref_node, group_id
                else:  # a sub-group id (int)
                    yield from walk(int(child), owner)

        for gid, owner in owner_of_group.items():
            yield from walk(gid, owner)

    def requires_dag(self) -> nx.MultiDiGraph:
        dag = nx.MultiDiGraph()
        dag.add_nodes_from(self.nodes.keys())
        # 1) hard prerequisite edges (a->b = a requires b); keep parallels + conditions
        for e in self.edges:
            if e.type is EdgeType.REQUIRES and e.dst is not None:
                dag.add_edge(e.src, e.dst, kind="requires", cond_group=e.cond_group)
        # 1b) ref-bearing condition leaves -> 'cond_dep' closure edges
        for owner, ref_node, gid in self._iter_ref_leaves():
            dag.add_edge(owner, ref_node, kind="cond_dep", cond_group=gid)
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
                cyc.add_edge(e.dst, e.src, kind="grant_synthetic")
        return [list(c) for c in nx.simple_cycles(cyc)]
