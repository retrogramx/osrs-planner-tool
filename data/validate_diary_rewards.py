#!/usr/bin/env python3
"""Diary-reward structural validator (Achievement Diaries brick, Task 4).

Committed, deterministic guard over data/diary_rewards.json.
Checks STRUCTURE + referential integrity (NOT editorial truth — that is the
owner's review).  Mirrors the data/validate_*.py idiom:
  pure check_diary_rewards(...) -> list[str]  +  main() -> int
  prints DIARY-REWARDS VALIDATION PASSED/FAILED, exits 0/1.

Usage:  ./venv/bin/python data/validate_diary_rewards.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REWARDS_PATH = os.path.join(ROOT, "data", "diary_rewards.json")
ITEMS_PATH = os.path.join(ROOT, "data", "items_equipment.json")
KG_NODES_PATH = os.path.join(ROOT, "kg", "nodes.json")

_REGIONS = {
    "ardougne", "desert", "falador", "fremennik", "kandarin", "karamja",
    "kourend", "lumbridge", "morytania", "varrock", "western", "wilderness",
}
_TIERS = {"easy", "medium", "hard", "elite"}
_EFFECT_KINDS = {
    "stat_multiplier", "rate_multiplier", "capacity_change", "fee_waiver",
    "behavior_toggle", "recurring_resource", "access",
}
_TARGET_KINDS = {"skill", "activity", "monster", "region", "item"}


def check_diary_rewards(
    reward_data: dict,
    item_ids: set,
    item_tradeable: dict,
    skill_ids: set = frozenset(),
    content_ids: set = frozenset(),  # noqa: B006
) -> list[str]:
    """Return a list of violation strings (empty = clean).

    skill_ids: set of valid skill display names from kg/nodes.json (kind=="skill").
    content_ids: activity/monster/region content node names — not validated here;
        non-skill content-target resolution is validated by validate_kg once
        content nodes exist (Task 6+).
    """
    # magnitude convention: bonus fraction (additive over baseline)
    # 0.1 = +10%, 0.5 = +50%, 1.0 = +100%/double
    errors: list[str] = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    # Provenance
    check(
        reward_data.get("_provenance", {}).get("source_urls"),
        "diary_rewards: _provenance.source_urls missing or empty",
    )

    for rec in reward_data.get("records", []):
        region = rec.get("region", "")
        tier = rec.get("tier", "")
        tag = f"{region}:{tier}"

        check(region in _REGIONS, f"diary_rewards: {tag!r} bad region {region!r}")
        check(tier in _TIERS, f"diary_rewards: {tag!r} bad tier {tier!r}")

        # regional_item
        ri = rec.get("regional_item", {})
        ri_id = ri.get("item_id")
        check(
            ri_id is not None and ri_id in item_ids,
            f"diary_rewards: {tag!r} regional_item.item_id {ri_id!r} resolves to no items_equipment item",
        )
        sup_id = ri.get("supersedes_item_id")
        if sup_id is not None:
            check(
                sup_id in item_ids,
                f"diary_rewards: {tag!r} supersedes_item_id {sup_id!r} resolves to no items_equipment item",
            )

        # lamp
        lamp = rec.get("lamp", {})
        lamt = lamp.get("amount")
        check(
            isinstance(lamt, int) and lamt > 0,
            f"diary_rewards: {tag!r} lamp.amount must be a positive int, got {lamt!r}",
        )
        lmin = lamp.get("min_level")
        check(
            lmin is None or (isinstance(lmin, int) and lmin > 0),
            f"diary_rewards: {tag!r} lamp.min_level must be null or a positive int, got {lmin!r}",
        )
        check(
            lamp.get("eligible_skills") == "any",
            f"diary_rewards: {tag!r} lamp.eligible_skills must be 'any', got {lamp.get('eligible_skills')!r}",
        )

        # effects
        for i, ef in enumerate(rec.get("effects", [])):
            ek = ef.get("effect_kind")
            check(
                ek in _EFFECT_KINDS,
                f"diary_rewards: {tag!r} effect[{i}] bad effect_kind {ek!r}",
            )
            mag = ef.get("magnitude")
            if mag is not None:
                check(
                    isinstance(mag, (int, float)),
                    f"diary_rewards: {tag!r} effect[{i}] magnitude must be numeric, got {mag!r}",
                )
            tgt = ef.get("target", {})
            tk = tgt.get("kind")
            check(
                tk in _TARGET_KINDS,
                f"diary_rewards: {tag!r} effect[{i}] bad target.kind {tk!r}",
            )
            if tk == "skill" and skill_ids:
                tgt_name = tgt.get("name")
                check(
                    tgt_name in skill_ids,
                    f"diary_rewards: {tag!r} effect[{i}] target skill {tgt_name!r} not in skill_ids",
                )
            ts = ef.get("tier_source")
            check(
                ts == f"{region}:{tier}",
                f"diary_rewards: {tag!r} effect[{i}] tier_source {ts!r} != expected '{region}:{tier}'",
            )

        # extra_unlocks
        for j, ul in enumerate(rec.get("extra_unlocks", [])):
            uid = ul.get("item_id")
            if uid is None:
                # null item_id — MUST be disclosed as untracked
                check(
                    ul.get("untracked") is True,
                    f"diary_rewards: {tag!r} extra_unlock[{j}] {ul.get('name')!r} has null item_id "
                    f"but is missing 'untracked': true (disclose items absent from the equipment DB)",
                )
            else:
                # non-null item_id — MUST resolve
                check(
                    uid in item_ids,
                    f"diary_rewards: {tag!r} extra_unlock[{j}] item_id {uid!r} resolves to no items_equipment item",
                )
                if uid in item_ids and "tradeable" in ul:
                    check(
                        bool(ul["tradeable"]) == bool(item_tradeable.get(uid)),
                        f"diary_rewards: {tag!r} extra_unlock[{j}] item {uid} tradeable={ul['tradeable']} "
                        f"disagrees with items_equipment ({item_tradeable.get(uid)})",
                    )

    return errors


def main(argv=None) -> int:
    with open(REWARDS_PATH, encoding="utf-8") as f:
        reward_data = json.load(f)
    with open(ITEMS_PATH, encoding="utf-8") as f:
        items = json.load(f)["records"]
    item_ids = {r["item_id"] for r in items if r.get("item_id") is not None}
    item_tradeable = {
        r["item_id"]: bool(r.get("tradeable"))
        for r in items
        if r.get("item_id") is not None
    }
    with open(KG_NODES_PATH, encoding="utf-8") as f:
        kg_nodes = json.load(f)
    skill_ids = {n["name"] for n in kg_nodes if n.get("kind") == "skill"}

    errors = check_diary_rewards(reward_data, item_ids, item_tradeable, skill_ids=skill_ids, content_ids=frozenset())
    if errors:
        print(f"DIARY-REWARDS VALIDATION FAILED — {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1
    print("DIARY-REWARDS VALIDATION PASSED — diary reward structure + references hold.")
    print(f"  diary reward records: {len(reward_data.get('records', []))}")
    print(f"  skill_ids loaded: {len(skill_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
