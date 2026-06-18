from osrs_planner.engine.kleene import Tri, k_and, k_or, k_not, from_bool


class TestTriEnum:
    def test_has_three_members(self):
        assert {m.name for m in Tri} == {"TRUE", "FALSE", "UNKNOWN"}

    def test_members_are_distinct(self):
        assert Tri.TRUE is not Tri.FALSE
        assert Tri.TRUE is not Tri.UNKNOWN
        assert Tri.FALSE is not Tri.UNKNOWN


class TestFromBool:
    def test_true(self):
        assert from_bool(True) is Tri.TRUE

    def test_false(self):
        assert from_bool(False) is Tri.FALSE


class TestKNot:
    def test_not_true_is_false(self):
        assert k_not(Tri.TRUE) is Tri.FALSE

    def test_not_false_is_true(self):
        assert k_not(Tri.FALSE) is Tri.TRUE

    def test_not_unknown_is_unknown(self):
        # UNKNOWN never flips -- negation can't resolve it.
        assert k_not(Tri.UNKNOWN) is Tri.UNKNOWN


class TestKAnd:
    # --- all-definite (classical) ---
    def test_true_true(self):
        assert k_and([Tri.TRUE, Tri.TRUE]) is Tri.TRUE

    def test_true_false(self):
        assert k_and([Tri.TRUE, Tri.FALSE]) is Tri.FALSE

    def test_false_false(self):
        assert k_and([Tri.FALSE, Tri.FALSE]) is Tri.FALSE

    # --- FALSE dominates: UNKNOWN is ABSORBED (does not flip the verdict) ---
    def test_false_unknown_is_false(self):
        # §6: a known-FALSE clause locks AND to FALSE; UNKNOWN can't rescue it.
        assert k_and([Tri.FALSE, Tri.UNKNOWN]) is Tri.FALSE

    def test_unknown_false_is_false(self):
        assert k_and([Tri.UNKNOWN, Tri.FALSE]) is Tri.FALSE

    # --- no FALSE present: UNKNOWN SURFACES (it flips a would-be TRUE) ---
    def test_true_unknown_is_unknown(self):
        # All others TRUE, one UNKNOWN -> can't claim TRUE -> UNKNOWN.
        assert k_and([Tri.TRUE, Tri.UNKNOWN]) is Tri.UNKNOWN

    def test_unknown_unknown_is_unknown(self):
        assert k_and([Tri.UNKNOWN, Tri.UNKNOWN]) is Tri.UNKNOWN

    # --- variadic / fold shape ---
    def test_all_true_three(self):
        assert k_and([Tri.TRUE, Tri.TRUE, Tri.TRUE]) is Tri.TRUE

    def test_false_anywhere_dominates(self):
        assert k_and([Tri.TRUE, Tri.UNKNOWN, Tri.FALSE, Tri.TRUE]) is Tri.FALSE

    def test_empty_is_true(self):
        # Empty conjunction = identity TRUE (vacuously satisfied).
        assert k_and([]) is Tri.TRUE

    def test_accepts_generator(self):
        # Signature is Iterable[Tri], not list -- must consume any iterable.
        assert k_and(t for t in (Tri.TRUE, Tri.FALSE)) is Tri.FALSE


class TestKOr:
    # --- all-definite (classical) ---
    def test_true_true(self):
        assert k_or([Tri.TRUE, Tri.TRUE]) is Tri.TRUE

    def test_true_false(self):
        assert k_or([Tri.TRUE, Tri.FALSE]) is Tri.TRUE

    def test_false_false(self):
        assert k_or([Tri.FALSE, Tri.FALSE]) is Tri.FALSE

    # --- TRUE dominates: UNKNOWN is ABSORBED (does not flip the verdict) ---
    def test_true_unknown_is_true(self):
        # §6: a known-TRUE alternative satisfies OR; UNKNOWN is irrelevant.
        # This is the worked-example shape: OR(known-true, can't-verify) == TRUE.
        assert k_or([Tri.TRUE, Tri.UNKNOWN]) is Tri.TRUE

    def test_unknown_true_is_true(self):
        assert k_or([Tri.UNKNOWN, Tri.TRUE]) is Tri.TRUE

    # --- no TRUE present: UNKNOWN SURFACES (it flips a would-be FALSE) ---
    def test_false_unknown_is_unknown(self):
        # No satisfied alternative, but one we can't rule out -> UNKNOWN.
        assert k_or([Tri.FALSE, Tri.UNKNOWN]) is Tri.UNKNOWN

    def test_unknown_unknown_is_unknown(self):
        assert k_or([Tri.UNKNOWN, Tri.UNKNOWN]) is Tri.UNKNOWN

    # --- variadic / fold shape ---
    def test_all_false_three(self):
        assert k_or([Tri.FALSE, Tri.FALSE, Tri.FALSE]) is Tri.FALSE

    def test_true_anywhere_dominates(self):
        assert k_or([Tri.FALSE, Tri.UNKNOWN, Tri.TRUE, Tri.FALSE]) is Tri.TRUE

    def test_empty_is_false(self):
        # Empty disjunction = identity FALSE (no alternative satisfies it).
        assert k_or([]) is Tri.FALSE

    def test_accepts_generator(self):
        assert k_or(t for t in (Tri.FALSE, Tri.TRUE)) is Tri.TRUE


import itertools
import pytest


@pytest.mark.parametrize("a,b", itertools.product(list(Tri), repeat=2))
def test_de_morgan_duality(a, b):
    # NOT(a AND b) == (NOT a) OR (NOT b), and dually -- must hold for all 9 pairs.
    assert k_not(k_and([a, b])) is k_or([k_not(a), k_not(b)])
    assert k_not(k_or([a, b])) is k_and([k_not(a), k_not(b)])
