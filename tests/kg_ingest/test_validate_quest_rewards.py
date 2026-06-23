"""Tests for data/validate_quest_rewards.py — structural reward validator (Task 6)."""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "validate_quest_rewards.py")
_spec = importlib.util.spec_from_file_location("validate_quest_rewards", _PATH)
vqr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vqr)

_ITEM_IDS = {7462, 7409}
_ITEM_TRADEABLE = {7462: False, 7409: True}
_QUESTS = {"Waterfall Quest", "Recipe for Disaster"}


def _data(records):
    return {"_provenance": {"source_urls": ["x"]}, "records": records}


def _ok_record():
    return {"quest": "Waterfall Quest", "quest_points": 1,
            "rewards": [{"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750}],
            "effects": []}


def test_valid_record_has_no_violations():
    errs = vqr.check_quest_rewards(_data([_ok_record()]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert errs == [], errs


def test_unresolved_item_id_is_flagged():
    rec = {"quest": "Recipe for Disaster", "rewards": [
        {"reward_type": "items", "item": "Fake", "item_id": 999999, "qty": 1, "tradeable": False}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("999999" in e for e in errs), errs


def test_unknown_quest_is_flagged():
    rec = dict(_ok_record(), quest="Nonexistent Quest")
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("Nonexistent Quest" in e for e in errs), errs


def test_bad_unlock_category_is_flagged():
    rec = {"quest": "Waterfall Quest", "rewards": [
        {"reward_type": "unlock", "category": "not-a-category", "stage": "completed"}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("not-a-category" in e for e in errs), errs


def test_tradeable_flag_mismatch_is_flagged():
    # Barrows gloves (7462) is untradeable; a record claiming tradeable=true is wrong.
    rec = {"quest": "Recipe for Disaster", "rewards": [
        {"reward_type": "items", "item": "Barrows gloves", "item_id": 7462, "qty": 1, "tradeable": True}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("tradeable" in e and "7462" in e for e in errs), errs


def test_committed_seed_passes():
    rc = vqr.main([])
    assert rc == 0


def test_effect_on_ungranted_item_is_flagged():
    rec = {"quest": "Waterfall Quest", "rewards": [],
           "effects": [{"rides_on_item_id": 7462, "effect_kind": "stat_multiplier"}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("does not grant" in e for e in errs), errs


def test_effect_on_granted_item_without_tradeable_key_is_ok():
    # Regression for the granted-item registration fix: the item is granted (resolves)
    # even though its items reward omits the `tradeable` key, so the effect must NOT be flagged.
    rec = {"quest": "Recipe for Disaster",
           "rewards": [{"reward_type": "items", "item": "Barrows gloves", "item_id": 7462, "qty": 1}],
           "effects": [{"rides_on_item_id": 7462, "effect_kind": "stat_multiplier"}]}
    errs = vqr.check_quest_rewards(_data([rec]), {"records": []},
                                   _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert not any("does not grant" in e for e in errs), errs


def test_bad_goal_counter_type_is_flagged():
    gd = {"records": [{"id": "goal:x", "name": "X", "counter_type": "bogus", "thresholds": [1]}]}
    errs = vqr.check_quest_rewards(_data([]), gd, _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("counter_type" in e for e in errs), errs


def test_empty_goal_thresholds_is_flagged():
    gd = {"records": [{"id": "goal:x", "name": "X", "counter_type": "points", "thresholds": []}]}
    errs = vqr.check_quest_rewards(_data([]), gd, _ITEM_IDS, _ITEM_TRADEABLE, _QUESTS)
    assert any("thresholds" in e for e in errs), errs
