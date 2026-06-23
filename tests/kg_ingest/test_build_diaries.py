"""kg_ingest/builders/diaries.py — diary tier nodes + requirement gates (diaries Task 2+)."""
from kg_ingest.builders.diaries import _parse_compound_quest_req, build_diaries
from osrs_planner.engine.kg.model import AtomType, ConditionAtom, EdgeType, NodeKind


def _tasks():
    return [
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 1, "task": "T1",
         "requirements": {"skills": [{"skill": "Thieving", "level": 5}], "quests": [], "items": []},
         "boostable": False, "reward": "Ardougne cloak 1:", "source_url": "u"},
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 2, "task": "T2",
         "requirements": {"skills": [{"skill": "Thieving", "level": 25}],
                          "quests": ["Completion of Biohazard"], "items": []},
         "boostable": False, "reward": "Ardougne cloak 1:", "source_url": "u"},
    ]


def test_one_tier_node_per_region_tier():
    nodes, edges, groups = build_diaries(_tasks())
    diary_nodes = [n for n in nodes if n.kind is NodeKind.DIARY]
    assert [n.id for n in diary_nodes] == ["diary:ardougne:easy"]
    n = diary_nodes[0]
    assert n.data["region"] == "ardougne" and n.data["tier"] == "easy"
    assert len(n.data["tasks"]) == 2  # per-task list retained for route detail


def test_tier_requires_edge_aggregates_max_skill_and_union_quests():
    nodes, edges, groups = build_diaries(_tasks())
    req = [e for e in edges if e.type is EdgeType.REQUIRES and e.src == "diary:ardougne:easy"][0]
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    skill = [a for a in atoms if a.atom_type is AtomType.SKILL_LEVEL]
    quest = [a for a in atoms if a.atom_type is AtomType.QUEST]
    assert len(skill) == 1 and skill[0].ref_node == "skill:thieving" and skill[0].threshold == 25  # MAX level
    assert len(quest) == 1 and quest[0].ref_node == "quest:biohazard"


def test_quest_atom_state_is_completed_for_completion_of_prefix():
    nodes, edges, groups = build_diaries(_tasks())
    req = [e for e in edges if e.type is EdgeType.REQUIRES and e.src == "diary:ardougne:easy"][0]
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    quest = [a for a in atoms if a.atom_type is AtomType.QUEST]
    assert len(quest) == 1 and quest[0].data["state"] == "completed"


def test_started_prefix_yields_in_progress_state():
    tasks = [
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 1, "task": "T1",
         "requirements": {"skills": [], "quests": ["Started Fairytale II - Cure a Queen"], "items": []},
         "boostable": False, "reward": "r", "source_url": "u"},
    ]
    nodes, edges, groups = build_diaries(tasks)
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    quest = [a for a in atoms if a.atom_type is AtomType.QUEST]
    assert len(quest) == 1
    assert quest[0].data["state"] == "in_progress"


def test_non_prefixed_entry_is_skipped_and_counted():
    """Non-quest mis-filed entries (no recognized prefix) are skipped + counted."""
    tasks = [
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 1, "task": "T1",
         "requirements": {"skills": [], "quests": ["Machete", "Completion of Biohazard"], "items": []},
         "boostable": False, "reward": "r", "source_url": "u"},
    ]
    nodes, edges, groups = build_diaries(tasks)
    diary_node = next(n for n in nodes if n.kind is NodeKind.DIARY)
    # "Machete" has no recognized prefix → skipped
    assert diary_node.data["skipped_quest_reqs"] >= 1
    # "Completion of Biohazard" is recognized → quest atom present
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    quest = [a for a in atoms if a.atom_type is AtomType.QUEST]
    assert len(quest) == 1 and quest[0].ref_node == "quest:biohazard"


def test_same_quest_at_multiple_states_keeps_strictest():
    """If a quest appears at both in_progress and completed across tasks, keep completed."""
    tasks = [
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 1, "task": "T1",
         "requirements": {"skills": [], "quests": ["Started Biohazard"], "items": []},
         "boostable": False, "reward": "r", "source_url": "u"},
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 2, "task": "T2",
         "requirements": {"skills": [], "quests": ["Completion of Biohazard"], "items": []},
         "boostable": False, "reward": "r", "source_url": "u"},
    ]
    nodes, edges, groups = build_diaries(tasks)
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    quest = [a for a in atoms if a.atom_type is AtomType.QUEST]
    assert len(quest) == 1
    assert quest[0].data["state"] == "completed"


def test_items_not_included_in_requirement_gate():
    """items[] are consumable/recommended, not hard gates — must not appear as atoms."""
    tasks = [
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 1, "task": "T1",
         "requirements": {"skills": [], "quests": [], "items": ["Rope", "Pickaxe"]},
         "boostable": False, "reward": "r", "source_url": "u"},
    ]
    nodes, edges, groups = build_diaries(tasks)
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    assert len(atoms) == 0  # no atoms: items excluded, no skills/quests


