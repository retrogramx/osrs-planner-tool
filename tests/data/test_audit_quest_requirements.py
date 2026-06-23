"""Tests for data/audit_quest_requirements.py — the quest-requirement correctness audit."""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "audit_quest_requirements.py")
_spec = importlib.util.spec_from_file_location("audit_quest_requirements", _PATH)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def _rec(name, prereqs=(), skills=()):
    return {"name": name, "node_type": "quest",
            "prereqs": [{"quest": q, "stage": s} for q, s in prereqs],
            "skill_reqs": [{"skill": sk, "level": lv, "ironman": ir, "boostable": bo}
                           for sk, lv, ir, bo in skills]}


def test_identical_records_have_no_diff():
    a = [_rec("Cook's Assistant", skills=[("Cooking", 10, False, False)])]
    report = audit.diff_records(a, [dict(r) for r in a])
    assert report["missing_in_committed"] == []
    assert report["extra_in_committed"] == []
    assert report["changed"] == []


def test_changed_skill_level_is_flagged():
    committed = [_rec("Druidic Ritual", skills=[("Herblore", 3, False, False)])]
    reparsed = [_rec("Druidic Ritual", skills=[("Herblore", 31, False, False)])]
    report = audit.diff_records(committed, reparsed)
    assert [c["name"] for c in report["changed"]] == ["Druidic Ritual"]
    assert report["missing_in_committed"] == [] and report["extra_in_committed"] == []


def test_missing_and_extra_quests_are_flagged():
    committed = [_rec("A"), _rec("B")]
    reparsed = [_rec("A"), _rec("C")]
    report = audit.diff_records(committed, reparsed)
    assert report["missing_in_committed"] == ["C"]   # in source, absent from committed
    assert report["extra_in_committed"] == ["B"]     # in committed, absent from source


def test_committed_data_reproduces_from_raw():
    # The offline regression: committed data/quests.json == re-parse of committed raw.
    report = audit.audit_offline()
    assert report["missing_in_committed"] == [], report["missing_in_committed"]
    assert report["extra_in_committed"] == [], report["extra_in_committed"]
    assert report["changed"] == [], [c["name"] for c in report["changed"]]
