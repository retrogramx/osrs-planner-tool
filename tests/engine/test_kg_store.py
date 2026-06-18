import networkx as nx
import pytest

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


def _tiny_store() -> InMemoryKGStore:
    """A 3-node graph: a boss requires an access (hard requires edge),
    and the access is gated by a dst=NULL requires edge whose cond tree
    has one ref-bearing leaf (a quest) -> a cond_dep edge in the DAG."""
    nodes = [
        Node(id="npc:1", kind=NodeKind.MONSTER, name="Boss", slug="boss"),
        Node(id="access:a", kind=NodeKind.ACCESS, name="A Access", slug="a"),
        Node(id="quest:q", kind=NodeKind.QUEST, name="A Quest", slug="q"),
    ]
    # group 1: AND( quest(quest:q, completed) ) — the access's pure-condition tree
    groups = {
        1: ConditionGroup(
            id=1,
            op=Op.AND,
            parent=None,
            children=[
                ConditionAtom(
                    atom_type=AtomType.QUEST,
                    ref_node="quest:q",
                    data={"state": "completed"},
                )
            ],
        ),
    }
    edges = [
        # boss --requires--> access  (hard prerequisite)
        Edge(id=1, type=EdgeType.REQUIRES, src="npc:1", dst="access:a"),
        # access --requires--> NULL, constraint IS the cond tree (group 1)
        Edge(id=2, type=EdgeType.REQUIRES, src="access:a", dst=None, cond_group=1),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


def test_inmemory_store_holds_collections_and_node_lookup():
    kg = _tiny_store()
    assert isinstance(kg, KGStore)
    assert set(kg.nodes.keys()) == {"npc:1", "access:a", "quest:q"}
    assert len(kg.edges) == 2
    assert set(kg.groups.keys()) == {1}
    assert kg.node("npc:1").name == "Boss"
    assert kg.node("nope") is None


def test_children_of_returns_group_children():
    kg = _tiny_store()
    children = kg.children_of(1)
    assert len(children) == 1
    atom = children[0]
    assert isinstance(atom, ConditionAtom)
    assert atom.atom_type == AtomType.QUEST
    assert atom.ref_node == "quest:q"


def _loadout_store() -> InMemoryKGStore:
    """A gear_loadout node carrying its composition on a dst=NULL requires edge."""
    nodes = [
        Node(id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Void", slug="void"),
        Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top"),
    ]
    groups = {
        10: ConditionGroup(
            id=10,
            op=Op.AND,
            parent=None,
            children=[ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839")],
        ),
    }
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src="gear_loadout:void", dst=None, cond_group=10),
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


def test_composition_of_returns_loadout_cond_group_id():
    kg = _loadout_store()
    assert kg.composition_of("gear_loadout:void") == 10


def test_requires_dag_has_requires_edge_and_cond_dep_edge():
    kg = _tiny_store()
    dag = kg.requires_dag()
    assert isinstance(dag, nx.MultiDiGraph)
    assert set(dag.nodes) == {"npc:1", "access:a", "quest:q"}

    # hard requires: npc:1 -> access:a (a->b = a requires b)
    req = [d for _, _, d in dag.out_edges("npc:1", data=True)]
    assert any(d.get("kind") == "requires" for d in req)
    assert dag.has_edge("npc:1", "access:a")

    # ref-bearing cond leaf: access:a (dst=NULL requires, group 1) -> quest:q
    assert dag.has_edge("access:a", "quest:q")
    cond = [d for _, _, d in dag.out_edges("access:a", data=True)]
    assert any(d.get("kind") == "cond_dep" for d in cond)


def test_requires_dag_preserves_parallel_edges():
    # two parallel requires edges with distinct cond_groups must both survive
    nodes = [
        Node(id="a", kind=NodeKind.ACTIVITY, name="A", slug="a"),
        Node(id="b", kind=NodeKind.SKILL, name="B", slug="b"),
    ]
    groups = {
        1: ConditionGroup(id=1, op=Op.AND, parent=None, children=[]),
        2: ConditionGroup(id=2, op=Op.AND, parent=None, children=[]),
    }
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src="a", dst="b", cond_group=1),
        Edge(id=2, type=EdgeType.REQUIRES, src="a", dst="b", cond_group=2),
    ]
    kg = InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)
    dag = kg.requires_dag()
    assert dag.number_of_edges("a", "b") == 2


