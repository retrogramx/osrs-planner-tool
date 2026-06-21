# tests/test_api_profile.py
from fastapi.testclient import TestClient
import osrs_planner.api as apimod
from osrs_planner.api import app
from osrs_planner.profile import Profile, SkillEntry, GoalStatus
from osrs_planner.hiscores import PlayerNotFoundError, HiscoresError

client = TestClient(app)

def _fake_profile(rsn, goal_id=None):
    return Profile(rsn=rsn, account_type="ironman", total_level=1000,
                   skills=[SkillEntry(name="Attack", level=75, xp=7500)],
                   goals=[GoalStatus(node_id="quest:cold-war", label="Cold War", status="blocked", steps=[])])

def test_profile_endpoint_ok(monkeypatch):
    monkeypatch.setattr(apimod, "build_profile", _fake_profile)
    r = client.get("/accounts/Tiger0295/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["rsn"] == "Tiger0295" and body["account_type"] == "ironman"
    assert body["goals"][0]["label"] == "Cold War"

def test_profile_endpoint_not_found(monkeypatch):
    def boom(rsn, **k): raise PlayerNotFoundError("nope")
    monkeypatch.setattr(apimod, "build_profile", boom)
    r = client.get("/accounts/FakeName123/profile")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()

def test_profile_endpoint_hiscores_error(monkeypatch):
    def boom(rsn, **k): raise HiscoresError("timeout")
    monkeypatch.setattr(apimod, "build_profile", boom)
    r = client.get("/accounts/AnyPlayer/profile")
    assert r.status_code == 502
    assert "unreachable" in r.json()["detail"].lower()
