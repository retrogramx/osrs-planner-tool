"""Direct unit tests for data/raw/questreq_parse.parse_questreq_lua (quest-foundation Task 1)."""
import importlib.util
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "raw", "questreq_parse.py")
_spec = importlib.util.spec_from_file_location("questreq_parse", _PATH)
questreq_parse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(questreq_parse)

_LUA = (
    "local questReqs = {\n"
    "    ['Cooks Test'] = {\n"
    "        ['quests'] = {\n"
    "            'Started:Big Quest',\n"
    "            'Done Quest',\n"
    "        },\n"
    "        ['skills'] = {\n"
    "            {'Cooking', 10},\n"
    "            {'Prayer', 31, 'ironman', 'boostable'},\n"
    "        },\n"
    "    },\n"
    "-- Insert Miniquests below here\n"
    "    ['Mini Test'] = {\n"
    "        ['skills'] = {\n"
    "            {'Slayer', 5},\n"
    "        },\n"
    "    },\n"
    "-- Insert Achievement Diaries below here\n"
    "    ['Easy Test Diary'] = {\n"
    "        ['quests'] = {\n"
    "            'Done Quest',\n"
    "        },\n"
    "    },\n"
    "}\n"
    "return questReqs\n"
)


def test_parses_quest_miniquest_and_diary_with_stages_and_flags():
    recs = {r["name"]: r for r in questreq_parse.parse_questreq_lua(_LUA)}
    assert set(recs) == {"Cooks Test", "Mini Test", "Easy Test Diary"}
    assert recs["Cooks Test"]["node_type"] == "quest"
    assert recs["Mini Test"]["node_type"] == "miniquest"
    assert recs["Easy Test Diary"]["node_type"] == "diary"
    # Started: prefix -> in_progress; bare name -> completed
    assert recs["Cooks Test"]["prereqs"] == [
        {"quest": "Big Quest", "stage": "in_progress"},
        {"quest": "Done Quest", "stage": "completed"},
    ]
    # ironman + boostable flags parsed
    assert recs["Cooks Test"]["skill_reqs"] == [
        {"skill": "Cooking", "level": 10, "ironman": False, "boostable": False},
        {"skill": "Prayer", "level": 31, "ironman": True, "boostable": True},
    ]


def test_missing_section_marker_raises():
    bad = "local questReqs = {\n    ['X'] = {\n    },\n}\n"  # no miniquest/diary markers
    with pytest.raises(ValueError, match="missing section marker"):
        questreq_parse.parse_questreq_lua(bad)
