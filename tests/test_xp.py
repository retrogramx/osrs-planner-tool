from osrs_planner.xp import xp_for_level, level_for_xp, xp_remaining

def test_level_1():
    assert xp_for_level(1) == 0

def test_level_92():
    assert xp_for_level(92) == 6_517_253

def test_level_99():
    assert xp_for_level(99) == 13_034_431

def test_level_for_xp_83():
    assert level_for_xp(83) == 2

def test_level_for_xp_14m():
    assert level_for_xp(14_000_000) == 99

def test_xp_remaining_97():
    assert xp_remaining(0, 97) == 10_692_629
