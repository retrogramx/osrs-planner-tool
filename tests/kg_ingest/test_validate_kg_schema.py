"""Tests for the schema-driven domain/range invariant + severity tiers in
data/validate_kg.py (v2 ontology build step 1, spec §8).

These exercise `validate_kg.check_schema(store, schema)` — a generic, schema-driven
check that reads kg/schema.json (the locked v2 ontology-as-data) and returns
severity-tagged Findings: VIOLATION for an undeclared kind/edge/atom/op or a
domain/range breach, INFO for legacy (v1) kinds/atoms pending migration.
"""
import importlib.util
import os
import pathlib

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.json_store import JsonKGStore

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_VK_PATH = os.path.join(_ROOT, "data", "validate_kg.py")
_spec = importlib.util.spec_from_file_location("validate_kg", _VK_PATH)
validate_kg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_kg)

KG_DIR = str(pathlib.Path(_ROOT) / "kg")


def _schema():
    return validate_kg.load_schema()


def _violations(findings):
    return [f for f in findings if f.severity is validate_kg.Severity.VIOLATION]


def _infos(findings):
    return [f for f in findings if f.severity is validate_kg.Severity.INFO]


def _store(nodes, edges=None, groups=None):
    return InMemoryKGStore(nodes, edges or [], groups or {})


# --- the load-bearing guarantee: the REAL committed graph is VIOLATION-clean ----

def test_real_kg_has_zero_schema_violations():
    """The committed kg/*.json must clear the schema-driven invariant with ZERO
    VIOLATIONs (CI/byte-stability guard). Legacy INFO findings are allowed."""
    store = JsonKGStore.from_dir(KG_DIR)
    findings = validate_kg.check_schema(store, _schema())
    assert _violations(findings) == [], [f.message for f in _violations(findings)]


def test_real_kg_reports_legacy_kinds_as_info():
    """region/access/gear_loadout are legacy v1 kinds -> surfaced at INFO, not fatal."""
    store = JsonKGStore.from_dir(KG_DIR)
    infos = _infos(validate_kg.check_schema(store, _schema()))
    blob = " ".join(f.message for f in infos)
    assert any("region" in f.message for f in infos), blob
    assert all(f.severity is not validate_kg.Severity.VIOLATION for f in infos)


# --- clean minimal store ---------------------------------------------------------

def test_clean_store_has_no_violations():
    nodes = [
        Node(id="quest:a", kind=NodeKind.QUEST, name="A", slug="a", data={}),
        Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={}),
    ]
    edges = [Edge(id=1, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=None)]
    assert _violations(validate_kg.check_schema(_store(nodes, edges), _schema())) == []


# --- closed vocabulary: kinds / edge types / atom types / ops --------------------

def test_undeclared_node_kind_is_a_violation():
    nodes = [Node(id="x:1", kind="totally_bogus_kind", name="X", slug="x", data={})]
    v = _violations(validate_kg.check_schema(_store(nodes), _schema()))
    assert any("totally_bogus_kind" in f.message for f in v), v


def test_undeclared_edge_type_is_a_violation():
    nodes = [Node(id="quest:a", kind=NodeKind.QUEST, name="A", slug="a", data={})]
    edges = [Edge(id=1, type="bogus_edge_type", src="quest:a", dst="quest:a")]
    v = _violations(validate_kg.check_schema(_store(nodes, edges), _schema()))
    assert any("bogus_edge_type" in f.message for f in v), v


def test_undeclared_atom_type_is_a_violation():
    groups = {1: ConditionGroup(id=1, op=Op.AND, parent=None, children=[
        ConditionAtom(atom_type="bogus_atom", ref_node=None, threshold=None, qty=None, data={}),
    ])}
    v = _violations(validate_kg.check_schema(_store([], [], groups), _schema()))
    assert any("bogus_atom" in f.message for f in v), v


def test_undeclared_op_is_a_violation():
    groups = {1: ConditionGroup(id=1, op="xor", parent=None, children=[])}
    v = _violations(validate_kg.check_schema(_store([], [], groups), _schema()))
    assert any("xor" in f.message for f in v), v


# --- domain / range / dst-nullability --------------------------------------------

def test_domain_breach_is_a_violation():
    # supersedes domain is [item, goal]; a skill src breaches it.
    nodes = [
        Node(id="skill:agility", kind=NodeKind.SKILL, name="Agility", slug="agility", data={}),
        Node(id="item:1", kind=NodeKind.ITEM, name="I", slug="i", data={}),
    ]
    edges = [Edge(id=1, type=EdgeType.SUPERSEDES, src="skill:agility", dst="item:1")]
    v = _violations(validate_kg.check_schema(_store(nodes, edges), _schema()))
    assert any(f.code == "domain" and "skill:agility" in f.message for f in v), v


def test_range_breach_is_a_violation():
    # progress_towards range is [goal]; a skill dst breaches it.
    nodes = [
        Node(id="quest:a", kind=NodeKind.QUEST, name="A", slug="a", data={}),
        Node(id="skill:agility", kind=NodeKind.SKILL, name="Agility", slug="agility", data={}),
    ]
    edges = [Edge(id=1, type=EdgeType.PROGRESS_TOWARDS, src="quest:a",
                  dst="skill:agility", data={"weight": 1})]
    v = _violations(validate_kg.check_schema(_store(nodes, edges), _schema()))
    assert any(f.code == "range" and "skill:agility" in f.message for f in v), v


def test_required_dst_none_is_a_violation():
    # supersedes requires a dst; dst=None breaches the dst policy.
    nodes = [Node(id="item:1", kind=NodeKind.ITEM, name="I", slug="i", data={})]
    edges = [Edge(id=1, type=EdgeType.SUPERSEDES, src="item:1", dst=None)]
    v = _violations(validate_kg.check_schema(_store(nodes, edges), _schema()))
    assert any(f.code == "dst" for f in v), v


