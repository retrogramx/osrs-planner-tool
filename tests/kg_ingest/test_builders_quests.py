"""Unit tests for kg_ingest.ids and kg_ingest.builders.quests (Task 3)."""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import (
    slugify, quest_id, skill_id, item_id, access_id, gear_loadout_id,
    group_id, edge_id,
)


def test_slugify_lowercases_and_dashes():
    assert slugify("Animal Magnetism") == "animal-magnetism"


def test_slugify_strips_punctuation_and_apostrophes():
    assert slugify("Cook's Assistant") == "cooks-assistant"
    assert slugify("Recipe for Disaster/Another Cook's Quest") == \
        "recipe-for-disaster-another-cooks-quest"


def test_id_helpers_use_locked_prefixes():
    assert quest_id("Animal Magnetism") == "quest:animal-magnetism"
    assert skill_id("Crafting") == "skill:crafting"
    assert item_id(4587) == "item:4587"
    assert item_id("6528") == "item:6528"
    assert access_id("Fairy rings") == "access:fairy-rings"
    assert gear_loadout_id("Infinity") == "gear_loadout:infinity"


def test_group_id_is_deterministic_and_offset_per_owner():
    a = group_id("quest:animal-magnetism", 0)
    assert a == group_id("quest:animal-magnetism", 0)
    assert a != group_id("quest:animal-magnetism", 1)
    assert a != group_id("quest:another-quest", 0)


def test_edge_id_is_deterministic_per_owner():
    assert edge_id("quest:animal-magnetism") == edge_id("quest:animal-magnetism")
    assert edge_id("quest:animal-magnetism") != edge_id("quest:another-quest")


from kg_ingest.builders.quests import build_quests


def _sample_records() -> list[dict]:
    return [
        {"name": "Animal Magnetism", "node_type": "quest",
         "prereqs": [{"quest": "Ernest the Chicken", "stage": "completed"}],
         "skill_reqs": [
             {"skill": "Crafting", "level": 19, "ironman": False, "boostable": False},
             {"skill": "Prayer", "level": 31, "ironman": True, "boostable": True}]},
        {"name": "Alfred Grimhand's Barcrawl", "node_type": "miniquest",
         "prereqs": [], "skill_reqs": []},
        {"name": "Recipe for Disaster/Another Cook's Quest", "node_type": "quest",
         "prereqs": [{"quest": "Cook's Assistant", "stage": "completed"}], "skill_reqs": []},
        {"name": "Easy Ardougne Diary", "node_type": "diary", "prereqs": [], "skill_reqs": []},
    ]


def _node_by_id(nodes, node_id):
    matches = [n for n in nodes if n.id == node_id]
    assert len(matches) == 1, f"expected exactly one {node_id}, got {len(matches)}"
    return matches[0]


def test_build_quests_returns_four_tuple_with_diaries_routed():
    nodes, edges, groups, diary_records = build_quests(_sample_records())
    node_ids = {n.id for n in nodes}
    assert "quest:animal-magnetism" in node_ids
    assert "quest:alfred-grimhands-barcrawl" in node_ids
    assert "quest:recipe-for-disaster-another-cooks-quest" in node_ids
    assert "diary:easy-ardougne-diary" not in node_ids
    assert all(not n.id.startswith("diary:") for n in nodes)
    assert diary_records == [r for r in _sample_records() if r["node_type"] == "diary"]


def test_build_quests_node_kinds_and_miniquest_flag():
    nodes, _e, _g, _d = build_quests(_sample_records())
    am = _node_by_id(nodes, "quest:animal-magnetism")
    assert am.kind is NodeKind.QUEST
    assert am.name == "Animal Magnetism"
    assert am.slug == "animal-magnetism"
    assert am.data.get("miniquest") is not True
    mini = _node_by_id(nodes, "quest:alfred-grimhands-barcrawl")
    assert mini.kind is NodeKind.QUEST
    assert mini.data.get("miniquest") is True