def test_no_requires_edge_emitted_when_tier_has_no_reqs():
    """Tiers with no skill/quest reqs still get a REQUIRES edge (empty AND group is valid gate)."""
    tasks = [
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 1, "task": "T1",
         "requirements": {"skills": [], "quests": [], "items": []},
         "boostable": False, "reward": "r", "source_url": "u"},
    ]
    nodes, edges, groups = build_diaries(tasks)
    requires = [e for e in edges if e.type is EdgeType.REQUIRES]
    assert len(requires) == 1


# ---------------------------------------------------------------------------
# Compound quest-req parsing tests (Fix 1)
# ---------------------------------------------------------------------------

def _slugs(*names: str) -> frozenset[str]:
    """Build a minimal known_slugs set from bare quest names."""
    from kg_ingest.ids import slugify
    return frozenset(f"quest:{slugify(n)}" for n in names)


def test_partial_completion_of_prefix_yields_in_progress():
    """'Partial completion of X' → in_progress state."""
    known = _slugs("Biohazard")
    result, skipped = _parse_compound_quest_req("Partial completion of Biohazard", known)
    assert skipped == 0
    assert result == {"quest:biohazard": "in_progress"}


def test_partial_prefix_yields_in_progress():
    """'Partial X' → in_progress state (no 'completion of' needed)."""
    known = _slugs("Biohazard")
    result, skipped = _parse_compound_quest_req("Partial Biohazard", known)
    assert skipped == 0
    assert result == {"quest:biohazard": "in_progress"}


def test_compound_one_quest_one_non_quest():
    """Compound where one part is a real quest and the other is not.

    'Completion of Biohazard and the Fishing Colony' splits into:
      - 'Biohazard'        → quest:biohazard (completed)
      - 'the Fishing Colony' → unresolvable (skipped + counted)
    The overall skipped_quest_reqs should be 1 (the non-quest part).
    """
    known = _slugs("Biohazard")  # 'the Fishing Colony' intentionally absent
    result, skipped = _parse_compound_quest_req(
        "Completion of Biohazard and the Fishing Colony", known
    )
    assert result == {"quest:biohazard": "completed"}
    assert skipped == 1


def test_compound_two_real_quests_with_sub_prefix():
    """Compound 'Completion of A and having started B' → two atoms, A completed + B in_progress.

    Uses The Fremennik Trials (completed) and Fairytale II - Cure a Queen (in_progress),
    matching the real Fremennik medium diary requirement.
    """
    known = _slugs("The Fremennik Trials", "Fairytale II - Cure a Queen")
    result, skipped = _parse_compound_quest_req(
        "Completion of The Fremennik Trials and having started Fairytale II - Cure a Queen",
        known,
    )
    assert skipped == 0
    assert result.get("quest:the-fremennik-trials") == "completed"
    assert result.get("quest:fairytale-ii-cure-a-queen") == "in_progress"


def test_quest_name_containing_and_is_not_split():
    """A quest whose name contains 'and' must not be split.

    'Skippy and the Mogres' is a real quest (quest:skippy-and-the-mogres).
    The whole-name-first strategy must preserve it.
    """
    known = _slugs("Skippy and the Mogres")
    result, skipped = _parse_compound_quest_req("Completion of Skippy and the Mogres", known)
    assert skipped == 0
    assert result == {"quest:skippy-and-the-mogres": "completed"}


def test_no_recognized_prefix_skipped_and_counted():
    """Entry with no recognized outer prefix → skipped + counted (skipped=1, resolved={})."""
    known = _slugs("Biohazard")
    result, skipped = _parse_compound_quest_req("Machete", known)
    assert result == {}
    assert skipped == 1


def test_compound_quest_req_integration_via_build_diaries():
    """Integration: build_diaries resolves compound reqs in real diary tasks.

    Fremennik medium contains:
      'Completion of The Fremennik Trials and having started Fairytale II - Cure a Queen'
    Both are real quests; they should appear as atoms (no longer fully skipped).
    """
    import json
    data = json.loads(open("data/achievement_diaries.json").read())
    nodes, edges, groups = build_diaries(data["records"])
    total_skipped = sum(n.data["skipped_quest_reqs"] for n in nodes)
    # Was 18 before compound splitting; 8 compounds partially/fully resolved → now 10.
    assert total_skipped == 10
    # Fremennik medium should have quest atoms for both quests
    frem_medium = next(n for n in nodes if n.id == "diary:fremennik:medium")
    req = next(e for e in edges if e.src == "diary:fremennik:medium")
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    quest_ids = {a.ref_node for a in atoms if a.atom_type is AtomType.QUEST}
    assert "quest:the-fremennik-trials" in quest_ids
    assert "quest:fairytale-ii-cure-a-queen" in quest_ids


def test_each_tier_has_progress_towards_the_cape():
    from osrs_planner.engine.kg.model import EdgeType
    _, edges, _ = build_diaries(_tasks())
    pt = [e for e in edges if e.type is EdgeType.PROGRESS_TOWARDS]
    assert pt and all(e.dst == "goal:achievement-diary-cape" and e.data == {"weight": 1} for e in pt)
