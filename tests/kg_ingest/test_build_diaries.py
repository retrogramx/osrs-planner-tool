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


# ---------------------------------------------------------------------------
# Task 5: reward emission tests — regional item, supersedes, lamp, extra unlocks
# ---------------------------------------------------------------------------

def _reward_record_ardougne_easy():
    """Minimal ardougne-easy reward record (no supersedes_item_id, null min_level-variant)."""
    return {
        "region": "ardougne",
        "tier": "easy",
        "regional_item": {
            "name": "Ardougne cloak 1",
            "item_id": 13121,
            "supersedes_item_id": None,
        },
        "lamp": {
            "amount": 2500,
            "min_level": None,
            "eligible_skills": "any",
            "lamp_item": "Antique lamp (easy)",
        },
        "effects": [],
        "extra_unlocks": [],
    }


def _reward_record_morytania_hard():
    """Minimal morytania-hard reward record (has supersedes + extra untracked unlock)."""
    return {
        "region": "morytania",
        "tier": "hard",
        "regional_item": {
            "name": "Morytania legs 3",
            "item_id": 13114,
            "supersedes_item_id": 13113,
        },
        "lamp": {
            "amount": 15000,
            "min_level": 50,
            "eligible_skills": "any",
            "lamp_item": "Antique lamp (hard)",
        },
        "effects": [],
        "extra_unlocks": [
            {
                "reward_type": "items",
                "name": "Bonecrusher",
                "item_id": None,
                "untracked": True,
                "note": "Inventory item; not in items_equipment.json.",
            }
        ],
    }


def _tasks_for_region(region_display: str, tier: str = "easy") -> list[dict]:
    return [
        {"diary_region": region_display, "tier": tier, "task_number": 1, "task": "T1",
         "requirements": {"skills": [], "quests": [], "items": []},
         "boostable": False, "reward": "r", "source_url": "u"},
    ]


def test_regional_item_grants_edge():
    """Regional item produces GRANTS edge from tier node to item:<item_id>."""
    tasks = _tasks_for_region("Ardougne", "easy")
    rec = _reward_record_ardougne_easy()
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    grants = [e for e in edges if e.type is EdgeType.GRANTS]
    item_grants = [e for e in grants if e.dst == "item:13121"]
    assert len(item_grants) == 1
    e = item_grants[0]
    assert e.src == "diary:ardougne:easy"
    assert e.data["reward"] == "items"
    assert e.data["qty"] == 1


def test_regional_item_grants_no_internal_keys():
    """Grants edge data must not contain internal record keys (source_token, target, etc.)."""
    tasks = _tasks_for_region("Ardougne", "easy")
    rec = _reward_record_ardougne_easy()
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    item_grants = [e for e in edges if e.type is EdgeType.GRANTS and e.dst == "item:13121"]
    assert item_grants
    data = item_grants[0].data
    forbidden = {"source_token", "target", "target_facet", "item_id", "name"}
    assert not (forbidden & set(data)), f"forbidden keys found: {forbidden & set(data)}"


def test_no_supersedes_edge_when_supersedes_item_id_is_null():
    """When supersedes_item_id is None, no SUPERSEDES edge is emitted."""
    tasks = _tasks_for_region("Ardougne", "easy")
    rec = _reward_record_ardougne_easy()
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    supersedes = [e for e in edges if e.type is EdgeType.SUPERSEDES]
    assert len(supersedes) == 0


def test_supersedes_edge_emitted_when_present():
    """When supersedes_item_id is set, SUPERSEDES edge src=higher item, dst=lower item."""
    tasks = _tasks_for_region("Morytania", "hard")
    rec = _reward_record_morytania_hard()
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    supersedes = [e for e in edges if e.type is EdgeType.SUPERSEDES]
    assert len(supersedes) == 1
    e = supersedes[0]
    assert e.src == "item:13114"   # higher item supersedes
    assert e.dst == "item:13113"   # lower item


def test_choice_lamp_grants_dst_none():
    """XP lamp produces GRANTS edge with dst=None and eligible_skills='any'."""
    tasks = _tasks_for_region("Ardougne", "easy")
    rec = _reward_record_ardougne_easy()
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    lamp_grants = [e for e in edges if e.type is EdgeType.GRANTS and e.dst is None
                   and e.data.get("reward") == "xp"]
    assert len(lamp_grants) == 1
    d = lamp_grants[0].data
    assert d["form"] == "choice_lamp"
    assert d["eligible_skills"] == "any"
    assert d["amount"] == 2500
    assert d["lamp_item"] == "Antique lamp (easy)"


def test_choice_lamp_min_level_null_honored():
    """When lamp.min_level is null, the edge data has min_level=None (not omitted)."""
    tasks = _tasks_for_region("Ardougne", "easy")
    rec = _reward_record_ardougne_easy()
    assert rec["lamp"]["min_level"] is None
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    lamp_grants = [e for e in edges if e.type is EdgeType.GRANTS and e.dst is None
                   and e.data.get("reward") == "xp"]
    assert lamp_grants[0].data["min_level"] is None


def test_choice_lamp_min_level_set_when_present():
    """When lamp.min_level is set, the edge data carries it."""
    tasks = _tasks_for_region("Morytania", "hard")
    rec = _reward_record_morytania_hard()
    assert rec["lamp"]["min_level"] == 50
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    lamp_grants = [e for e in edges if e.type is EdgeType.GRANTS and e.dst is None
                   and e.data.get("reward") == "xp"]
    assert lamp_grants[0].data["min_level"] == 50


