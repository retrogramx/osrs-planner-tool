#!/usr/bin/env python3
"""Quest-reward structural validator (spec §10,§11; quest-foundation Task 6).

Committed, deterministic guard over data/quest_rewards.json + data/completion_goals.json.
Checks STRUCTURE + referential integrity (NOT editorial truth — that is the owner's
review). Mirrors the data/validate_*.py idiom: pure check_* + main() exit 0/1.

Usage:  ./venv/bin/python data/validate_quest_rewards.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REWARDS_PATH = os.path.join(ROOT, "data", "quest_rewards.json")
GOALS_PATH = os.path.join(ROOT, "data", "completion_goals.json")
ITEMS_PATH = os.path.join(ROOT, "data", "items_equipment.json")
QUESTS_PATH = os.path.join(ROOT, "data", "quests.json")

_REWARD_TYPES = {"xp", "items", "unlock", "cosmetic"}
_XP_FORMS = {"fixed", "choice_lamp", "special"}
_UNLOCK_CATEGORIES = {
    "skill", "equipment", "skilling-method", "magic", "spellbook", "prayer",
    "location", "area", "transportation", "guild", "shortcut", "monster",
    "slayer", "minigame", "shop", "respawn-point", "area-effect",
}
_STAGES = {"started", "in_progress", "completed"}
_EFFECT_KINDS = {
    "stat_multiplier", "rate_multiplier", "capacity_change", "fee_waiver",
    "behavior_toggle", "recurring_resource", "access",
}
_COUNTER_TYPES = {"points", "member_count", "tier_count"}


def check_quest_rewards(reward_data: dict, goal_data: dict, item_ids: set,
                        item_tradeable: dict, quest_names: set) -> list[str]:
    errors: list[str] = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    check(reward_data.get("_provenance", {}).get("source_urls"),
          "quest_rewards: _provenance.source_urls missing or empty")

    granted_item_ids: dict[str, set] = {}  # quest -> set(item_id) granted (for effect cross-check)
    for rec in reward_data.get("records", []):
        q = rec.get("quest")
        check(q in quest_names, f"quest_rewards: quest {q!r} resolves to no quest record")
        granted_item_ids.setdefault(q, set())

        qp = rec.get("quest_points")
        check(qp is None or (isinstance(qp, int) and qp >= 0),
              f"quest_rewards: {q!r} quest_points {qp!r} must be a non-negative int")

        for rw in rec.get("rewards", []):
            rt = rw.get("reward_type")
            check(rt in _REWARD_TYPES, f"quest_rewards: {q!r} bad reward_type {rt!r}")
            if rt == "xp":
                check(rw.get("form") in _XP_FORMS, f"quest_rewards: {q!r} bad xp form {rw.get('form')!r}")
                check(isinstance(rw.get("amount"), int) and rw["amount"] > 0,
                      f"quest_rewards: {q!r} xp amount must be a positive int, got {rw.get('amount')!r}")
                if rw.get("form") == "fixed":
                    check(rw.get("skill"), f"quest_rewards: {q!r} fixed xp missing skill")
            elif rt == "items":
                iid = rw.get("item_id")
                check(iid in item_ids,
                      f"quest_rewards: {q!r} item reward item_id {iid!r} resolves to no items_equipment item")
                if iid in item_ids:
                    granted_item_ids[q].add(iid)          # register regardless of the tradeable field
                    if "tradeable" in rw:
                        check(bool(rw["tradeable"]) == bool(item_tradeable.get(iid)),
                              f"quest_rewards: {q!r} item {iid} tradeable={rw['tradeable']} "
                              f"disagrees with items_equipment ({item_tradeable.get(iid)})")
            elif rt == "unlock":
                check(rw.get("category") in _UNLOCK_CATEGORIES,
                      f"quest_rewards: {q!r} bad unlock category {rw.get('category')!r}")
                check(rw.get("stage") in _STAGES,
                      f"quest_rewards: {q!r} bad unlock stage {rw.get('stage')!r}")
            elif rt == "cosmetic":
                check(rw.get("kind"), f"quest_rewards: {q!r} cosmetic missing kind")

        for ef in rec.get("effects", []):
            check(ef.get("effect_kind") in _EFFECT_KINDS,
                  f"quest_rewards: {q!r} bad effect_kind {ef.get('effect_kind')!r}")
            iid = ef.get("rides_on_item_id")
            check(iid in item_ids,
                  f"quest_rewards: {q!r} effect rides_on_item_id {iid!r} resolves to no item")
            # The effect's item should be granted by the same quest (or disclosed otherwise).
            check(iid in granted_item_ids.get(q, set()) or ef.get("rides_on_external"),
                  f"quest_rewards: {q!r} effect rides on item {iid} that this quest does not grant "
                  f"(set rides_on_external:true to disclose an intentional cross-reference)")

    for rec in goal_data.get("records", []):
        gid = rec.get("id", "?")
        check(str(gid).startswith("goal:"), f"completion_goals: id {gid!r} must start with 'goal:'")
        check(rec.get("counter_type") in _COUNTER_TYPES,
              f"completion_goals: {gid!r} bad counter_type {rec.get('counter_type')!r}")
        thr = rec.get("thresholds")
        check(isinstance(thr, list) and thr and all(isinstance(t, int) and t > 0 for t in thr),
              f"completion_goals: {gid!r} thresholds must be a non-empty list of positive ints, got {thr!r}")
    return errors


def main(argv=None) -> int:
    with open(REWARDS_PATH, encoding="utf-8") as f:
        reward_data = json.load(f)
    goal_data = {"records": []}
    if os.path.exists(GOALS_PATH):
        with open(GOALS_PATH, encoding="utf-8") as f:
            goal_data = json.load(f)
    with open(ITEMS_PATH, encoding="utf-8") as f:
        items = json.load(f)["records"]
    item_ids = {r["item_id"] for r in items if r.get("item_id") is not None}
    item_tradeable = {r["item_id"]: bool(r.get("tradeable"))
                      for r in items if r.get("item_id") is not None}
    with open(QUESTS_PATH, encoding="utf-8") as f:
        quest_names = {r["name"] for r in json.load(f)["records"]
                       if r.get("node_type") in ("quest", "miniquest")}

    errors = check_quest_rewards(reward_data, goal_data, item_ids, item_tradeable, quest_names)
    if errors:
        print(f"QUEST-REWARDS VALIDATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1
    print("QUEST-REWARDS VALIDATION PASSED — reward/goal structure + references hold.")
    print(f"  quest reward records: {len(reward_data.get('records', []))}")
    print(f"  completion goals: {len(goal_data.get('records', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
