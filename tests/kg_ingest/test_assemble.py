"""Tests for kg_ingest.assemble — merge builders, stable ids, dedup, write kg/*.json."""
from __future__ import annotations

import json
import pathlib

import pytest

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)


def test_stable_group_id_is_deterministic_and_domain_offset():
    from kg_ingest.assemble import stable_group_id
    a = stable_group_id("quest:dragon-slayer-i", 0)
    assert a == stable_group_id("quest:dragon-slayer-i", 0)
    assert 4_000_000 <= a < 6_000_000
    assert stable_group_id("quest:dragon-slayer-i", 1) != a
    assert stable_group_id("quest:monkey-madness-i", 0) != a


def test_stable_edge_id_is_deterministic_and_distinct_domain():
    from kg_ingest.assemble import stable_edge_id, stable_group_id
    e = stable_edge_id("quest:dragon-slayer-i", 0)
    assert e == stable_edge_id("quest:dragon-slayer-i", 0)
    assert 6_000_000 <= e < 8_000_000
    assert stable_edge_id("quest:x", 0) != stable_group_id("quest:x", 0)


def _toy_builder_output():
    node = Node(id="quest:toy", kind=NodeKind.QUEST, name="Toy", slug="toy", data={})
    leaf = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack",
                         threshold=60, data={"boostable": False})
    sub_leaf = ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:monkey-madness-i",
                             data={"state": "completed"})
    root = ConditionGroup(id=1, op=Op.AND, parent=None, children=[leaf, 2])
    sub = ConditionGroup(id=2, op=Op.OR, parent=1, children=[sub_leaf])
    edge = Edge(id=99, type=EdgeType.REQUIRES, src="quest:toy", dst=None, cond_group=1)
    return [node], [edge], {1: root, 2: sub}


def test_rekey_remaps_groups_and_edges_to_stable_ids():
    from kg_ingest.assemble import rekey, stable_edge_id, stable_group_id
    nodes, edges, groups = _toy_builder_output()
    out_nodes, out_edges, out_groups = rekey(nodes, edges, groups)
    assert out_nodes == nodes
    assert len(out_edges) == 1
    e = out_edges[0]
    assert e.id == stable_edge_id("quest:toy", 0)
    new_root_id = stable_group_id("quest:toy", 0)
    new_sub_id = stable_group_id("quest:toy", 1)
    assert e.cond_group == new_root_id
    assert set(out_groups) == {new_root_id, new_sub_id}
    root = out_groups[new_root_id]
    assert root.id == new_root_id and root.parent is None
    assert root.children == [
        ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack",
                      threshold=60, data={"boostable": False}),
        new_sub_id,
    ]
    sub = out_groups[new_sub_id]
    assert sub.id == new_sub_id and sub.parent == new_root_id


def test_rekey_raises_on_group_id_collision(monkeypatch):
    """A hash collision mapping two distinct local groups to the same global id must
    fail fast (not silently overwrite/drop a group). Force it by making
    stable_group_id return a CONSTANT for every input — the toy builder's root +
    sub groups then collide."""
    import kg_ingest.assemble as A
    monkeypatch.setattr(A, "stable_group_id", lambda owner, idx: 4_000_000)
    nodes, edges, groups = _toy_builder_output()
    with pytest.raises(ValueError, match="group id collision at 4000000"):
        A.rekey(nodes, edges, groups)


def test_rekey_raises_on_edge_id_collision(monkeypatch):
    """Two distinct edges re-keyed to the same global id must fail fast rather than
    silently overwrite. Force it by pinning stable_edge_id to a CONSTANT."""
    import kg_ingest.assemble as A
    node = Node(id="quest:toy", kind=NodeKind.QUEST, name="Toy", slug="toy", data={})
    e1 = Edge(id=10, type=EdgeType.REQUIRES, src="quest:toy", dst="skill:attack", cond_group=None)
    e2 = Edge(id=11, type=EdgeType.REQUIRES, src="quest:toy", dst="skill:strength", cond_group=None)
    monkeypatch.setattr(A, "stable_edge_id", lambda owner, idx: 6_000_000)
    with pytest.raises(ValueError, match="edge id collision at 6000000"):
        A.rekey([node], [e1, e2], {})


def test_rekey_is_deterministic_across_calls():
    from kg_ingest.assemble import rekey
    n1, e1, g1 = rekey(*_toy_builder_output())
    n2, e2, g2 = rekey(*_toy_builder_output())
    assert e1 == e2 and g1 == g2


def test_dedup_nodes_collapses_identical_ids():
    from kg_ingest.assemble import dedup_nodes
    a = Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={})
    a2 = Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={})
    b = Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength", data={})
    assert [n.id for n in dedup_nodes([a, a2, b])] == ["skill:attack", "skill:strength"]