def test_build_quests_requires_edge_and_root_group():
    nodes, edges, groups, _d = build_quests(_sample_records())
    req_edges = [e for e in edges if e.type is EdgeType.REQUIRES]
    assert len(req_edges) == 3
    am_edges = [e for e in edges if e.src == "quest:animal-magnetism"]
    assert len(am_edges) == 1
    e = am_edges[0]
    assert e.type is EdgeType.REQUIRES
    assert e.dst is None
    assert e.id == edge_id("quest:animal-magnetism")
    root_gid = group_id("quest:animal-magnetism", 0)
    assert e.cond_group == root_gid
    root = groups[root_gid]
    assert root.op is Op.AND
    assert root.parent is None


def test_build_quests_prereq_quest_atom_state_from_stage():
    _n, _e, groups, _d = build_quests(_sample_records())
    root = groups[group_id("quest:animal-magnetism", 0)]
    quest_atoms = [c for c in root.children
                   if isinstance(c, ConditionAtom) and c.atom_type is AtomType.QUEST]
    assert len(quest_atoms) == 1
    a = quest_atoms[0]
    assert a.ref_node == "quest:ernest-the-chicken"
    assert a.data["state"] == "completed"


def test_build_quests_nonironman_skill_level_atom_with_boostable():
    _n, _e, groups, _d = build_quests(_sample_records())
    root = groups[group_id("quest:animal-magnetism", 0)]
    skill_atoms = [c for c in root.children
                   if isinstance(c, ConditionAtom) and c.atom_type is AtomType.SKILL_LEVEL]
    crafting = [a for a in skill_atoms if a.ref_node == "skill:crafting"]
    assert len(crafting) == 1
    assert crafting[0].threshold == 19
    assert crafting[0].data["boostable"] is False


def test_build_quests_empty_reqs_quest_gets_empty_and_group():
    _n, edges, groups, _d = build_quests(_sample_records())
    mini_id = "quest:alfred-grimhands-barcrawl"
    e = [e for e in edges if e.src == mini_id][0]
    root = groups[e.cond_group]
    assert root.op is Op.AND
    assert root.children == []


def test_build_quests_ironman_skill_req_wrapped_in_or_main():
    _n, _e, groups, _d = build_quests(_sample_records())
    nid = "quest:animal-magnetism"
    root = groups[group_id(nid, 0)]
    # ironman:true req (Prayer 31) must NOT appear as a bare atom on the root AND group
    bare_prayer = [c for c in root.children
                   if isinstance(c, ConditionAtom) and c.atom_type is AtomType.SKILL_LEVEL
                   and c.ref_node == "skill:prayer"]
    assert bare_prayer == []
    # it MUST be wrapped in a 2-child OR group (no NOT group needed)
    or_gid = group_id(nid, 1)
    assert or_gid in root.children
    or_group = groups[or_gid]
    assert or_group.op is Op.OR
    assert or_group.parent == group_id(nid, 0)
    assert len(or_group.children) == 2
    # child 1: account_type == "main" (family value)
    acct_atoms = [c for c in or_group.children
                  if isinstance(c, ConditionAtom) and c.atom_type is AtomType.ACCOUNT_TYPE]
    assert len(acct_atoms) == 1
    assert acct_atoms[0].data["value"] == "main"
    # child 2: the real skill_level requirement
    other = [c for c in or_group.children if c is not acct_atoms[0]]
    assert len(other) == 1
    req = other[0]
    assert isinstance(req, ConditionAtom)
    assert req.atom_type is AtomType.SKILL_LEVEL
    assert req.ref_node == "skill:prayer"
    assert req.threshold == 31
    assert req.data["boostable"] is True