def test_untracked_extra_unlock_grants_dst_none():
    """Untracked extra_unlock (item_id=null, untracked=true) → GRANTS dst=None with name+untracked."""
    tasks = _tasks_for_region("Morytania", "hard")
    rec = _reward_record_morytania_hard()
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    # There should be a GRANTS edge for the untracked Bonecrusher
    untracked = [e for e in edges if e.type is EdgeType.GRANTS and e.dst is None
                 and e.data.get("untracked") is True]
    assert len(untracked) == 1
    d = untracked[0].data
    assert d["name"] == "Bonecrusher"
    assert d["reward"] == "items"


def test_reward_edges_do_not_contaminate_task_only_build():
    """Calling build_diaries without reward_records emits no GRANTS/SUPERSEDES edges."""
    _, edges, _ = build_diaries(_tasks())
    assert all(e.type not in (EdgeType.GRANTS, EdgeType.SUPERSEDES) for e in edges)


def test_reward_edge_slot_distinct_from_requires_and_progress_towards():
    """All edges from the same tier node must have distinct ids."""
    tasks = _tasks_for_region("Morytania", "hard")
    rec = _reward_record_morytania_hard()
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    tier_edges = [e for e in edges if e.src == "diary:morytania:hard"]
    ids = [e.id for e in tier_edges]
    assert len(ids) == len(set(ids)), f"duplicate edge ids: {ids}"


# --- Task 7: effect edges with dst = content node -------------------------

def _reward_record_with_effects():
    """Morytania-hard-style record carrying two effects: an activity-targeted
    rate_multiplier (Barrows) and a region-targeted access (Burgh de Rott)."""
    rec = _reward_record_morytania_hard()
    rec["effects"] = [
        {"effect_kind": "rate_multiplier", "magnitude": 0.5,
         "target_facet": "runes received from the Barrows chest",
         "target": {"kind": "activity", "name": "Barrows"},
         "condition": "unconditional-once-earned", "tier_source": "morytania:hard"},
        {"effect_kind": "access", "magnitude": None,
         "target_facet": "unlimited teleports to Burgh de Rott",
         "target": {"kind": "region", "name": "Burgh de Rott"},
         "condition": "unconditional-once-earned", "tier_source": "morytania:hard"},
    ]
    return rec


def test_effect_edge_rides_on_regional_item_dst_is_content_node():
    tasks = _tasks_for_region("Morytania", "hard")
    _, edges, _ = build_diaries(tasks, reward_records=[_reward_record_with_effects()])
    effects = [e for e in edges if e.type is EdgeType.EFFECT]
    barrows = [e for e in effects if e.dst == "activity:barrows"]
    assert len(barrows) == 1
    e = barrows[0]
    assert e.src == "item:13114"          # rides on the regional item
    assert e.data["effect_kind"] == "rate_multiplier"
    assert e.data["magnitude"] == 0.5
    assert e.data["tier_source"] == "morytania:hard"
    assert e.data["target_facet"] == "runes received from the Barrows chest"
    assert e.data["condition"] == "unconditional-once-earned"


def test_effect_edge_region_target_and_no_raw_target_key():
    tasks = _tasks_for_region("Morytania", "hard")
    _, edges, _ = build_diaries(tasks, reward_records=[_reward_record_with_effects()])
    region = [e for e in edges if e.type is EdgeType.EFFECT and e.dst == "region:burgh-de-rott"]
    assert len(region) == 1
    d = region[0].data
    assert d["effect_kind"] == "access"
    assert "target" not in d              # the resolved dst replaces the raw target dict
    assert "rides_on_item_id" not in d


def test_effect_skill_target_resolves_to_skill_node():
    tasks = _tasks_for_region("Morytania", "hard")
    rec = _reward_record_morytania_hard()
    rec["effects"] = [
        {"effect_kind": "rate_multiplier", "magnitude": 0.075,
         "target_facet": "Slayer XP in the Slayer Tower",
         "target": {"kind": "skill", "name": "Slayer"},
         "condition": "unconditional-once-earned", "tier_source": "morytania:hard"},
    ]
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    skill = [e for e in edges if e.type is EdgeType.EFFECT and e.dst == "skill:slayer"]
    assert len(skill) == 1 and skill[0].src == "item:13114"


def test_effect_rides_on_item_id_override():
    """An effect may ride on a specific item (e.g. the Bonecrusher) instead of the
    regional item, via rides_on_item_id."""
    tasks = _tasks_for_region("Morytania", "hard")
    rec = _reward_record_morytania_hard()
    rec["effects"] = [
        {"effect_kind": "behavior_toggle", "magnitude": None,
         "target_facet": "auto-buries bones", "rides_on_item_id": 4587,
         "target": {"kind": "item", "item_id": 4587},
         "condition": "while-carried", "tier_source": "morytania:hard"},
    ]
    _, edges, _ = build_diaries(tasks, reward_records=[rec])
    eff = [e for e in edges if e.type is EdgeType.EFFECT]
    assert len(eff) == 1
    assert eff[0].src == "item:4587" and eff[0].dst == "item:4587"


def test_no_effects_emits_no_effect_edges():
    tasks = _tasks_for_region("Ardougne", "easy")
    _, edges, _ = build_diaries(tasks, reward_records=[_reward_record_ardougne_easy()])
    assert all(e.type is not EdgeType.EFFECT for e in edges)