def test_dedup_nodes_raises_on_conflicting_definitions():
    from kg_ingest.assemble import dedup_nodes
    a = Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={})
    bad = Node(id="skill:attack", kind=NodeKind.SKILL, name="ATK!", slug="attack", data={})
    with pytest.raises(ValueError, match="conflicting node definitions for 'skill:attack'"):
        dedup_nodes([a, bad])


def test_serialize_group_children_are_int_or_inline_atom():
    from kg_ingest.assemble import serialize_group, serialize_node
    n = Node(id="quest:toy", kind=NodeKind.QUEST, name="Toy", slug="toy", data={})
    assert serialize_node(n) == {"id": "quest:toy", "kind": "quest", "name": "Toy",
                                 "slug": "toy", "data": {}}
    leaf = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack",
                         threshold=60, qty=None, data={"boostable": False})
    g = ConditionGroup(id=4_000_123, op=Op.AND, parent=None, children=[leaf, 4_000_124])
    assert serialize_group(g) == {
        "id": 4_000_123, "op": "and", "parent": None,
        "children": [
            {"atom_type": "skill_level", "ref_node": "skill:attack", "threshold": 60,
             "qty": None, "data": {"boostable": False}},
            4_000_124,
        ],
    }


def test_serialize_edge():
    from kg_ingest.assemble import serialize_edge
    e = Edge(id=6_000_5, type=EdgeType.REQUIRES, src="quest:toy", dst=None, cond_group=4_000_123)
    assert serialize_edge(e) == {"id": 6_000_5, "type": "requires", "src": "quest:toy",
                                 "dst": None, "cond_group": 4_000_123, "data": {}}


def test_assemble_writes_three_files_and_is_byte_stable(tmp_path, monkeypatch):
    import kg_ingest.assemble as A
    out_dir = tmp_path / "kg"
    monkeypatch.setattr(A, "OUT_DIR", out_dir)
    A.assemble()
    nodes_p = out_dir / "nodes.json"
    edges_p = out_dir / "edges.json"
    groups_p = out_dir / "condition_groups.json"
    assert nodes_p.exists() and edges_p.exists() and groups_p.exists()
    nodes = json.loads(nodes_p.read_text())
    edges = json.loads(edges_p.read_text())
    groups = json.loads(groups_p.read_text())
    assert isinstance(nodes, list) and isinstance(edges, list) and isinstance(groups, list)
    assert len(nodes) > 200
    assert [n["id"] for n in nodes] == sorted(n["id"] for n in nodes)
    assert [e["id"] for e in edges] == sorted(e["id"] for e in edges)
    assert [g["id"] for g in groups] == sorted(g["id"] for g in groups)
    assert len({n["id"] for n in nodes}) == len(nodes)
    before = (nodes_p.read_bytes(), edges_p.read_bytes(), groups_p.read_bytes())
    A.assemble()
    after = (nodes_p.read_bytes(), edges_p.read_bytes(), groups_p.read_bytes())
    assert before == after


def test_assemble_output_loads_via_jsonkgstore(tmp_path, monkeypatch):
    import kg_ingest.assemble as A
    from osrs_planner.engine.kg.json_store import JsonKGStore
    out_dir = tmp_path / "kg"
    monkeypatch.setattr(A, "OUT_DIR", out_dir)
    A.assemble()
    store = JsonKGStore.from_dir(str(out_dir))
    assert store.node("quest:dragon-slayer-i") is not None
    assert store.find_cycles() == []


def test_committed_kg_matches_freshly_assembled(tmp_path, monkeypatch):
    """The committed kg/*.json MUST be byte-identical to a fresh assembler run.

    Without this, a builder edit that forgets to regenerate kg/*.json sails
    through the whole acceptance gate green (the validator + golden set read the
    STALE committed files). Re-run the assembler into a temp dir and byte-compare
    each output to the committed file; on drift, tell the dev exactly how to fix.
    """
    import kg_ingest.assemble as A
    out_dir = tmp_path / "kg"
    monkeypatch.setattr(A, "OUT_DIR", out_dir)
    A.assemble()
    # Resolve the committed kg/ dir the same way the assembler computes its real
    # OUT_DIR (repo-root/kg): assemble.py is kg_ingest/assemble.py, parents[1] = root.
    committed_dir = pathlib.Path(A.__file__).resolve().parents[1] / "kg"
    for fname in ("nodes.json", "edges.json", "condition_groups.json"):
        fresh_bytes = (out_dir / fname).read_bytes()
        committed_bytes = (committed_dir / fname).read_bytes()
        assert fresh_bytes == committed_bytes, (
            f"committed kg/{fname} is stale — regenerate with "
            f"`./venv/bin/python -m kg_ingest.assemble`"
        )
