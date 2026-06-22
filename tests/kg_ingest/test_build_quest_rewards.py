"""Tests for kg_ingest/builders/quest_rewards.py (quest-foundation Task 4/5)."""
from kg_ingest.builders.quest_rewards import build_quest_rewards
from osrs_planner.engine.kg.model import EdgeType


def _edges_by_type(edges, t):
    return [e for e in edges if e.type is t]


def test_fixed_xp_becomes_a_grants_edge_to_the_skill():
    rec = {"quest": "Waterfall Quest", "rewards": [
        {"reward_type": "xp", "form": "fixed", "skill": "Attack", "amount": 13750}]}
    nodes, edges, groups = build_quest_rewards([rec])
    assert nodes == []
    g = _edges_by_type(edges, EdgeType.GRANTS)
    assert len(g) == 1
    assert g[0].src == "quest:waterfall-quest" and g[0].dst == "skill:attack"
    assert g[0].data == {"reward": "xp", "form": "fixed", "amount": 13750}


def test_item_reward_becomes_a_grants_edge_to_the_item_node():
    rec = {"quest": "Recipe for Disaster", "rewards": [
        {"reward_type": "items", "item": "Barrows gloves", "item_id": 7462,
         "qty": 1, "tradeable": False}]}
    _, edges, _ = build_quest_rewards([rec])
    g = _edges_by_type(edges, EdgeType.GRANTS)[0]
    assert g.dst == "item:7462"
    assert g.data == {"reward": "items", "qty": 1, "tradeable": False}


def test_choice_lamp_has_no_dst_and_carries_eligibility():
    rec = {"quest": "Fairytale I - Growing Pains", "rewards": [
        {"reward_type": "xp", "form": "choice_lamp", "amount": 1000, "count": 1,
         "eligible_skills": ["Attack", "Strength"], "min_level": 30}]}
    _, edges, _ = build_quest_rewards([rec])
    g = _edges_by_type(edges, EdgeType.GRANTS)[0]
    assert g.dst is None and g.data["eligible_skills"] == ["Attack", "Strength"]


def test_effect_becomes_an_effect_edge_owned_by_the_item():
    rec = {"quest": "Fairytale I - Growing Pains", "rewards": [], "effects": [
        {"rides_on_item": "Magic secateurs", "rides_on_item_id": 7409,
         "effect_kind": "rate_multiplier", "magnitude": 0.10,
         "target": "Farming herb yield", "condition": "while-wielded",
         "tier_source": "Fairytale I - Growing Pains"}]}
    _, edges, _ = build_quest_rewards([rec])
    ef = _edges_by_type(edges, EdgeType.EFFECT)
    assert len(ef) == 1 and ef[0].src == "item:7409" and ef[0].dst is None
    assert ef[0].data["effect_kind"] == "rate_multiplier" and ef[0].data["magnitude"] == 0.10


def test_unlock_with_access_targets_the_access_node():
    rec = {"quest": "Fairytale II - Cure a Queen", "rewards": [
        {"reward_type": "unlock", "category": "transportation",
         "name": "Fairy rings", "stage": "in_progress", "access": "Fairy rings"}]}
    _, edges, _ = build_quest_rewards([rec])
    g = [e for e in edges if e.type is EdgeType.GRANTS][0]
    assert g.dst == "access:fairy-rings" and g.data["stage"] == "in_progress"


def test_quest_points_becomes_progress_towards_the_cape():
    from osrs_planner.engine.kg.model import EdgeType
    rec = {"quest": "Waterfall Quest", "quest_points": 1, "rewards": []}
    _, edges, _ = build_quest_rewards([rec])
    pt = [e for e in edges if e.type is EdgeType.PROGRESS_TOWARDS]
    assert len(pt) == 1
    assert pt[0].src == "quest:waterfall-quest"
    assert pt[0].dst == "goal:quest-point-cape" and pt[0].data == {"weight": 1}