def test_descendants_is_full_prereq_closure():
    kg = _tiny_store()
    # npc:1 -> access:a -> quest:q  => closure of npc:1 is {access:a, quest:q}
    assert kg.descendants("npc:1") == {"access:a", "quest:q"}
    assert kg.descendants("access:a") == {"quest:q"}
    assert kg.descendants("quest:q") == set()


def test_topo_order_lists_prereqs_before_goal():
    kg = _tiny_store()
    order = kg.topo_order("npc:1")
    assert set(order) == {"npc:1", "access:a", "quest:q"}
    # D1: a->b means a requires b, so b (the prereq) must come BEFORE a in
    # completion order. reversed(topological_sort) yields prereqs first, goal last.
    assert order.index("quest:q") < order.index("access:a")
    assert order.index("access:a") < order.index("npc:1")


def test_find_cycles_empty_for_acyclic_graph():
    kg = _tiny_store()
    assert kg.find_cycles() == []


def test_find_cycles_detects_requires_loop():
    nodes = [
        Node(id="x", kind=NodeKind.ACCESS, name="X", slug="x"),
        Node(id="y", kind=NodeKind.ACCESS, name="Y", slug="y"),
    ]
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src="x", dst="y"),
        Edge(id=2, type=EdgeType.REQUIRES, src="y", dst="x"),
    ]
    kg = InMemoryKGStore(nodes=nodes, edges=edges, groups={})
    cycles = kg.find_cycles()
    assert cycles  # non-empty
    assert {"x", "y"} <= set().union(*[set(c) for c in cycles])


def test_find_cycles_detects_grant_flip_tangle():
    # access:g granted by quest:p, but quest:p requires access:g -> a cycle
    # ONLY through the grant-flip synthetic (I1's reason to augment the graph).
    nodes = [
        Node(id="access:g", kind=NodeKind.ACCESS, name="G", slug="g"),
        Node(id="quest:p", kind=NodeKind.QUEST, name="P", slug="p"),
    ]
    edges = [
        Edge(id=1, type=EdgeType.GRANTS, src="quest:p", dst="access:g"),
        Edge(id=2, type=EdgeType.REQUIRES, src="quest:p", dst="access:g"),
    ]
    kg = InMemoryKGStore(nodes=nodes, edges=edges, groups={})
    # requires alone is acyclic (quest:p -> access:g); the grant flip
    # (access:g -> quest:p) closes the loop, which I1 must catch.
    cycles = kg.find_cycles()
    assert cycles


