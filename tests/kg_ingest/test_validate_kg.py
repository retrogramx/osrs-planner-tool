"""Tests for data/validate_kg.py — the KG invariant + completeness guard (spec §7)."""
import importlib.util
import json
import os

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from osrs_planner.engine.kg.store import InMemoryKGStore

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_VK_PATH = os.path.join(_ROOT, "data", "validate_kg.py")
_spec = importlib.util.spec_from_file_location("validate_kg", _VK_PATH)
validate_kg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_kg)


def _quests_data(names):
    return {
        "_provenance": {
            "accessed": "2026-06-17T18:18:04Z",
            "completeness": {"universe_count": len(names), "known_missing": []},
        },
        "records": [{"name": n, "node_type": "quest"} for n in names],
        "_excluded": [],
    }


def _good_store():
    nodes = [
        Node(id="quest:a", kind=NodeKind.QUEST, name="A", slug="a", data={}),
        Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={}),
        Node(id="skill:agility", kind=NodeKind.SKILL, name="Agility", slug="agility", data={}),
    ]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:a", threshold=None,
                          qty=None, data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:agility",
                          threshold=25, qty=None, data={"boostable": False}),
        ]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    return InMemoryKGStore(nodes, edges, groups), ["A", "B"]


def test_good_store_has_no_violations():
    store, names = _good_store()
    assert validate_kg.check_kg(store, _quests_data(names)) == []


def test_dangling_ref_node_is_flagged():
    # R2: construct the broken atom directly — Node/Edge/ConditionGroup/ConditionAtom
    # are FROZEN dataclasses, so mutating an existing instance raises FrozenInstanceError.
    nodes = [
        Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={}),
    ]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:nonexistent",
                          threshold=None, qty=None, data={"state": "completed"}),
        ]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    store = InMemoryKGStore(nodes, edges, groups)
    violations = validate_kg.check_kg(store, _quests_data(["B"]))
    assert any("quest:nonexistent" in v and "ref_node" in v for v in violations), violations


def _store_with(nodes, edges, groups):
    return InMemoryKGStore(nodes, edges, groups)


def test_invalid_atom_type_is_flagged():
    # R2: build the atom with a bogus atom_type at construction (string, not enum).
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type="not_a_real_atom", ref_node=None,
                          threshold=None, qty=None, data={}),
        ]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    v = validate_kg.check_kg(_store_with(nodes, edges, groups), _quests_data(["B"]))
    assert any("invalid atom_type" in x and "not_a_real_atom" in x for x in v), v


def test_invalid_node_kind_is_flagged():
    # R2: build the node with a bogus kind at construction (string, not NodeKind).
    nodes = [
        Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={}),
        Node(id="skill:agility", kind="bogus_kind", name="Agility", slug="agility", data={}),
    ]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:agility",
                          threshold=25, qty=None, data={"boostable": False}),
        ]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    v = validate_kg.check_kg(_store_with(nodes, edges, groups), _quests_data(["B"]))
    assert any("invalid kind" in x and "bogus_kind" in x for x in v), v


def test_not_group_with_two_children_is_flagged():
    # A NOT group with two children, constructed directly and rooted via a fresh
    # AND group's child list (list construction, not frozen-attr mutation).
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[4002]),
        4002: ConditionGroup(id=4002, op=Op.NOT, parent=4001, children=[
            ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, ref_node=None, threshold=None,
                          qty=None, data={"value": "ironman"}),
            ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, ref_node=None, threshold=None,
                          qty=None, data={"value": "uim"}),
        ]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    v = validate_kg.check_kg(_store_with(nodes, edges, groups), _quests_data(["B"]))
    assert any("NOT group 4002" in x and "must be exactly 1" in x for x in v), v


def test_dangling_edge_cond_group_is_flagged():
    # R2: build the edge pointing at a missing group id at construction.
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=9999)]
    v = validate_kg.check_kg(_store_with(nodes, edges, {}), _quests_data(["B"]))
    assert any("edge 7001 cond_group 9999" in x for x in v), v


def test_dangling_sub_group_child_is_flagged():
    # An int sub-group child pointing at a missing group; built into the child list.
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[8888]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    v = validate_kg.check_kg(_store_with(nodes, edges, groups), _quests_data(["B"]))
    assert any("sub-group child 8888" in x for x in v), v


def test_orphan_group_is_flagged():
    # An extra group unreferenced by any edge or parent, added at construction.
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[]),
        4050: ConditionGroup(id=4050, op=Op.AND, parent=None, children=[]),  # orphan
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    v = validate_kg.check_kg(_store_with(nodes, edges, groups), _quests_data(["B"]))
    assert any("group 4050 is unreferenced" in x for x in v), v


