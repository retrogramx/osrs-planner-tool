"""Tests for data/validate_diary_rewards.py — structural diary-reward validator (Task 4)."""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "validate_diary_rewards.py")
_spec = importlib.util.spec_from_file_location("validate_diary_rewards", _PATH)
vdr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vdr)

# Minimal item universe for unit tests
_ITEM_IDS = {13121, 13122, 13113, 13114}       # cloak 1, cloak 2, legs 2, legs 3
_ITEM_TRADEABLE = {13121: False, 13122: False, 13113: False, 13114: False}
_SKILL_IDS = {"Slayer", "Prayer", "Magic", "Agility", "Farming"}


def _make_record(**overrides):
    base = {
        "region": "ardougne",
        "tier": "easy",
        "regional_item": {"name": "Ardougne cloak 1", "item_id": 13121},
        "lamp": {"amount": 2500, "min_level": 30, "eligible_skills": "any",
                 "lamp_item": "Antique lamp (easy)"},
        "effects": [
            {"effect_kind": "rate_multiplier", "magnitude": 1.0,
             "target_facet": "death runes from trading cats",
             "target": {"kind": "activity", "name": "West Ardougne cat trade"},
             "condition": "unconditional-once-earned",
             "tier_source": "ardougne:easy"}
        ],
        "extra_unlocks": [],
        "source_url": "https://oldschool.runescape.wiki/w/Ardougne_Diary",
    }
    base.update(overrides)
    return base


def _data(records):
    return {"records": records, "_provenance": {"source_urls": ["https://oldschool.runescape.wiki/w/Ardougne_Diary"]}}


def _check(records, *, skill_ids=frozenset(), content_ids=frozenset()):
    return vdr.check_diary_rewards(
        _data(records), _ITEM_IDS, _ITEM_TRADEABLE,
        skill_ids=skill_ids, content_ids=content_ids,
    )


def test_valid_record_has_no_violations():
    errs = _check([_make_record()])
    assert errs == [], errs


def test_bad_effect_kind_is_flagged():
    rec = _make_record()
    rec["effects"][0]["effect_kind"] = "magic_bonus"
    errs = _check([rec])
    assert any("effect_kind" in e or "magic_bonus" in e for e in errs), errs


def test_unresolved_regional_item_id_is_flagged():
    rec = _make_record()
    rec["regional_item"] = {"name": "Fake cloak", "item_id": 999999}
    errs = _check([rec])
    assert any("999999" in e for e in errs), errs


def test_unresolved_supersedes_item_id_is_flagged():
    rec = _make_record()
    rec["regional_item"] = {"name": "Ardougne cloak 1", "item_id": 13121, "supersedes_item_id": 999998}
    errs = _check([rec])
    assert any("999998" in e for e in errs), errs


def test_lamp_amount_zero_is_flagged():
    rec = _make_record()
    rec["lamp"]["amount"] = 0
    errs = _check([rec])
    assert any("lamp" in e and "amount" in e for e in errs), errs


def test_lamp_amount_negative_is_flagged():
    rec = _make_record()
    rec["lamp"]["amount"] = -1
    errs = _check([rec])
    assert any("lamp" in e and "amount" in e for e in errs), errs


def test_bad_target_kind_is_flagged():
    rec = _make_record()
    rec["effects"][0]["target"]["kind"] = "dungeon"
    errs = _check([rec])
    assert any("target.kind" in e or "dungeon" in e for e in errs), errs


def test_null_item_id_without_untracked_is_flagged():
    rec = _make_record()
    rec["extra_unlocks"] = [{"reward_type": "items", "name": "Mystery Item", "item_id": None}]
    errs = _check([rec])
    assert any("untracked" in e for e in errs), errs


def test_null_item_id_with_untracked_is_ok():
    rec = _make_record()
    rec["extra_unlocks"] = [{"reward_type": "items", "name": "Bonecrusher",
                             "item_id": None, "untracked": True}]
    errs = _check([rec])
    assert errs == [], errs


def test_nonnull_item_id_that_doesnt_resolve_is_flagged():
    rec = _make_record()
    rec["extra_unlocks"] = [{"reward_type": "items", "name": "Fake Item",
                             "item_id": 88888, "tradeable": False}]
    errs = _check([rec])
    assert any("88888" in e for e in errs), errs


def test_wrong_tier_source_is_flagged():
    rec = _make_record()
    rec["effects"][0]["tier_source"] = "morytania:hard"  # wrong for ardougne:easy
    errs = _check([rec])
    assert any("tier_source" in e for e in errs), errs


def test_bad_region_is_flagged():
    rec = _make_record(region="narnia")
    errs = _check([rec])
    assert any("region" in e and "narnia" in e for e in errs), errs


def test_bad_tier_is_flagged():
    rec = _make_record(tier="legendary")
    errs = _check([rec])
    assert any("tier" in e and "legendary" in e for e in errs), errs


def test_missing_source_url_is_flagged():
    data = {"records": [_make_record()]}  # no _provenance
    errs = vdr.check_diary_rewards(data, _ITEM_IDS, _ITEM_TRADEABLE, skill_ids=_SKILL_IDS)
    assert any("provenance" in e or "source_url" in e for e in errs), errs


# --- Fix: skill-resolution check ---

def test_skill_target_with_valid_skill_passes():
    """Effect targeting a known skill passes when skill_ids is provided."""
    rec = _make_record()
    rec["effects"][0]["target"] = {"kind": "skill", "name": "Slayer"}
    errs = _check([rec], skill_ids=_SKILL_IDS)
    assert errs == [], errs


def test_skill_target_with_unknown_skill_is_flagged():
    """Effect targeting an unknown skill is flagged when skill_ids is provided."""
    rec = _make_record()
    rec["effects"][0]["target"] = {"kind": "skill", "name": "FakeSkill"}
    errs = _check([rec], skill_ids=_SKILL_IDS)
    assert any("FakeSkill" in e for e in errs), errs


def test_skill_target_without_skill_ids_skips_check():
    """When skill_ids is empty (frozenset()), the skill-name check is skipped."""
    rec = _make_record()
    rec["effects"][0]["target"] = {"kind": "skill", "name": "FakeSkill"}
    errs = _check([rec], skill_ids=frozenset())
    assert errs == [], errs


def test_lamp_eligible_skills_non_any_is_flagged():
    """lamp.eligible_skills other than 'any' is flagged (minor coverage gap)."""
    rec = _make_record()
    rec["lamp"]["eligible_skills"] = "Prayer"
    errs = _check([rec])
    assert any("eligible_skills" in e for e in errs), errs


# --- Committed seed ---

def test_committed_seed_passes():
    rc = vdr.main([])
    assert rc == 0
