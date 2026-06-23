"""Schema round-trip + inertness for the reward edge/node types (quest-foundation Task 2)."""
from osrs_planner.engine.kg.model import (
    Edge, EdgeType, Node, NodeKind, ConditionGroup, ConditionAtom, AtomType, Op,
)
from osrs_planner.engine.kg.json_store import edge_to_dict, edge_from_dict, node_from_dict, node_to_dict
from osrs_planner.engine.kg.store import InMemoryKGStore


def test_new_enum_values_exist():
    assert EdgeType.EFFECT.value == "effect"
    assert EdgeType.PROGRESS_TOWARDS.value == "progress_towards"
    assert NodeKind.GOAL.value == "goal"


def test_edge_data_round_trips():
    e = Edge(id=1, type=EdgeType.GRANTS, src="quest:x", dst="skill:attack",
             cond_group=None, data={"reward": "xp", "form": "fixed", "amount": 13750})
    d = edge_to_dict(e)
    assert d["data"] == {"reward": "xp", "form": "fixed", "amount": 13750}
    assert edge_from_dict(d) == e


def test_edge_without_data_key_decodes_to_empty_dict():
    # Pre-Task-2 committed edges have no "data" key; they must load as data={}.
    legacy = {"id": 9, "type": "requires", "src": "quest:b", "dst": None, "cond_group": None}
    assert edge_from_dict(legacy).data == {}


def test_goal_node_round_trips():
    d = {"id": "goal:quest-point-cape", "kind": "goal", "name": "Quest point cape",
         "slug": "quest-point-cape", "data": {"counter_type": "points", "thresholds": [33]}}
    n = node_from_dict(d)
    assert n.kind is NodeKind.GOAL and n.data["thresholds"] == [33]
    assert node_to_dict(node_from_dict(d)) == d


def test_effect_edges_are_inert_to_cycle_detection():
    # An EFFECT edge (src=item, dst=None) must not break find_cycles().
    nodes = [Node(id="item:99", kind=NodeKind.ITEM, name="Item99", slug="99")]
    edges = [Edge(id=1, type=EdgeType.EFFECT, src="item:99", dst=None,
                  cond_group=None, data={"effect_kind": "stat_multiplier"})]
    store = InMemoryKGStore(nodes, edges, {})
    assert store.find_cycles() == []


def test_supersedes_enum_exists_and_is_inert():
    from osrs_planner.engine.kg.model import EdgeType, Edge, Node, NodeKind
    from osrs_planner.engine.kg.store import InMemoryKGStore
    assert EdgeType.SUPERSEDES.value == "supersedes"
    nodes = [Node(id="item:1", kind=NodeKind.ITEM, name="A", slug="1"),
             Node(id="item:2", kind=NodeKind.ITEM, name="B", slug="2")]
    edges = [Edge(id=1, type=EdgeType.SUPERSEDES, src="item:2", dst="item:1", cond_group=None, data={})]
    assert InMemoryKGStore(nodes, edges, {}).find_cycles() == []


def test_progress_towards_edges_are_inert_to_cycle_detection():
    # A goal node + a progress_towards edge from a quest must not break find_cycles().
    nodes = [Node(id="quest:x", kind=NodeKind.QUEST, name="X", slug="x"),
             Node(id="goal:quest-point-cape", kind=NodeKind.GOAL, name="QP cape",
                  slug="quest-point-cape", data={"counter_type": "points", "thresholds": [2]})]
    edges = [Edge(id=1, type=EdgeType.PROGRESS_TOWARDS, src="quest:x",
                  dst="goal:quest-point-cape", cond_group=None, data={"weight": 1})]
    store = InMemoryKGStore(nodes, edges, {})
    assert store.find_cycles() == []
