"""Tests for data/verify_quest_rewards.py — source-grounding fabrication gate."""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "verify_quest_rewards.py")
_spec = importlib.util.spec_from_file_location("verify_quest_rewards", _PATH)
vqr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vqr)


# ---------------------------------------------------------------------------
# Fixtures — rewards_block is the ALREADY-EXTRACTED ==Rewards== section only
# (extract_rewards_block stops at the next == heading, so "Required for
# completing" never appears in a real extracted block).
# ---------------------------------------------------------------------------

_WATERFALL_BLOCK = {
    "rewards_block": (
        "==Rewards==\n"
        "{{Quest rewards\n"
        "|name = Waterfall Quest\n"
        "|qp = 1\n"
        "|rewards = * {{SCP|Strength|13,750}} [[Strength]] experience\n"
        "*{{SCP|Attack|13,750}} [[Attack]] experience\n"
        "*2 [[Diamond]]s\n"
        "}}"
    ),
    "source_url": "https://oldschool.runescape.wiki/w/Waterfall_Quest",
    "accessed": "2026-06-22",
}

# Correctly extracted Demon Slayer rewards block — does NOT include the
# "Required for completing" section (which is where "Shadow of the Storm"
# actually appears on the wiki page).
_DEMON_SLAYER_BLOCK = {
    "rewards_block": (
        "==Rewards==\n"
        "{{Quest rewards\n"
        "|name = Demon Slayer\n"
        "|qp = 3\n"
        "|rewards =\n"
        "*[[Silverlight]] (if lost, players may retrieve it from [[Sir Prysin]] for a fee of 500 [[coins]].)\n"
        "}}"
    ),
    "source_url": "https://oldschool.runescape.wiki/w/Demon_Slayer",
    "accessed": "2026-06-22",
}

_DRUIDIC_BLOCK = {
    "rewards_block": (
        "==Rewards==\n"
        "{{Quest rewards\n"
        "|name = Druidic Ritual\n"
        "|qp = 4\n"
        "|rewards = \n"
        "* {{SCP|Herblore|250}} [[Herblore]] [[experience]]\n"
        "*The ability to use the [[Herblore]] [[Skills|skill]]\n"
        "}}"
    ),
    "source_url": "https://oldschool.runescape.wiki/w/Druidic_Ritual",
    "accessed": "2026-06-22",
}

_BELOW_ICE_BLOCK = {
    "rewards_block": (
        "==Rewards==\n"
        "{{Quest rewards\n"
        "|name = Below Ice Mountain\n"
        "|qp = 1\n"
        "|rewards =\n"
        "*2,000 coins\n"
        "*Access to the [[Ruins of Camdozaal]]\n"
        "*[[Flex]] emote\n"
        "}}"
    ),
    "source_url": "https://oldschool.runescape.wiki/w/Below_Ice_Mountain",
    "accessed": "2026-06-22",
}


# ---------------------------------------------------------------------------
# extract_rewards_block
# ---------------------------------------------------------------------------

def test_extract_rewards_block_captures_rewards_section():
    wikitext = (
        "==Walkthrough==\nSome text.\n\n"
        "==Rewards==\n"
        "{{Quest rewards|qp=1|rewards=*[[Silverlight]]}}\n"
        "\n==Required for completing==\n"
        "*[[Shadow of the Storm]]\n"
    )
    block = vqr.extract_rewards_block(wikitext)
    assert "Silverlight" in block
    # Section after "Required for completing" must NOT be in the block
    assert "Shadow of the Storm" not in block


def test_extract_rewards_block_excludes_required_for_completing():
    """Critical block-scoping check: the fabricated Demon Slayer example.
    'Shadow of the Storm' lives under 'Required for completing', NOT Rewards.
    The extractor must stop at the next == heading."""
    wikitext = (
        "==Rewards==\n"
        "{{Quest rewards|qp=3|rewards=*[[Silverlight]]}}\n"
        "\n==Required for completing==\n"
        "*[[Shadow of the Storm]]\n"
    )
    block = vqr.extract_rewards_block(wikitext)
    assert "Silverlight" in block
    assert "Shadow of the Storm" not in block