def test_duplicate_node_id_is_flagged_in_raw_list():
    # M4 / spec §7.4: a duplicate id in the RAW serialized nodes.json list must be
    # flagged even though JsonKGStore collapses duplicates into a dict. check_kg takes
    # an optional raw_node_dicts list; pass two dicts sharing an id.
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    edges = []
    raw = [
        {"id": "quest:b", "kind": "quest", "name": "B", "slug": "b", "data": {}},
        {"id": "quest:b", "kind": "quest", "name": "B (dup)", "slug": "b", "data": {}},
    ]
    v = validate_kg.check_kg(_store_with(nodes, edges, {}), _quests_data(["B"]),
                              raw_node_dicts=raw)
    assert any("duplicate node id" in x and "quest:b" in x for x in v), v


def test_gear_loadout_must_have_exactly_one_composition_edge():
    # B3 invariant (spec §7.4): every gear_loadout:* node has EXACTLY ONE dst=None
    # requires edge (its composition). Two such edges must be flagged.
    nodes = [
        Node(id="gear_loadout:x", kind=NodeKind.GEAR_LOADOUT, name="X", slug="x", data={}),
        Node(id="item:1", kind=NodeKind.ITEM, name="One", slug="1", data={}),
    ]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:1", qty=1)]),
        4002: ConditionGroup(id=4002, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:1", qty=1)]),
    }
    edges = [
        Edge(id=7001, type=EdgeType.REQUIRES, src="gear_loadout:x", dst=None, cond_group=4001),
        Edge(id=7002, type=EdgeType.REQUIRES, src="gear_loadout:x", dst=None, cond_group=4002),
    ]
    v = validate_kg.check_kg(_store_with(nodes, edges, groups), _quests_data([]))
    assert any("gear_loadout:x" in x and "composition" in x and "exactly 1" in x for x in v), v


def test_genuinely_missing_quest_is_flagged_but_known_missing_is_not():
    store, _ = _good_store()
    data = _quests_data(["A", "B"])
    data["records"].append({"name": "C", "node_type": "quest"})
    data["_provenance"]["completeness"]["universe_count"] = 3
    v = validate_kg.check_kg(store, data)
    assert any("[completeness]" in x and "C" in x for x in v), v
    data["_provenance"]["completeness"]["known_missing"] = ["C"]
    v2 = validate_kg.check_kg(store, data)
    assert not any("[completeness]" in x and "missing from KG" in x for x in v2), v2


def test_universe_count_mismatch_is_flagged():
    store, _ = _good_store()
    data = _quests_data(["A", "B"])
    data["_provenance"]["completeness"]["universe_count"] = 99
    v = validate_kg.check_kg(store, data)
    assert any("universe_count 99" in x and "drift" in x for x in v), v


# --- Amendment (A): known_missing dangling quest ref → warn+pass; non-known-missing → fatal ---

def test_known_missing_quest_ref_is_a_warning_not_error():
    """A dangling quest:* ref_node whose slug is in known_missing → non-fatal [known-gap] warn."""
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[
            # quest:architectural-alliance is a real known-gap slug
            ConditionAtom(atom_type=AtomType.QUEST,
                          ref_node="quest:architectural-alliance",
                          threshold=None, qty=None, data={"state": "completed"}),
        ]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    store = _store_with(nodes, edges, groups)
    data = _quests_data(["B"])
    data["_provenance"]["completeness"]["known_missing"] = ["Architectural Alliance"]
    violations = validate_kg.check_kg(store, data)
    # Must NOT be a fatal [ref] error
    assert not any("[ref]" in v and "quest:architectural-alliance" in v for v in violations), violations
    # Must emit a [known-gap] warning — returned separately
    warnings = validate_kg.check_kg_warnings(store, data)
    assert any("[known-gap]" in w and "quest:architectural-alliance" in w for w in warnings), warnings


def test_non_known_missing_dangling_quest_ref_is_fatal():
    """A dangling quest:* ref_node NOT in known_missing → fatal [ref] error."""
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST,
                          ref_node="quest:completely-unknown",
                          threshold=None, qty=None, data={"state": "completed"}),
        ]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    store = _store_with(nodes, edges, groups)
    data = _quests_data(["B"])
    data["_provenance"]["completeness"]["known_missing"] = ["Architectural Alliance"]
    violations = validate_kg.check_kg(store, data)
    assert any("[ref]" in v and "quest:completely-unknown" in v for v in violations), violations


# --- Amendment (B): diary records flagged as [diary] warning ---

def test_diary_records_in_quests_data_emit_diary_warning():
    """Quests.json records with node_type=='diary' must emit a [diary] warning."""
    store, _ = _good_store()
    data = _quests_data(["A", "B"])
    # Inject two stray diary records (mirroring the real 8 in data/quests.json)
    data["records"].append({"name": "Easy Ardougne Diary", "node_type": "diary"})
    data["records"].append({"name": "Medium Ardougne Diary", "node_type": "diary"})
    data["_provenance"]["completeness"]["universe_count"] = 4
    warnings = validate_kg.check_kg_warnings(store, data)
    assert any("[diary]" in w and "Easy Ardougne Diary" in w for w in warnings), warnings
    assert any("[diary]" in w and "Medium Ardougne Diary" in w for w in warnings), warnings


