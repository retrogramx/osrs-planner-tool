"""Tests for engine/kg/json_store.py — JsonKGStore (K10).

Proves the kg/*.json serialized shapes (spec §5) round-trip through encode →
write → JsonKGStore.from_dir → identical engine dataclasses, and that a
condition group whose children mix an inline atom object and an int sub-group
id deserializes correctly (the int stays an int; the atom becomes a
ConditionAtom).
"""
from __future__ import annotations

import json

from osrs_planner.engine.kg.json_store import (
    JsonKGStore,
    edge_to_dict,
    group_to_dict,
    node_to_dict,
)
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


def _tiny_graph():
    nodes = [
        Node(id="quest:monkey-madness-i", kind=NodeKind.QUEST,
             name="Monkey Madness I", slug="monkey-madness-i", data={}),
        Node(id="quest:the-grand-tree", kind=NodeKind.QUEST,
             name="The Grand Tree", slug="the-grand-tree", data={"miniquest": False}),
        Node(id="skill:agility", kind=NodeKind.SKILL,
             name="Agility", slug="agility", data={}),
    ]
    groups = {
        4012: ConditionGroup(id=4012, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:agility",
                          threshold=25, qty=None, data={"boostable": True}),
            4013,
        ]),
        4013: ConditionGroup(id=4013, op=Op.OR, parent=4012, children=[
            ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, ref_node=None,
                          threshold=None, qty=None, data={"value": "main"}),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:agility",
                          threshold=25, qty=None, data={"boostable": True}),
        ]),
    }
    edges = [
        Edge(id=7001, type=EdgeType.REQUIRES, src="quest:monkey-madness-i",
             dst=None, cond_group=4012),
        Edge(id=7002, type=EdgeType.REQUIRES, src="quest:monkey-madness-i",
             dst="quest:the-grand-tree", cond_group=None),
    ]
    return nodes, edges, groups


def _write_kg(tmp_path, nodes, edges, groups):
    (tmp_path / "nodes.json").write_text(json.dumps([node_to_dict(n) for n in nodes], indent=2))
    (tmp_path / "edges.json").write_text(json.dumps([edge_to_dict(e) for e in edges], indent=2))
    (tmp_path / "condition_groups.json").write_text(
        json.dumps([group_to_dict(g) for g in groups.values()], indent=2))


def test_round_trip_equals(tmp_path):
    nodes, edges, groups = _tiny_graph()
    _write_kg(tmp_path, nodes, edges, groups)
    store = JsonKGStore.from_dir(str(tmp_path))
    assert store.nodes == {n.id: n for n in nodes}
    assert store.edges == edges
    assert store.groups == groups


def test_inline_atom_and_int_child(tmp_path):
    nodes, edges, groups = _tiny_graph()
    _write_kg(tmp_path, nodes, edges, groups)
    store = JsonKGStore.from_dir(str(tmp_path))
    children = store.children_of(4012)
    assert len(children) == 2
    atom = children[0]
    assert isinstance(atom, ConditionAtom)
    assert atom.atom_type is AtomType.SKILL_LEVEL
    assert atom.ref_node == "skill:agility"
    assert atom.threshold == 25
    assert atom.data == {"boostable": True}
    assert children[1] == 4013
    assert isinstance(children[1], int)
    sub = store.groups[4013]
    assert sub.op is Op.OR
    assert sub.parent == 4012
    assert len(sub.children) == 2
    assert isinstance(sub.children[0], ConditionAtom)
    assert sub.children[0].atom_type is AtomType.ACCOUNT_TYPE
    assert sub.children[0].data == {"value": "main"}


def test_delegates_store_interface(tmp_path):
    nodes, edges, groups = _tiny_graph()
    _write_kg(tmp_path, nodes, edges, groups)
    store = JsonKGStore.from_dir(str(tmp_path))
    assert store.node("skill:agility").name == "Agility"
    assert store.node("quest:does-not-exist") is None
    assert store.composition_of("quest:monkey-madness-i") == 4012
    dag = store.requires_dag()
    assert dag.has_edge("quest:monkey-madness-i", "quest:the-grand-tree")
    assert store.find_cycles() == []
