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
