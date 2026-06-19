"""Task 6: build_goals part 2 — Barrows gloves/RFD convergence, full Infinity
gear-set composition, Voidwaker multi-component assembly (K8)."""
from __future__ import annotations

import pytest

from kg_ingest.builders.goals import build_goals
from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, NodeKind, Op,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.conditions import evaluate
from osrs_planner.engine.kleene import Tri
from osrs_planner.engine.state import AccountState


@pytest.fixture(scope="module")
def built():
    return build_goals()


def _node(nodes, node_id):
    matches = [n for n in nodes if n.id == node_id]
    assert len(matches) == 1, f"expected exactly one {node_id!r}, got {len(matches)}"
    return matches[0]


def _requires_edge(edges, src):
    matches = [e for e in edges if e.type is EdgeType.REQUIRES and e.src == src
               and e.cond_group is not None]
    assert len(matches) == 1, f"expected one requires edge from {src!r}, got {len(matches)}"
    return matches[0]


def _atoms(group):
    return [c for c in group.children if isinstance(c, ConditionAtom)]


def test_barrows_gloves_node_exists(built):
    nodes, _, _ = built
    n = _node(nodes, "item:7462")
    assert n.kind is NodeKind.ITEM
    assert n.name == "Barrows gloves"
    assert n.slug == "barrows-gloves"


def test_barrows_gloves_requires_owned_item_and_rfd_completed(built):
    nodes, edges, groups = built
    root = groups[_requires_edge(edges, "item:7462").cond_group]
    assert root.op is Op.AND
    atoms = _atoms(root)
    item_atoms = [a for a in atoms if a.atom_type is AtomType.ITEM]
    quest_atoms = [a for a in atoms if a.atom_type is AtomType.QUEST]
    assert len(item_atoms) == 1 and item_atoms[0].ref_node == "item:7462"
    assert (item_atoms[0].qty or 1) == 1
    assert len(quest_atoms) == 1
    assert quest_atoms[0].ref_node == "quest:recipe-for-disaster"
    assert quest_atoms[0].data["state"] == "completed"


def test_barrows_gloves_does_not_recreate_rfd_quest_node(built):
    nodes, _, _ = built
    assert not any(n.id == "quest:recipe-for-disaster" for n in nodes)