def test_build_quests_ironman_wrapper_evaluates_per_family():
    from osrs_planner.engine.kg.store import InMemoryKGStore
    from osrs_planner.engine.conditions import evaluate
    from osrs_planner.engine.state import AccountState
    from osrs_planner.engine.kleene import Tri
    nodes, edges, groups, _d = build_quests(_sample_records())
    kg = InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)
    or_gid = group_id("quest:animal-magnetism", 1)
    # main (normal) → account_type=="main" TRUE → OR satisfied → req invisible
    main = AccountState(mode="normal", observable_families={"skill_level", "account_type"})
    assert evaluate(or_gid, main, kg) is Tri.TRUE
    # ironman at insufficient level → req applies and fails
    iron_low = AccountState(mode="ironman", levels={"skill:prayer": 30},
                            observable_families={"skill_level", "account_type"})
    assert evaluate(or_gid, iron_low, kg) is Tri.FALSE
    # ironman at sufficient level → req applies and passes
    iron_ok = AccountState(mode="ironman", levels={"skill:prayer": 31},
                           observable_families={"skill_level", "account_type"})
    assert evaluate(or_gid, iron_ok, kg) is Tri.TRUE
    # UIM at insufficient level → req applies (UIM is NOT main-family) → fails
    uim_low = AccountState(mode="ultimate_ironman", levels={"skill:prayer": 30},
                           observable_families={"skill_level", "account_type"})
    assert evaluate(or_gid, uim_low, kg) is Tri.FALSE
    # UIM at sufficient level → req applies and passes
    uim_ok = AccountState(mode="ultimate_ironman", levels={"skill:prayer": 31},
                          observable_families={"skill_level", "account_type"})
    assert evaluate(or_gid, uim_ok, kg) is Tri.TRUE


import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def test_build_quests_rfd_subquest_is_granular_node():
    nodes, _e, groups, _d = build_quests(_sample_records())
    sub_id = "quest:recipe-for-disaster-another-cooks-quest"
    sub = _node_by_id(nodes, sub_id)
    assert sub.kind is NodeKind.QUEST
    root = groups[group_id(sub_id, 0)]
    qa = [c for c in root.children
          if isinstance(c, ConditionAtom) and c.atom_type is AtomType.QUEST]
    assert len(qa) == 1
    assert qa[0].ref_node == "quest:cooks-assistant"


def test_build_quests_rfd_parent_requires_all_subquests_transitively():
    data = json.loads((_REPO / "data" / "quests.json").read_text())
    nodes, _e, groups, _d = build_quests(data["records"])
    node_ids = {n.id for n in nodes}
    parent_id = "quest:recipe-for-disaster"
    culi_id = "quest:recipe-for-disaster-defeating-the-culinaromancer"
    assert parent_id in node_ids
    assert culi_id in node_ids
    parent_root = groups[group_id(parent_id, 0)]
    parent_prereq_refs = {c.ref_node for c in parent_root.children
                          if isinstance(c, ConditionAtom) and c.atom_type is AtomType.QUEST}
    assert culi_id in parent_prereq_refs
    culi_root = groups[group_id(culi_id, 0)]
    culi_prereq_refs = {c.ref_node for c in culi_root.children
                        if isinstance(c, ConditionAtom) and c.atom_type is AtomType.QUEST}
    assert "quest:recipe-for-disaster-freeing-king-awowogei" in culi_prereq_refs
    assert "quest:recipe-for-disaster-freeing-the-mountain-dwarf" in culi_prereq_refs
    assert len([r for r in culi_prereq_refs
                if r.startswith("quest:recipe-for-disaster-freeing")]) == 8


def test_build_quests_on_full_dataset_counts():
    data = json.loads((_REPO / "data" / "quests.json").read_text())
    nodes, edges, groups, diaries = build_quests(data["records"])
    assert len(nodes) == 205
    assert len(diaries) == 8
    assert len([e for e in edges if e.type is EdgeType.REQUIRES]) == 205
    for n in nodes:
        assert group_id(n.id, 0) in groups
    assert len(groups) == len(set(groups.keys()))
    edge_ids = [e.id for e in edges]
    assert len(edge_ids) == len(set(edge_ids))
