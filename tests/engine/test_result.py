from dataclasses import FrozenInstanceError

import pytest

from osrs_planner.engine.result import (
    Empty,
    NodeRef,
    Ok,
    Problem,
    ProblemKind,
    Refs,
    Result,
    TerminalReason,
)


# --- ProblemKind: the closed failure taxonomy (contract §4, §10) ---

def test_problemkind_members_exact():
    assert {k.value for k in ProblemKind} == {
        "not_found",
        "ambiguous",
        "invalid_target",
        "impossible_for_account",
        "missing_state",
        "unsatisfiable_cycle",
    }

def test_problemkind_is_str_enum():
    # str-mixin: the value compares/serializes as the bare string
    assert ProblemKind.NOT_FOUND == "not_found"
    assert ProblemKind.NOT_FOUND.value == "not_found"


# --- TerminalReason: Empty's "this is a success" reasons (contract §4) ---

def test_terminalreason_members_exact():
    assert {r.value for r in TerminalReason} == {
        "already_satisfied",
        "no_frontier",
        "empty_result",
    }

def test_terminalreason_is_str_enum():
    assert TerminalReason.ALREADY_SATISFIED == "already_satisfied"


# --- NodeRef: the grounding atom ---

def test_noderef_fields():
    ref = NodeRef(id="npc:7221", kind="monster", name="Scurrius")
    assert ref.id == "npc:7221"
    assert ref.kind == "monster"
    assert ref.name == "Scurrius"

def test_noderef_frozen():
    ref = NodeRef(id="npc:7221", kind="monster", name="Scurrius")
    with pytest.raises(FrozenInstanceError):
        ref.id = "npc:0"  # type: ignore[misc]


# --- Refs: two maps, each defaulting to an independent empty dict ---

def test_refs_defaults_empty():
    refs = Refs()
    assert refs.nodes == {}
    assert refs.mentions == {}

def test_refs_default_factory_not_shared():
    # default_factory must give each instance its OWN dict (no mutable-default bug)
    a = Refs()
    b = Refs()
    assert a.nodes is not b.nodes
    assert a.mentions is not b.mentions

def test_refs_carries_node_and_mention_maps():
    n = NodeRef(id="skill:attack", kind="skill", name="Attack")
    m = NodeRef(id="activity:fight-caves", kind="activity", name="Fight Caves")
    refs = Refs(nodes={n.id: n}, mentions={m.id: m})
    assert refs.nodes["skill:attack"] is n
    assert refs.mentions["activity:fight-caves"] is m

def test_refs_frozen():
    refs = Refs()
    with pytest.raises(FrozenInstanceError):
        refs.nodes = {}  # type: ignore[misc]


# --- Ok[T]: carries the card + refs (contract §4) ---

def test_ok_carries_card_and_refs():
    refs = Refs(nodes={"npc:7221": NodeRef("npc:7221", "monster", "Scurrius")})
    ok = Ok(card="any-card-payload", refs=refs)
    assert ok.card == "any-card-payload"
    assert ok.refs is refs

def test_ok_is_generic_over_card_type():
    # Generic[T]: the payload may be any type; a list works as well as a str
    ok = Ok(card=[1, 2, 3], refs=Refs())
    assert ok.card == [1, 2, 3]

def test_ok_frozen():
    ok = Ok(card=1, refs=Refs())
    with pytest.raises(FrozenInstanceError):
        ok.card = 2  # type: ignore[misc]


# --- Empty: a SUCCESS state (status defaults to "ok"), with a TerminalReason ---

def test_empty_is_success_with_reason():
    refs = Refs(nodes={"npc:7221": NodeRef("npc:7221", "monster", "Scurrius")})
    empty = Empty(refs=refs, reason=TerminalReason.ALREADY_SATISFIED)
    assert empty.status == "ok"        # Empty is NOT a failure
    assert empty.reason is TerminalReason.ALREADY_SATISFIED
    assert empty.refs is refs

def test_empty_status_default_is_ok():
    empty = Empty(refs=Refs(), reason=TerminalReason.NO_FRONTIER)
    assert empty.status == "ok"

def test_empty_frozen():
    empty = Empty(refs=Refs(), reason=TerminalReason.EMPTY_RESULT)
    with pytest.raises(FrozenInstanceError):
        empty.reason = TerminalReason.NO_FRONTIER  # type: ignore[misc]


# --- Problem: the failure carrier (kind + refs + message) ---

def test_problem_carries_kind_refs_message():
    refs = Refs(nodes={"npc:0": NodeRef("npc:0", "monster", "?")})
    prob = Problem(
        kind=ProblemKind.NOT_FOUND,
        refs=refs,
        message="no node 'npc:0'",
    )
    assert prob.kind is ProblemKind.NOT_FOUND
    assert prob.refs is refs
    assert prob.message == "no node 'npc:0'"

def test_problem_frozen():
    prob = Problem(kind=ProblemKind.MISSING_STATE, refs=Refs(), message="x")
    with pytest.raises(FrozenInstanceError):
        prob.message = "y"  # type: ignore[misc]


# --- Result alias: usable as a type annotation over all three variants ---

def test_result_alias_admits_all_three_variants():
    values: list[Result] = [
        Ok(card="c", refs=Refs()),
        Empty(refs=Refs(), reason=TerminalReason.ALREADY_SATISFIED),
        Problem(kind=ProblemKind.AMBIGUOUS, refs=Refs(), message="2 candidates"),
    ]
    # the consumer pattern both projections use: branch on the concrete variant
    kinds = [type(v).__name__ for v in values]
    assert kinds == ["Ok", "Empty", "Problem"]
