"""Tests for data/verify_diary_rewards.py — diary reward source-grounding gate."""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "verify_diary_rewards.py")
_spec = importlib.util.spec_from_file_location("verify_diary_rewards", _PATH)
vdr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vdr)


# A synthetic morytania:hard reward block (pipe-delimited like the real prose).
_MORY_HARD_BLOCK = {
    "rewards_block": (
        "Morytania legs 3: | Unlimited teleports to Burgh de Rott | "
        "Bonecrusher, claimable from a ghost disciple | "
        "Antique lamp worth 15,000 experience | "
        "50% more runes from the Barrows chest"
    ),
    "source_url": "https://oldschool.runescape.wiki/w/Morytania_Diary",
    "accessed": "2026-06-17T18:22:53Z",
}


def _record(**over):
    rec = {
        "region": "morytania", "tier": "hard",
        "regional_item": {"name": "Morytania legs 3", "item_id": 13114,
                          "supersedes_item_id": 13113},
        "lamp": {"amount": 15000, "min_level": 50, "eligible_skills": "any",
                 "lamp_item": "Antique lamp (hard)"},
        "effects": [], "extra_unlocks": [],
    }
    rec.update(over)
    return rec


def _blocks():
    return {"morytania:hard": dict(_MORY_HARD_BLOCK)}


# --- token grounding ------------------------------------------------------

def test_valid_record_passes():
    disc, _ = vdr.verify_diary_rewards([_record()], _blocks())
    assert disc == []


def test_fabricated_regional_item_flagged():
    rec = _record(regional_item={"name": "Fakebracers 9", "item_id": 13114,
                                 "supersedes_item_id": None})
    disc, _ = vdr.verify_diary_rewards([rec], _blocks())
    assert any(d["label"] == "regional_item" and d["token"] == "Fakebracers 9" for d in disc)


def test_lamp_amount_must_appear():
    rec = _record(lamp={"amount": 999999, "min_level": 50, "eligible_skills": "any",
                        "lamp_item": "Antique lamp (hard)"})
    disc, _ = vdr.verify_diary_rewards([rec], _blocks())
    assert any(d["label"] == "lamp" and d["token"] == "999,999" for d in disc)


def test_lamp_amount_comma_formatted_match():
    # 15000 -> "15,000" which IS in the block.
    disc, _ = vdr.verify_diary_rewards([_record()], _blocks())
    assert all(d["label"] != "lamp" for d in disc)


def test_fabricated_extra_unlock_flagged():
    rec = _record(extra_unlocks=[{"reward_type": "items", "name": "Phantom widget",
                                  "item_id": None, "untracked": True}])
    disc, _ = vdr.verify_diary_rewards([rec], _blocks())
    assert any(d["label"] == "extra_unlock" and d["token"] == "Phantom widget" for d in disc)


def test_grounded_extra_unlock_passes():
    rec = _record(extra_unlocks=[{"reward_type": "items", "name": "Bonecrusher",
                                  "item_id": None, "untracked": True}])
    disc, _ = vdr.verify_diary_rewards([rec], _blocks())
    assert disc == []


def test_effect_source_token_flagged_when_absent():
    rec = _record(effects=[{"effect_kind": "rate_multiplier", "magnitude": 0.5,
                            "source_token": "90% more runes from the Barrows chest",
                            "target": {"kind": "activity", "name": "Barrows"},
                            "tier_source": "morytania:hard"}])
    disc, _ = vdr.verify_diary_rewards([rec], _blocks())
    assert any(d["label"] == "effect" for d in disc)


def test_effect_source_token_grounded_passes():
    rec = _record(effects=[{"effect_kind": "rate_multiplier", "magnitude": 0.5,
                            "source_token": "50% more runes from the Barrows chest",
                            "target": {"kind": "activity", "name": "Barrows"},
                            "tier_source": "morytania:hard"}])
    disc, _ = vdr.verify_diary_rewards([rec], _blocks())
    assert disc == []


def test_effect_without_source_token_is_skipped():
    # No source_token -> not checked (rides on the already-checked regional item).
    rec = _record(effects=[{"effect_kind": "access", "magnitude": None,
                            "target": {"kind": "region", "name": "Burgh de Rott"},
                            "tier_source": "morytania:hard"}])
    disc, _ = vdr.verify_diary_rewards([rec], _blocks())
    assert disc == []


def test_missing_cache_entry_is_fatal():
    disc, _ = vdr.verify_diary_rewards([_record()], {})  # empty cache
    assert len(disc) == 1 and "No cache entry" in disc[0]["detail"]


def test_empty_block_is_fatal():
    blocks = {"morytania:hard": {"rewards_block": "", "source_url": "", "accessed": ""}}
    disc, _ = vdr.verify_diary_rewards([_record()], blocks)
    assert len(disc) == 1 and "empty rewards_block" in disc[0]["detail"]


def test_missing_notes_report_uncaptured_bullets():
    _, notes = vdr.verify_diary_rewards([_record()], _blocks())
    # "Unlimited teleports to Burgh de Rott" is a wiki bullet with no seed token.
    assert any("Burgh de Rott" in n["wiki_line"] for n in notes)


# --- block helpers / cache ------------------------------------------------

def test_block_bullets_splits_on_pipe():
    bullets = vdr._block_bullets("Item N: | a | b | c")
    assert bullets == ["Item N:", "a", "b", "c"]


def test_build_cache_from_data_covers_48_tiers():
    blocks = vdr.build_cache_from_data()
    assert len(blocks) == 48
    assert "morytania:hard" in blocks
    assert blocks["morytania:hard"]["rewards_block"].startswith("Morytania legs 3")


def test_committed_seed_passes_offline():
    # The committed cache + committed diary_rewards.json must verify clean.
    assert vdr.main([]) == 0
