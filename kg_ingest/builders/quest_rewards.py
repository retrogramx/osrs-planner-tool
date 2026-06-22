"""Quest-reward builder (spec §3,§4,§5; quest-foundation Tasks 4-5).

build_quest_rewards(reward_records) -> (nodes, edges, groups)
Turns the data/quest_rewards.json reward overlay into reward edges. Emits NO nodes
(it references existing skill:/item:/access: leaves + the goal: node from
build_completion_goals). Edge mapping per the spec reward taxonomy:
  xp(fixed)       -> GRANTS quest -> skill:<skill>      data{reward:xp,form:fixed,amount}
  xp(choice_lamp) -> GRANTS quest -> None              data{reward:xp,form:choice_lamp,...}
  items           -> GRANTS quest -> item:<id>          data{reward:items,qty,tradeable,...}
  unlock          -> GRANTS quest -> access:<slug>|None data{reward:unlock,category,stage,...}
  cosmetic        -> GRANTS quest -> None               data{reward:cosmetic,kind,name}
  quest_points(N) -> PROGRESS_TOWARDS quest -> goal:quest-point-cape data{weight:N}  (Task 5)
  effects[]       -> EFFECT item:<id> -> None           data{effect_kind,magnitude,...}

IDs (K9): builder-local group/edge ids use bands 0x50000000/0x60000000 (disjoint
from quests 0x10/0x20 and goals 0x30/0x40). assemble.rekey() re-keys to global ids.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, access_id, item_id, quest_id, skill_id

_GROUP_BAND = 0x50000000
_EDGE_BAND = 0x60000000
_QP_CAPE_GOAL = "goal:quest-point-cape"

_UNLOCK_CATEGORIES = frozenset({
    "skill", "equipment", "skilling-method", "magic", "spellbook", "prayer",
    "location", "area", "transportation", "guild", "shortcut", "monster",
    "slayer", "minigame", "shop", "respawn-point", "area-effect",
})
_REWARD_STAGES = frozenset({"started", "in_progress", "completed"})


def _eid(owner: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{owner}#reward-edge#{slot}")


def _gid(owner: str, slot: int) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner}#reward-group#{slot}")


def build_quest_rewards(
    reward_records: list[dict],
) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    for rec in reward_records:
        qid = quest_id(rec["quest"])
        slot = 0  # per-owner edge slot; rekey re-derives global ids anyway

        for rw in rec.get("rewards", []):
            rtype = rw["reward_type"]
            if rtype == "xp":
                if rw["form"] == "fixed":
                    dst = skill_id(rw["skill"])
                    data = {"reward": "xp", "form": "fixed", "amount": rw["amount"]}
                else:  # choice_lamp / special: no single skill -> dst=None, carry the spec
                    dst = None
                    data = {"reward": "xp", **{k: v for k, v in rw.items()
                                               if k != "reward_type"}}
            elif rtype == "items":
                dst = item_id(rw["item_id"]) if rw.get("item_id") is not None else None
                data = {"reward": "items",
                        **{k: v for k, v in rw.items()
                           if k not in ("reward_type", "item", "item_id")}}
            elif rtype == "unlock":
                dst = access_id(rw["access"]) if rw.get("access") else None
                data = {"reward": "unlock",
                        **{k: v for k, v in rw.items()
                           if k not in ("reward_type", "access")}}
                if rw.get("access"):
                    data["access"] = rw["access"]
            elif rtype == "cosmetic":
                dst = None
                data = {"reward": "cosmetic",
                        **{k: v for k, v in rw.items() if k != "reward_type"}}
            else:
                raise ValueError(f"build_quest_rewards: unknown reward_type {rtype!r} "
                                 f"for quest {rec['quest']!r}")
            edges.append(Edge(id=_eid(qid, slot), type=EdgeType.GRANTS,
                              src=qid, dst=dst, cond_group=None, data=data))
            slot += 1

        # quest_points -> a counting contribution toward the QP cape (Task 5).
        qp = rec.get("quest_points")
        if qp:
            edges.append(Edge(id=_eid(qid, slot), type=EdgeType.PROGRESS_TOWARDS,
                              src=qid, dst=_QP_CAPE_GOAL, cond_group=None,
                              data={"weight": qp}))
            slot += 1

        # effects ride on the granted ITEM (or unlock); owner = the item node.
        for ef in rec.get("effects", []):
            iid = item_id(ef["rides_on_item_id"])
            data = {k: v for k, v in ef.items()
                    if k not in ("rides_on_item_id", "rides_on_item")}
            data["rides_on_item"] = ef.get("rides_on_item")
            edges.append(Edge(id=_eid(iid, 0), type=EdgeType.EFFECT,
                              src=iid, dst=None, cond_group=None, data=data))

    return nodes, edges, groups
