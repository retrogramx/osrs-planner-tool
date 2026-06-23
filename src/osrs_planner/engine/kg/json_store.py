"""JsonKGStore — load committed kg/*.json into engine dataclasses (K10).

Thin deserializer over the existing KGStore interface (spec §4). Reads the three
committed files produced by kg_ingest/assemble.py —
    nodes.json             list[node-dict]
    edges.json             list[edge-dict]
    condition_groups.json  list[group-dict]
— into Node / Edge / ConditionGroup / ConditionAtom and delegates every KGStore
query to an internal InMemoryKGStore (built from the loaded lists).

Serialized shapes (spec §5) — all enum fields are the enum .value string:
    node:  {"id","kind","name","slug","data"}
    edge:  {"id","type","src","dst","cond_group","data"}   (dst/cond_group may be null)
    group: {"id","op","parent","children"}          (parent may be null)
             children = list of (int sub-group id) | (inline atom-dict)
    atom:  {"atom_type","ref_node","threshold","qty","data"}

The kg_ingest assembler MUST import node_to_dict / edge_to_dict / group_to_dict / atom_to_dict from this module to write kg/*.json — do NOT re-implement the serialization shape (prevents encode/decode drift).
"""
from __future__ import annotations

import json
import os
from typing import Optional

import networkx as nx

from osrs_planner.engine.kg.model import (
    AtomType,
    ConditionAtom,
    ConditionGroup,
    Edge,
    EdgeType,
    Node,
    NodeKind,
    Op,
)
from osrs_planner.engine.kg.store import InMemoryKGStore, KGStore

NODES_FILE = "nodes.json"
EDGES_FILE = "edges.json"
GROUPS_FILE = "condition_groups.json"


# ---- encode (dataclass -> json-ready dict) ----
def atom_to_dict(atom: ConditionAtom) -> dict:
    return {"atom_type": atom.atom_type.value, "ref_node": atom.ref_node,
            "threshold": atom.threshold, "qty": atom.qty, "data": atom.data}


def node_to_dict(node: Node) -> dict:
    return {"id": node.id, "kind": node.kind.value, "name": node.name,
            "slug": node.slug, "data": node.data}


def edge_to_dict(edge: Edge) -> dict:
    return {"id": edge.id, "type": edge.type.value, "src": edge.src,
            "dst": edge.dst, "cond_group": edge.cond_group, "data": edge.data}


def group_to_dict(group: ConditionGroup) -> dict:
    children: list = []
    for child in group.children:
        if isinstance(child, ConditionAtom):
            children.append(atom_to_dict(child))
        else:
            children.append(int(child))
    return {"id": group.id, "op": group.op.value, "parent": group.parent,
            "children": children}


# ---- decode (json dict -> dataclass) ----
def atom_from_dict(d: dict) -> ConditionAtom:
    return ConditionAtom(atom_type=AtomType(d["atom_type"]), ref_node=d.get("ref_node"),
                         threshold=d.get("threshold"), qty=d.get("qty"),
                         data=d.get("data") or {})


def node_from_dict(d: dict) -> Node:
    return Node(id=d["id"], kind=NodeKind(d["kind"]), name=d["name"],
                slug=d["slug"], data=d.get("data") or {})


def edge_from_dict(d: dict) -> Edge:
    return Edge(id=d["id"], type=EdgeType(d["type"]), src=d["src"],
                dst=d.get("dst"), cond_group=d.get("cond_group"), data=d.get("data") or {})


def group_from_dict(d: dict) -> ConditionGroup:
    children: list[int | ConditionAtom] = []
    for child in d["children"]:
        if isinstance(child, dict):
            children.append(atom_from_dict(child))
        else:
            children.append(int(child))
    return ConditionGroup(id=int(d["id"]), op=Op(d["op"]),
                          parent=int(d["parent"]) if d.get("parent") is not None else None,
                          children=children)


class JsonKGStore(KGStore):
    """KGStore backed by committed kg/*.json; delegates queries to InMemory."""

    def __init__(self, nodes: list[Node], edges: list[Edge],
                 groups: dict[int, ConditionGroup]) -> None:
        self._inner = InMemoryKGStore(nodes, edges, groups)
        self.nodes = self._inner.nodes
        self.edges = self._inner.edges
        self.groups = self._inner.groups

    @classmethod
    def from_dir(cls, path: str) -> "JsonKGStore":
        with open(os.path.join(path, NODES_FILE), encoding="utf-8") as f:
            nodes = [node_from_dict(d) for d in json.load(f)]
        with open(os.path.join(path, EDGES_FILE), encoding="utf-8") as f:
            edges = [edge_from_dict(d) for d in json.load(f)]
        with open(os.path.join(path, GROUPS_FILE), encoding="utf-8") as f:
            groups = {g.id: g for g in (group_from_dict(d) for d in json.load(f))}
        return cls(nodes, edges, groups)

    def node(self, node_id: str) -> Optional[Node]:
        return self._inner.node(node_id)

    def children_of(self, group_id: int) -> list:
        return self._inner.children_of(group_id)

    def composition_of(self, loadout_node_id: str) -> int:
        return self._inner.composition_of(loadout_node_id)

    def requires_dag(self) -> nx.MultiDiGraph:
        return self._inner.requires_dag()

    def descendants(self, goal_id: str) -> set[str]:
        return self._inner.descendants(goal_id)

    def topo_order(self, goal_id: str) -> list[str]:
        return self._inner.topo_order(goal_id)

    def find_cycles(self) -> list[list[str]]:
        return self._inner.find_cycles()