def test_optional_dst_none_is_allowed():
    # requires dst policy is 'optional' -> dst=None is fine (no violation).
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    edges = [Edge(id=1, type=EdgeType.REQUIRES, src="quest:b", dst=None)]
    assert _violations(validate_kg.check_schema(_store(nodes, edges), _schema())) == []


# --- legacy tolerance: INFO, never VIOLATION -------------------------------------

def test_legacy_node_kind_is_info_not_violation():
    nodes = [Node(id="region:misthalin", kind=NodeKind.REGION, name="Misthalin",
                  slug="misthalin", data={})]
    findings = validate_kg.check_schema(_store(nodes), _schema())
    assert _violations(findings) == [], findings
    assert any(f.code == "legacy" and "region" in f.message for f in _infos(findings)), findings


def test_legacy_atom_type_is_info_not_violation():
    groups = {1: ConditionGroup(id=1, op=Op.AND, parent=None, children=[
        ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, ref_node=None, threshold=None,
                      qty=None, data={"set_ref": []}),
    ])}
    findings = validate_kg.check_schema(_store([], [], groups), _schema())
    assert _violations(findings) == [], findings
    assert any(f.code == "legacy" and "count_satisfied" in f.message for f in _infos(findings)), findings


# --- schema loader + severity surface --------------------------------------------

def test_load_schema_shape():
    schema = _schema()
    assert schema["status"] == "locked"
    for key in ("node_kinds", "legacy_node_kinds", "edge_kinds", "atom_types",
                "legacy_atom_types", "ops", "severity_tiers"):
        assert key in schema, key


def test_severity_enum_has_three_tiers():
    tiers = {s.value for s in validate_kg.Severity}
    assert tiers == {"VIOLATION", "WARNING", "INFO"}


# --- review follow-ups: closed-contract hardening ---------------------------------

def _min_schema(**overrides):
    """A minimal-but-complete schema dict for isolating one check at a time."""
    s = {
        "node_kinds": {"item": {"status": "live"}, "goal": {"status": "live"}},
        "legacy_node_kinds": {},
        "edge_kinds": {},
        "legacy_edge_kinds": {},
        "atom_types": {},
        "legacy_atom_types": {},
        "ops": ["and", "or", "not"],
    }
    s.update(overrides)
    return s


def test_model_enums_are_all_declared_in_schema():
    """Every engine model-enum value (NodeKind/EdgeType/AtomType) the builders can
    emit MUST be declared in the schema (live, reserved, or legacy) so it can never
    produce a surprise closed-vocabulary VIOLATION. v1-only vestiges are legacy."""
    schema = _schema()
    declared_nodes = set(schema["node_kinds"]) | set(schema["legacy_node_kinds"])
    declared_edges = set(schema["edge_kinds"]) | set(schema.get("legacy_edge_kinds", {}))
    declared_atoms = set(schema["atom_types"]) | set(schema["legacy_atom_types"])
    assert {k.value for k in NodeKind} <= declared_nodes, \
        {k.value for k in NodeKind} - declared_nodes
    assert {e.value for e in EdgeType} <= declared_edges, \
        {e.value for e in EdgeType} - declared_edges
    assert {a.value for a in AtomType} <= declared_atoms, \
        {a.value for a in AtomType} - declared_atoms


def test_forbidden_dst_with_present_dst_is_a_violation():
    schema = _min_schema(edge_kinds={
        "x": {"domain": ["item"], "range": ["item"], "dst": "forbidden"}})
    nodes = [Node(id="item:1", kind=NodeKind.ITEM, name="A", slug="a", data={}),
             Node(id="item:2", kind=NodeKind.ITEM, name="B", slug="b", data={})]
    edges = [Edge(id=1, type="x", src="item:1", dst="item:2")]
    v = _violations(validate_kg.check_schema(_store(nodes, edges), schema))
    assert any(f.code == "dst" for f in v), v


def test_forbidden_dst_with_none_dst_is_allowed():
    schema = _min_schema(edge_kinds={
        "x": {"domain": ["item"], "range": ["item"], "dst": "forbidden"}})
    nodes = [Node(id="item:1", kind=NodeKind.ITEM, name="A", slug="a", data={})]
    edges = [Edge(id=1, type="x", src="item:1", dst=None)]
    assert _violations(validate_kg.check_schema(_store(nodes, edges), schema)) == []


def test_legacy_edge_type_is_info_not_violation():
    # gated_by is a v1 model EdgeType with no v2 row -> legacy, surfaced at INFO.
    nodes = [Node(id="quest:a", kind=NodeKind.QUEST, name="A", slug="a", data={}),
             Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b", data={})]
    edges = [Edge(id=1, type=EdgeType.GATED_BY, src="quest:a", dst="quest:b")]
    findings = validate_kg.check_schema(_store(nodes, edges), _schema())
    assert _violations(findings) == [], findings
    assert any(f.code == "legacy" and "gated_by" in f.message for f in _infos(findings)), findings


def test_dangling_src_is_not_double_reported_as_domain_breach():
    # A dangling src (no node) is referential-integrity's job (check_kg [ref]); the
    # schema check must not ALSO mislabel it 'kind None not in domain'.
    nodes = [Node(id="item:1", kind=NodeKind.ITEM, name="A", slug="a", data={})]
    edges = [Edge(id=1, type=EdgeType.SUPERSEDES, src="ghost:1", dst="item:1")]
    findings = validate_kg.check_schema(_store(nodes, edges), _schema())
    assert not any(f.code == "domain" for f in _violations(findings)), findings