def test_requires_dag_gear_loadout_enters_closure():
    """D3 projection rule: a GEAR_LOADOUT ref-bearing atom must project a cond_dep
    edge to its gear_loadout:* node AND the loadout's own composition edge (a dst=None
    REQUIRES edge) causes its item leaves to enter the requires closure.

    Chain: activity:boss --cond_dep--> gear_loadout:void --cond_dep--> item:8839
    Both gear_loadout:void and item:8839 must appear in descendants("activity:boss").
    """
    nodes = [
        Node(id="activity:boss", kind=NodeKind.ACTIVITY, name="Boss", slug="boss"),
        Node(id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Void", slug="void"),
        Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top"),
    ]
    # group 20: activity's condition tree — requires the void loadout
    # group 10: gear_loadout:void's composition — contains one item leaf (reuse from _loadout_store style)
    groups = {
        20: ConditionGroup(
            id=20,
            op=Op.AND,
            parent=None,
            children=[
                ConditionAtom(
                    atom_type=AtomType.GEAR_LOADOUT,
                    ref_node="gear_loadout:void",
                )
            ],
        ),
        10: ConditionGroup(
            id=10,
            op=Op.AND,
            parent=None,
            children=[ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839")],
        ),
    }
    edges = [
        # activity has a pure-condition requires edge (dst=None) pointing at group 20
        Edge(id=1, type=EdgeType.REQUIRES, src="activity:boss", dst=None, cond_group=20),
        # gear_loadout:void's composition edge — dst=None, cond_group is its item list
        Edge(id=2, type=EdgeType.REQUIRES, src="gear_loadout:void", dst=None, cond_group=10),
    ]
    kg = InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)
    dag = kg.requires_dag()

    # cond_dep edge from activity to the gear_loadout node must exist
    assert dag.has_edge("activity:boss", "gear_loadout:void"), (
        "requires_dag must project a cond_dep edge from activity:boss to gear_loadout:void"
    )
    cond_out = [d for _, _, d in dag.out_edges("activity:boss", data=True)]
    assert any(d.get("kind") == "cond_dep" for d in cond_out), (
        "the edge from activity:boss to gear_loadout:void must carry kind='cond_dep'"
    )

    # the loadout's item leaf must also enter the closure via the loadout's own
    # composition requires edge (gear_loadout:void -> item:8839 as cond_dep)
    closure = kg.descendants("activity:boss")
    assert "gear_loadout:void" in closure, (
        "gear_loadout:void must be in the requires closure of activity:boss"
    )
    assert "item:8839" in closure, (
        "item:8839 (loadout leaf) must enter the requires closure of activity:boss"
    )


def test_requires_dag_shared_cond_group_projects_for_all_owners():
    """I1: two REQUIRES edges from DIFFERENT src nodes referencing the SAME cond_group
    id must BOTH get their cond_dep edges projected.  The old setdefault(gid, src)
    silently dropped the second owner."""
    nodes = [
        Node(id="npc:1", kind=NodeKind.MONSTER, name="Boss1", slug="boss1"),
        Node(id="npc:2", kind=NodeKind.MONSTER, name="Boss2", slug="boss2"),
        Node(id="item:x", kind=NodeKind.ITEM, name="Item X", slug="item-x"),
    ]
    # A single cond_group containing one ref-bearing ITEM atom
    groups = {
        99: ConditionGroup(
            id=99,
            op=Op.AND,
            parent=None,
            children=[ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:x")],
        ),
    }
    edges = [
        # Both npc:1 AND npc:2 reference the same cond_group=99
        Edge(id=1, type=EdgeType.REQUIRES, src="npc:1", dst=None, cond_group=99),
        Edge(id=2, type=EdgeType.REQUIRES, src="npc:2", dst=None, cond_group=99),
    ]
    kg = InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)
    dag = kg.requires_dag()

    assert dag.has_edge("npc:1", "item:x"), (
        "cond_dep edge from npc:1 to item:x must be projected"
    )
    assert dag.has_edge("npc:2", "item:x"), (
        "cond_dep edge from npc:2 to item:x must be projected (was silently dropped)"
    )


def test_iter_ref_leaves_raises_on_condition_group_cycle():
    """I2: a cycle in condition-group children (group 1 -> group 2 -> group 1)
    must raise ValueError, NOT recurse infinitely into RecursionError."""
    nodes = [
        Node(id="npc:1", kind=NodeKind.MONSTER, name="Boss", slug="boss"),
    ]
    # group 1 children include group 2; group 2 children include group 1 -> cycle
    groups = {
        1: ConditionGroup(id=1, op=Op.AND, parent=None, children=[2]),
        2: ConditionGroup(id=2, op=Op.AND, parent=None, children=[1]),
    }
    edges = [
        Edge(id=1, type=EdgeType.REQUIRES, src="npc:1", dst=None, cond_group=1),
    ]
    kg = InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)

    with pytest.raises(ValueError, match="cycle"):
        kg.requires_dag()
