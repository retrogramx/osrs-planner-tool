"""count_satisfied atom — Kleene cardinality over diary-tier completion (diaries Task 1)."""
from osrs_planner.engine.kg.model import AtomType, ConditionAtom
from osrs_planner.engine.conditions import atom_satisfied
from osrs_planner.engine.kleene import Tri
from osrs_planner.engine.state import AccountState


def _atom(set_ref, threshold):
    return ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=threshold,
                         data={"set_ref": set_ref})


def test_enough_completed_is_true():
    st = AccountState(mode="main", observable_families={"achievement_diary"},
                      diary_state={"diary:ardougne:easy": "completed",
                                   "diary:desert:easy": "completed"})
    assert atom_satisfied(_atom(["diary:ardougne:easy", "diary:desert:easy"], 2), st, None) is Tri.TRUE


def test_observed_absence_short_of_threshold_is_false():
    st = AccountState(mode="main", observable_families={"achievement_diary"},
                      diary_state={"diary:ardougne:easy": "completed"})
    # 1 completed, 1 observed-not-done, threshold 2 -> can't reach -> FALSE
    assert atom_satisfied(_atom(["diary:ardougne:easy", "diary:desert:easy"], 2), st, None) is Tri.FALSE


def test_unobserved_members_are_unknown():
    st = AccountState(mode="main", observable_families=set(),  # diary not observed
                      diary_state={"diary:ardougne:easy": "completed"})
    # 1 known-true, 1 unknown, threshold 2 -> might reach -> UNKNOWN
    assert atom_satisfied(_atom(["diary:ardougne:easy", "diary:desert:easy"], 2), st, None) is Tri.UNKNOWN
