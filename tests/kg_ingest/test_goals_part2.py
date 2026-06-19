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


def test_barrows_gloves_requires_rfd_completed(built):
    # B2 no-self-loop: the requires group holds ONLY the quest atom (the prerequisite
    # for obtaining the item). A self-referential ITEM atom (ref_node == "item:7462"
    # on the item:7462 node) would create a cond_dep self-loop caught by find_cycles;
    # ownership is expressed by the item leaf node existing, not by a self-atom.
    nodes, edges, groups = built
    root = groups[_requires_edge(edges, "item:7462").cond_group]
    assert root.op is Op.AND
    atoms = _atoms(root)
    item_atoms = [a for a in atoms if a.atom_type is AtomType.ITEM]
    quest_atoms = [a for a in atoms if a.atom_type is AtomType.QUEST]
    # No self-referential item atom.
    assert len(item_atoms) == 0
    assert len(quest_atoms) == 1
    assert quest_atoms[0].ref_node == "quest:recipe-for-disaster"
    assert quest_atoms[0].data["state"] == "completed"


def test_barrows_gloves_does_not_recreate_rfd_quest_node(built):
    nodes, _, _ = built
    assert not any(n.id == "quest:recipe-for-disaster" for n in nodes)


# ---------------------------------------------------------------------------
# Full Infinity — canonical two-node Void pattern (B2/B3)
# ---------------------------------------------------------------------------
INFINITY_PIECES = ["item:6918", "item:6916", "item:6924", "item:6922", "item:6920"]
INFINITY_LOADOUT = "gear_loadout:infinity"
INFINITY_GOAL = "gear_loadout_goal:infinity"


def _dst_none_requires(edges, src):
    return [e for e in edges if e.type is EdgeType.REQUIRES and e.src == src
            and e.dst is None and e.cond_group is not None]


def test_infinity_loadout_node_exists(built):
    nodes, _, _ = built
    n = _node(nodes, INFINITY_LOADOUT)
    assert n.kind is NodeKind.GEAR_LOADOUT
    assert n.name == "Full Infinity"
    assert n.slug == "infinity"


def test_infinity_loadout_node_has_exactly_one_composition_edge(built):
    # B3 invariant: the loadout node owns EXACTLY ONE dst=None requires edge (its
    # composition), so composition_of is unambiguous regardless of id sort order.
    _n, edges, _g = built
    assert len(_dst_none_requires(edges, INFINITY_LOADOUT)) == 1


def test_infinity_composition_is_and_of_five_piece_items(built):
    nodes, edges, groups = built
    store = InMemoryKGStore(nodes, edges, groups)
    comp = groups[store.composition_of(INFINITY_LOADOUT)]
    assert comp.op is Op.AND
    item_atoms = _atoms(comp)
    assert all(a.atom_type is AtomType.ITEM for a in item_atoms)
    assert sorted(a.ref_node for a in item_atoms) == sorted(INFINITY_PIECES)
    assert all((a.qty or 1) == 1 for a in item_atoms)
    # the loadout node carries NO gear_loadout atom and NO skill atoms (B2).
    assert all(a.atom_type is AtomType.ITEM for a in item_atoms)


def test_infinity_wield_goal_node_exists(built):
    nodes, _, _ = built
    g = _node(nodes, INFINITY_GOAL)
    assert g.kind is NodeKind.GEAR_LOADOUT
    assert g.name == "Wielding full Infinity"


def test_infinity_wield_gate_lives_on_goal_node_referencing_the_loadout(built):
    # B2: the wield gate is on a SEPARATE node and references the loadout node, so
    # there is no self-loop. cond_group = AND(gear_loadout atom, 50 Magic, 25 Def).
    nodes, edges, groups = built
    wield_edges = _dst_none_requires(edges, INFINITY_GOAL)
    assert len(wield_edges) == 1
    g = groups[wield_edges[0].cond_group]
    assert g.op is Op.AND
    by_type: dict = {}
    for a in _atoms(g):
        by_type.setdefault(a.atom_type, []).append(a)
    assert len(by_type[AtomType.GEAR_LOADOUT]) == 1
    assert by_type[AtomType.GEAR_LOADOUT][0].ref_node == INFINITY_LOADOUT
    skills = {a.ref_node: a.threshold for a in by_type[AtomType.SKILL_LEVEL]}
    assert skills == {"skill:magic": 50, "skill:defence": 25}


def test_infinity_wield_goal_resolves_composition_via_loadout_node(built):
    # The gear_loadout atom on the goal node re-evaluates the loadout's composition
    # against live counts (engine D3) — owning all 5 pieces satisfies the gate.
    nodes, edges, groups = built
    store = InMemoryKGStore(nodes, edges, groups)
    gate_id = _dst_none_requires(edges, INFINITY_GOAL)[0].cond_group
    owns_all = AccountState(mode="main",
                            counts={p: 1 for p in INFINITY_PIECES},
                            levels={"skill:magic": 50, "skill:defence": 25},
                            observable_families={"item", "skill_level"})
    assert evaluate(gate_id, owns_all, store) is Tri.TRUE
    missing_boots = AccountState(mode="main",
                                 counts={p: 1 for p in INFINITY_PIECES if p != "item:6920"},
                                 levels={"skill:magic": 50, "skill:defence": 25},
                                 observable_families={"item", "skill_level"})
    assert evaluate(gate_id, missing_boots, store) is Tri.FALSE


def test_infinity_no_self_loop_acyclic(built):
    # B2: with the two-node model the requires-graph stays acyclic.
    nodes, edges, groups = built
    store = InMemoryKGStore(nodes, edges, groups)
    assert store.find_cycles() == []


def test_infinity_composition_evaluates_against_live_counts(built):
    nodes, edges, groups = built
    store = InMemoryKGStore(nodes, edges, groups)
    comp_id = store.composition_of(INFINITY_LOADOUT)
    owns_all = AccountState(mode="main", counts={p: 1 for p in INFINITY_PIECES},
                            observable_families={"item"})
    assert evaluate(comp_id, owns_all, store) is Tri.TRUE
    missing_boots = AccountState(mode="main",
                                 counts={p: 1 for p in INFINITY_PIECES if p != "item:6920"},
                                 observable_families={"item"})
    assert evaluate(comp_id, missing_boots, store) is Tri.FALSE
