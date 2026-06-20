import math
from data._rarity_grammar import parse_rarity

def approx(a, b): return a is not None and math.isclose(a, b, rel_tol=1e-6)

def test_simple_fraction():
    rate, rolls, status = parse_rarity("1/512")
    assert approx(rate, 1/512) and rolls == 1 and status == "sourced"

def test_non_unit_numerator():
    rate, _, status = parse_rarity("12/128")
    assert approx(rate, 12/128) and status == "sourced"

def test_decimal_denominator():
    rate, _, status = parse_rarity("1/26.9")
    assert approx(rate, 1/26.9) and status == "sourced"

def test_comma_thousands_separator():  # M3 — real API emits "1/3,000", "1/16,384"
    rate, _, status = parse_rarity("1/3,000")
    assert approx(rate, 1/3000) and status == "sourced"
    rate2, _, status2 = parse_rarity("1/16,384")
    assert approx(rate2, 1/16384) and status2 == "sourced"
    rate3, _, status3 = parse_rarity("1/2,687.2")  # comma + decimal
    assert approx(rate3, 1/2687.2) and status3 == "sourced"

def test_embedded_rolls_multiplier():
    rate, rolls, status = parse_rarity("2 × 1/128")
    assert approx(rate, 1/128) and rolls == 2 and status == "sourced"

def test_always_is_one():
    assert parse_rarity("Always") == (1.0, 1, "sourced")
    assert parse_rarity("1/1") == (1.0, 1, "sourced")

def test_qualitative_is_null_not_fabricated():
    for q in ("Common", "Uncommon", "Varies", "~", ""):
        rate, _, status = parse_rarity(q)
        assert rate is None and status == "null-qualitative"

def test_unparseable_is_null_unparsed():
    rate, _, status = parse_rarity("see notes")
    assert rate is None and status == "null-unparsed"

def test_none_input():
    rate, _, status = parse_rarity(None)
    assert rate is None and status == "null-qualitative"