# --- Amendment (C): global edge/group integer-id uniqueness ---

def test_duplicate_edge_id_is_flagged_in_raw_list():
    """Amendment C: duplicate edge ids in the raw kg/edges.json list are fatal."""
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=None)]
    raw_edges = [
        {"id": 7001, "type": "requires", "src": "quest:b", "dst": None, "cond_group": None},
        {"id": 7001, "type": "requires", "src": "quest:b", "dst": None, "cond_group": None},
    ]
    v = validate_kg.check_kg(_store_with(nodes, edges, {}), _quests_data(["B"]),
                              raw_edge_dicts=raw_edges)
    assert any("duplicate edge id" in x and "7001" in x for x in v), v


def test_duplicate_group_id_is_flagged_in_raw_list():
    """Amendment C: duplicate group ids in the raw kg/condition_groups.json list are fatal."""
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    groups = {
        4001: ConditionGroup(id=4001, op=Op.AND, parent=None, children=[]),
    }
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=4001)]
    raw_groups = [
        {"id": 4001, "op": "and", "parent": None, "children": []},
        {"id": 4001, "op": "and", "parent": None, "children": []},
    ]
    v = validate_kg.check_kg(_store_with(nodes, edges, groups), _quests_data(["B"]),
                              raw_group_dicts=raw_groups)
    assert any("duplicate group id" in x and "4001" in x for x in v), v


# --- Acyclicity (I1): genuine-cycle path + amendment-E find_cycles()-raised except path ---

def test_genuine_requires_cycle_is_flagged():
    # Branch (a): two REQUIRES edges form a real cycle (quest:a -> quest:b -> quest:a).
    # find_cycles() returns normally and the normal path appends an [acyclic] violation
    # naming the cycle members. R2: edges built directly (frozen dataclasses).
    nodes = [
        Node(id="quest:a", kind=NodeKind.QUEST, name="A", slug="a", data={}),
        Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={}),
    ]
    edges = [
        Edge(id=7001, type=EdgeType.REQUIRES, src="quest:a", dst="quest:b", cond_group=None),
        Edge(id=7002, type=EdgeType.REQUIRES, src="quest:b", dst="quest:a", cond_group=None),
    ]
    v = validate_kg.check_kg(_store_with(nodes, edges, {}), _quests_data(["A", "B"]))
    assert any("[acyclic]" in x and "cycle" in x for x in v), v
    assert any("[acyclic]" in x and "quest:a" in x and "quest:b" in x for x in v), v


def test_dangling_group_ref_makes_find_cycles_raise_and_is_caught():
    # Branch (b) / amendment E: a REQUIRES edge points at a cond_group id that does not
    # exist, so find_cycles() (via requires_dag -> _iter_ref_leaves -> self.groups[gid])
    # raises KeyError BEFORE the [ref] check runs. The except branch must catch it,
    # append an [acyclic] find_cycles() raised ... violation, and let check_kg degrade
    # gracefully (return a non-empty violation set rather than crashing).
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    edges = [Edge(id=7001, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=9999)]
    # check_kg must NOT raise (the whole point of the amendment-E guard).
    v = validate_kg.check_kg(_store_with(nodes, edges, {}), _quests_data(["B"]))
    assert any("[acyclic] find_cycles() raised" in x and "9999" in x for x in v), v
    assert v, v  # degraded gracefully: still a non-empty (non-zero exit) violation set


# --- Step 4: on-real-data acceptance test ---

def test_main_passes_on_committed_kg():
    from osrs_planner.engine.kg.json_store import JsonKGStore
    store = JsonKGStore.from_dir(validate_kg.KG_DIR)
    with open(validate_kg.QUESTS_PATH) as f:
        quests_data = json.load(f)
    with open(os.path.join(validate_kg.KG_DIR, "nodes.json"), encoding="utf-8") as f:
        raw_node_dicts = json.load(f)
    with open(os.path.join(validate_kg.KG_DIR, "edges.json"), encoding="utf-8") as f:
        raw_edge_dicts = json.load(f)
    with open(os.path.join(validate_kg.KG_DIR, "condition_groups.json"), encoding="utf-8") as f:
        raw_group_dicts = json.load(f)
    assert validate_kg.check_kg(store, quests_data, raw_node_dicts=raw_node_dicts,
                                 raw_edge_dicts=raw_edge_dicts,
                                 raw_group_dicts=raw_group_dicts) == []
    assert validate_kg.main() == 0
