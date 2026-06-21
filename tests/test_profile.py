# tests/test_profile.py
import osrs_planner.profile as profmod
from osrs_planner.profile import build_profile, Profile
from osrs_planner.models import Account, AccountMode, Skill

def _fake_account(rsn):
    skills = {n: Skill(name=n, level=l, xp=l * 100) for n, l in
              {"Overall": 1000, "Attack": 75, "Strength": 80, "Defence": 70, "Agility": 5}.items()}
    return Account(rsn=rsn, mode=AccountMode.ironman, skills=skills)

def test_build_profile_shape_and_unknown_handling(monkeypatch):
    monkeypatch.setattr(profmod, "detect_account_type", lambda rsn, **k: AccountMode.ironman)
    monkeypatch.setattr(profmod, "fetch_stats", lambda rsn, mode: _fake_account(rsn))
    monkeypatch.setattr(profmod, "fetch_collection_log", lambda rsn: {"obtained": set()})
    p = build_profile("TestAcc")          # default goal = a skill-gated KG node
    assert isinstance(p, Profile)
    assert p.rsn == "TestAcc" and p.account_type == "ironman"
    assert p.total_level == 1000
    assert {s.name for s in p.skills} == {"Attack", "Strength", "Defence", "Agility"}  # Overall excluded
    assert len(p.goals) == 1
    g = p.goals[0]
    assert g.status in {"met", "blocked", "unknown"}
    # the goal has at least one skill blocker (low Agility=5) OR every step is met -> any way, steps are well-formed
    for step in g.steps:
        assert step.status in {"met", "unmet", "unknown"}
    assert p.clog_synced is True

def test_clog_failure_is_not_fatal(monkeypatch):
    monkeypatch.setattr(profmod, "detect_account_type", lambda rsn, **k: AccountMode.ironman)
    monkeypatch.setattr(profmod, "fetch_stats", lambda rsn, mode: _fake_account(rsn))
    def boom(rsn): raise RuntimeError("temple down")
    monkeypatch.setattr(profmod, "fetch_collection_log", boom)
    p = build_profile("TestAcc")
    assert p.clog_synced is False and isinstance(p, Profile)


def test_goal_label_resolves_to_human_name():
    # regression: KGStore exposes .node(id), not .get_node — the label must be the node name
    from osrs_planner.profile import _goal_label, DEFAULT_GOAL_NODE
    assert _goal_label("quest:mage-arena-i") == "Mage Arena I"
    assert _goal_label(DEFAULT_GOAL_NODE) != DEFAULT_GOAL_NODE   # not the raw id


import os
import pytest

@pytest.mark.skipif(os.environ.get("LIVE") != "1", reason="hits live Hiscores/Temple; run with LIVE=1")
def test_live_tiger0295_profile_has_a_real_goal():
    p = build_profile("Tiger0295")
    assert p.account_type in {"normal", "ironman", "hardcore_ironman", "ultimate_ironman"}
    assert len(p.skills) >= 23 and p.total_level > 0          # 23 classic + Sailing
    g = p.goals[0]
    assert g.label != g.node_id and g.status in {"met", "blocked", "unknown"}
    print(f"\nTiger0295: {p.account_type} total {p.total_level} | goal '{g.label}' = {g.status}, {len(g.steps)} steps")
    for s in g.steps:
        print("   ", s.status, s.label)
