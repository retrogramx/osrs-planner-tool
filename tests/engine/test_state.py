# tests/engine/test_state.py
from osrs_planner.engine.state import QUEST_STATE_ORDER, AccountState, family_is_observed


def test_quest_state_order_is_ordered_three_state():
    assert QUEST_STATE_ORDER == {"not_started": 0, "in_progress": 1, "completed": 2}
    # ordered: a 'completed' requirement is met only by completed;
    # an 'in_progress' requirement is met by in_progress or completed.
    assert QUEST_STATE_ORDER["completed"] > QUEST_STATE_ORDER["in_progress"]
    assert QUEST_STATE_ORDER["in_progress"] > QUEST_STATE_ORDER["not_started"]
    # diary states reuse the same ordering map
    assert QUEST_STATE_ORDER["completed"] >= QUEST_STATE_ORDER["in_progress"]


def test_account_state_constructs_with_defaults():
    st = AccountState(mode="ironman")
    assert st.mode == "ironman"
    # every collection field defaults to an independent empty container
    assert st.levels == {}
    assert st.xp == {}
    assert st.counts == {}
    assert st.quest_state == {}
    assert st.diary_state == {}
    assert st.done == set()
    assert st.kc == {}
    assert st.clue_counts == {}
    assert st.observable_families == set()
    # scalar derived defaults
    assert st.combat_level == 3
    assert st.qp == 0
    assert st.ca_points == 0


def test_account_state_default_containers_are_not_shared():
    a = AccountState(mode="normal")
    b = AccountState(mode="normal")
    a.levels["attack"] = 70
    a.done.add("access:lumbridge")
    # mutable defaults must be per-instance (field(default_factory=...))
    assert b.levels == {}
    assert b.done == set()


def test_observed_family_with_absent_value_is_a_real_zero():
    # skill_level IS Hiscores-observable: absence == observed zero (eligible FALSE)
    st = AccountState(mode="normal", observable_families={"skill_level", "kill_count"})
    assert family_is_observed("skill_level", st, manually_asserted=False) is True
    assert family_is_observed("kill_count", st, manually_asserted=False) is True


def test_unobserved_family_absent_and_not_asserted_is_unknown():
    # quest is NOT a Hiscores field -> absence is UNKNOWN, not FALSE
    st = AccountState(mode="normal", observable_families={"skill_level"})
    assert family_is_observed("quest", st, manually_asserted=False) is False
    assert family_is_observed("achievement_diary", st, manually_asserted=False) is False
    assert family_is_observed("combat_achievement", st, manually_asserted=False) is False
    assert family_is_observed("item", st, manually_asserted=False) is False
    assert family_is_observed("is_unlocked", st, manually_asserted=False) is False


def test_manual_assertion_makes_any_family_observed():
    # a one-tap "confirm this value" manual fact is trusted (contract §6 / §9.3):
    # even an unobservable family becomes a known value once manually asserted.
    st = AccountState(mode="normal", observable_families=set())
    assert family_is_observed("quest", st, manually_asserted=True) is True
    assert family_is_observed("item", st, manually_asserted=True) is True


def test_observable_families_membership_drives_the_decision():
    # the SAME family flips purely on whether it's in observable_families
    observed = AccountState(mode="normal", observable_families={"kill_count"})
    not_observed = AccountState(mode="normal", observable_families=set())
    assert family_is_observed("kill_count", observed, manually_asserted=False) is True
    assert family_is_observed("kill_count", not_observed, manually_asserted=False) is False
