"""parse_requirements_html: real money_making.json HTML -> Requirements."""
from __future__ import annotations

from osrs_planner.income.methods import parse_requirements_html, Requirements

# Verbatim skill_requirements_html from data/money_making.json "Killing blue dragons"
BLUE_DRAGONS = (
    '* <span class="scp" data-skill="Combat level" data-level="90+" '
    'style="position:relative;display:inline-block;height:1em;">'
    '[[File:Attack style icon.png|link=Combat level|alt=Combat level]] 90+ </span> recommended for [[Melee]]\n'
    '* <span class="scp" data-skill="Ranged" data-level="70+" '
    'style="position:relative;display:inline-block;height:1em;">'
    '[[File:Ranged icon.png|link=Ranged|alt=Ranged]] 70+ </span> recommended for [[Ranged]]\n'
    '* <span class="scp" data-skill="Magic" data-level="47" '
    'style="position:relative;display:inline-block;height:1em;">'
    '[[File:Magic icon.png|link=Magic|alt=Magic]] 47 </span> recommended\n'
    '* <span class="scp" data-skill="Agility" data-level="70" '
    'style="position:relative;display:inline-block;height:1em;">'
    '[[File:Agility icon.png|link=Agility|alt=Agility]] 70 </span> recommended'
)

# "Collecting mort myre fungi": skills WITHOUT data-level (no numeric gate).
NO_LEVELS = (
    '* <span class="scp" data-skill="Prayer" style="x">[[File:Prayer icon.png]] </span>\n'
    '* <span class="scp" data-skill="Construction" style="x">[[File:Construction icon.png]] </span>\n'
    '* <span class="scp" data-skill="Herblore" style="x">[[File:Herblore icon.png]] </span>'
)


def test_parses_real_blue_dragons_html():
    r = parse_requirements_html(BLUE_DRAGONS)
    # "Combat level" pseudo-skill skipped; "+" stripped; KG skill ids.
    assert r.skills == {"skill:ranged": 70, "skill:magic": 47, "skill:agility": 70}
    assert "skill:combat" not in r.skills and "skill:combat level" not in r.skills
    assert r.quests == [] and r.items == []


def test_skips_spans_without_a_level():
    r = parse_requirements_html(NO_LEVELS)
    assert r.skills == {}


def test_none_or_empty_html():
    assert parse_requirements_html(None) == Requirements()
    assert parse_requirements_html("") == Requirements()


def test_quest_html_param_extracts_wikilinks():
    r = parse_requirements_html(
        None,
        quest_html="* [[Priest in Peril]]\n* Partial completion of [[Fairytale II - Cure a Queen]] (recommended)",
    )
    assert r.quests == ["quest:priest-in-peril", "quest:fairytale-ii-cure-a-queen"]


def test_quest_none_literal():
    assert parse_requirements_html(None, quest_html="None").quests == []


def test_quest_comma_joined_with_parenthetical():
    # Managing Miscellania's real quest field shape.
    r = parse_requirements_html(None, quest_html="[[Throne of Miscellania]], [[Royal Trouble]] (recommended)")
    assert r.quests == ["quest:throne-of-miscellania", "quest:royal-trouble"]
