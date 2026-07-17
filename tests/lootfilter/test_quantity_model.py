from osrs_planner.lootfilter.palette import GRADE_ORDER, quantity_display_grade as q

def test_grade_order():
    assert GRADE_ORDER == ["SS", "S", "A", "B", "C", "D", "E"]

def test_base_floor_at_count_one():
    assert q("A", 1) == "A" and q("E", 1) == "E"

def test_ranarr_case_base_A():        # the design's motivating example
    assert q("A", 40) == "S" and q("A", 100) == "SS" and q("A", 9) == "A"

def test_guam_case_base_E():
    assert q("E", 40) == "D" and q("E", 100) == "C" and q("E", 1000) == "B"

def test_caps_at_ss():
    assert q("B", 10_000_000) == "SS" and q("SS", 5) == "SS"

def test_no_float_precision_bug_at_powers_of_ten():
    # integer decades, NOT float log10 (log10(1000)=2.9999.. would misgrade)
    assert q("B", 1000) == "SS" and q("A", 100) == "SS" and q("C", 100) == "A"

def test_count_below_one_is_base():
    assert q("B", 0) == "B"
