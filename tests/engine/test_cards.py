from osrs_planner.engine.cards import (
    NodeRef,
    ReferencedAtom,
    Step,
    UnlockCard,
    PlanCard,
)


def test_node_ref_constructs_and_dumps():
    ref = NodeRef(id="quest:fairytale_2", kind="QUEST", name="Fairytale II")
    assert ref.id == "quest:fairytale_2"
    assert ref.kind == "QUEST"
    assert ref.name == "Fairytale II"
    assert ref.model_dump() == {
        "id": "quest:fairytale_2",
        "kind": "QUEST",
        "name": "Fairytale II",
    }


def test_referenced_atom_defaults_to_minimal_scalar():
    atom = ReferencedAtom(atom_type="SKILL_LEVEL", ref_node="skill:attack", threshold=70)
    assert atom.atom_type == "SKILL_LEVEL"
    assert atom.ref_node == "skill:attack"
    assert atom.threshold == 70
    assert atom.qty is None
    assert atom.state is None
    assert atom.is_partial is False
    assert atom.model_dump() == {
        "atom_type": "SKILL_LEVEL",
        "ref_node": "skill:attack",
        "threshold": 70,
        "qty": None,
        "state": None,
        "is_partial": False,
    }


def test_referenced_atom_partial_quest_state():
    atom = ReferencedAtom(
        atom_type="QUEST",
        ref_node="quest:fairytale_2",
        state="in_progress",
        is_partial=True,
    )
    assert atom.state == "in_progress"
    assert atom.is_partial is True
    dumped = atom.model_dump()
    assert dumped["state"] == "in_progress"
    assert dumped["is_partial"] is True
    assert dumped["threshold"] is None


def test_step_constructs_and_dumps():
    step = Step(
        node_id="skill:attack",
        name="70 Attack",
        reason="SKILL_LEVEL",
        status="satisfiable",
    )
    assert step.node_id == "skill:attack"
    assert step.name == "70 Attack"
    assert step.reason == "SKILL_LEVEL"
    assert step.status == "satisfiable"
    assert step.model_dump() == {
        "node_id": "skill:attack",
        "name": "70 Attack",
        "reason": "SKILL_LEVEL",
        "status": "satisfiable",
    }


def test_step_allows_null_node_id():
    step = Step(node_id=None, name="Combat level 100", reason="COMBAT_LEVEL", status="cant_verify")
    assert step.node_id is None
    assert step.model_dump()["node_id"] is None


def test_unlock_card_defaults_empty_blockers():
    card = UnlockCard(node_id="access:fairy_rings", status="unlocked")
    assert card.node_id == "access:fairy_rings"
    assert card.status == "unlocked"
    assert card.blockers == []
    assert card.model_dump() == {
        "node_id": "access:fairy_rings",
        "status": "unlocked",
        "blockers": [],
    }


def test_unlock_card_with_blockers_serializes_nested_steps():
    blocker = Step(
        node_id="quest:fairytale_2",
        name="Fairytale II",
        reason="QUEST",
        status="satisfiable",
    )
    card = UnlockCard(node_id="access:fairy_rings", status="locked", blockers=[blocker])
    dumped = card.model_dump()
    assert dumped["status"] == "locked"
    assert dumped["blockers"] == [
        {
            "node_id": "quest:fairytale_2",
            "name": "Fairytale II",
            "reason": "QUEST",
            "status": "satisfiable",
        }
    ]


def test_plan_card_defaults_empty_referenced_atoms():
    card = PlanCard(goal_id="access:fairy_rings", steps=[])
    assert card.goal_id == "access:fairy_rings"
    assert card.steps == []
    assert card.referenced_atoms == []
    assert card.model_dump() == {
        "goal_id": "access:fairy_rings",
        "steps": [],
        "referenced_atoms": [],
    }


def test_plan_card_full_round_trips():
    step = Step(
        node_id="skill:attack",
        name="70 Attack",
        reason="SKILL_LEVEL",
        status="satisfiable",
    )
    atom = ReferencedAtom(atom_type="SKILL_LEVEL", ref_node="skill:attack", threshold=70)
    card = PlanCard(
        goal_id="access:fairy_rings",
        steps=[step],
        referenced_atoms=[atom],
    )
    assert card.model_dump() == {
        "goal_id": "access:fairy_rings",
        "steps": [
            {
                "node_id": "skill:attack",
                "name": "70 Attack",
                "reason": "SKILL_LEVEL",
                "status": "satisfiable",
            }
        ],
        "referenced_atoms": [
            {
                "atom_type": "SKILL_LEVEL",
                "ref_node": "skill:attack",
                "threshold": 70,
                "qty": None,
                "state": None,
                "is_partial": False,
            }
        ],
    }