def test_extract_rewards_block_returns_empty_when_missing():
    block = vqr.extract_rewards_block("==Walkthrough==\nNo rewards section here.\n")
    assert block == ""


# ---------------------------------------------------------------------------
# source_tokens
# ---------------------------------------------------------------------------

def test_source_tokens_items():
    rw = {"reward_type": "items", "item": "Barrows gloves", "item_id": 7462}
    assert vqr.source_tokens(rw) == ["Barrows gloves"]


def test_source_tokens_xp_fixed():
    rw = {"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750}
    tokens = vqr.source_tokens(rw)
    assert "Attack" in tokens
    assert "13,750" in tokens


def test_source_tokens_xp_lamp():
    rw = {"reward_type": "xp", "form": "choice_lamp", "amount": 2500}
    tokens = vqr.source_tokens(rw)
    assert "2,500" in tokens
    assert len(tokens) == 1


def test_source_tokens_unlock_uses_access():
    rw = {"reward_type": "unlock", "name": "Fairy ring network", "access": "Fairy rings",
          "category": "transportation", "stage": "completed"}
    tokens = vqr.source_tokens(rw)
    assert "Fairy rings" in tokens


def test_source_tokens_unlock_uses_source_token_escape_hatch():
    rw = {"reward_type": "unlock", "name": "Herblore skill access", "access": "Herblore skill",
          "source_token": "Herblore", "category": "skill", "stage": "completed"}
    tokens = vqr.source_tokens(rw)
    assert tokens == ["Herblore"]


def test_source_tokens_cosmetic():
    rw = {"reward_type": "cosmetic", "kind": "emote", "name": "Flex"}
    assert vqr.source_tokens(rw) == ["Flex"]


def test_source_tokens_effect_skipped():
    rw = {"reward_type": "effect"}
    assert vqr.source_tokens(rw) == []


def test_source_tokens_explicit_source_token_wins():
    """Escape hatch: explicit source_token overrides all derivation."""
    rw = {"reward_type": "items", "item": "Some Item", "source_token": "specific phrase"}
    assert vqr.source_tokens(rw) == ["specific phrase"]


# ---------------------------------------------------------------------------
# verify_quest_rewards — fabrication detection
# ---------------------------------------------------------------------------

def test_fabricated_item_reward_is_flagged():
    """An item reward whose name is NOT in the rewards block is a fabrication."""
    records = [{
        "quest": "Demon Slayer",
        "rewards": [
            {"reward_type": "items", "item": "Fabricated item", "item_id": 9999},
        ]
    }]
    blocks = {"Demon Slayer": _DEMON_SLAYER_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert len(discrepancies) == 1
    assert "Fabricated item" in discrepancies[0]["token"]


def test_fabricated_unlock_shadow_of_storm_is_flagged():
    """The real fabrication example: 'Shadow of the Storm' appears under
    'Required for completing' on the Demon Slayer wiki page, NOT under Rewards.
    The extracted rewards_block does NOT contain it (the extractor stops at
    the next == heading).  If added as an unlock reward, it must be caught."""
    records = [{
        "quest": "Demon Slayer",
        "rewards": [
            {"reward_type": "items", "item": "Silverlight", "item_id": 2402},
            # FAKE: this unlock's access token is not in the extracted rewards block
            {"reward_type": "unlock", "category": "area", "name": "Shadow of the Storm access",
             "access": "Shadow of the Storm", "stage": "completed"},
        ]
    }]
    # Use the correctly-extracted block (no "Required for completing" text)
    blocks = {"Demon Slayer": _DEMON_SLAYER_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    # Silverlight passes; Shadow of the Storm is caught as fabricated
    assert any("Shadow of the Storm" in d["token"] for d in discrepancies)
    # Silverlight must NOT be in discrepancies
    assert not any("Silverlight" in (d.get("token") or "") for d in discrepancies)


def test_real_reward_passes():
    """A correctly grounded item reward passes without discrepancy."""
    records = [{
        "quest": "Demon Slayer",
        "rewards": [
            {"reward_type": "items", "item": "Silverlight", "item_id": 2402},
        ]
    }]
    blocks = {"Demon Slayer": _DEMON_SLAYER_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert discrepancies == []


def test_real_xp_reward_passes():
    """A correctly grounded fixed-XP reward passes."""
    records = [{
        "quest": "Waterfall Quest",
        "rewards": [
            {"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750},
        ]
    }]
    blocks = {"Waterfall Quest": _WATERFALL_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert discrepancies == []


def test_wrong_xp_amount_is_flagged():
    """If the amount in the seed doesn't match what's in the wiki block, it's flagged."""
    records = [{
        "quest": "Waterfall Quest",
        "rewards": [
            {"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 99999},
        ]
    }]
    blocks = {"Waterfall Quest": _WATERFALL_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert any("99,999" in d["token"] for d in discrepancies)


def test_missing_cache_entry_is_fatal():
    """A quest in the seed with no cache entry is a FATAL discrepancy."""
    records = [{"quest": "Unknown Quest", "rewards": []}]
    blocks = {}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert len(discrepancies) == 1
    assert "Unknown Quest" in discrepancies[0]["quest"]


def test_source_token_escape_hatch_must_still_be_present():
    """A source_token that is NOT in the block still fails — escape hatch
    controls WHAT token is checked, but cannot bypass the check itself."""
    records = [{
        "quest": "Druidic Ritual",
        "rewards": [
            {"reward_type": "unlock", "name": "Herblore skill access",
             "access": "Herblore skill", "source_token": "NOT_IN_BLOCK",
             "category": "skill", "stage": "completed"},
        ]
    }]
    blocks = {"Druidic Ritual": _DRUIDIC_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert any("NOT_IN_BLOCK" in d["token"] for d in discrepancies)


def test_source_token_escape_hatch_present_passes():
    """A source_token that IS in the block passes."""
    records = [{
        "quest": "Druidic Ritual",
        "rewards": [
            {"reward_type": "unlock", "name": "Herblore skill access",
             "access": "Herblore skill", "source_token": "Herblore",
             "category": "skill", "stage": "completed"},
        ]
    }]
    blocks = {"Druidic Ritual": _DRUIDIC_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert discrepancies == []


def test_cosmetic_flex_passes():
    """A cosmetic reward with a name present in the block passes."""
    records = [{
        "quest": "Below Ice Mountain",
        "rewards": [
            {"reward_type": "cosmetic", "kind": "emote", "name": "Flex"},
        ]
    }]
    blocks = {"Below Ice Mountain": _BELOW_ICE_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert discrepancies == []


def test_missing_notes_are_informational_only():
    """Wiki bullets with no matching seed reward generate missing_notes, not discrepancies."""
    records = [{
        "quest": "Waterfall Quest",
        "rewards": [
            {"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750},
        ]
    }]
    # Block has Strength XP + Diamond + Gold bar bullets that the seed omits
    blocks = {"Waterfall Quest": _WATERFALL_BLOCK}
    discrepancies, missing_notes = vqr.verify_quest_rewards(records, blocks)
    assert discrepancies == []
    assert any("Diamond" in mn["wiki_line"] for mn in missing_notes)


def test_case_insensitive_token_matching():
    """Token matching is case-insensitive."""
    records = [{
        "quest": "Below Ice Mountain",
        "rewards": [
            {"reward_type": "unlock", "name": "Ruins of Camdozaal",
             "access": "ruins of camdozaal",  # lower-case
             "category": "area", "stage": "completed"},
        ]
    }]
    blocks = {"Below Ice Mountain": _BELOW_ICE_BLOCK}
    discrepancies, _ = vqr.verify_quest_rewards(records, blocks)
    assert discrepancies == []


# ---------------------------------------------------------------------------
# Full committed seed — integration test
# ---------------------------------------------------------------------------

def test_committed_seed_passes_verifier():
    """The real committed 14-quest seed must pass with 0 discrepancies."""
    rc = vqr.main([])
    assert rc == 0
