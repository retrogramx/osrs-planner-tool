from osrs_planner.engine.kleene import Tri
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.model import (
    AtomType, Op, NodeKind, Node, ConditionAtom, ConditionGroup, Edge, EdgeType,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.conditions import evaluate, atom_satisfied


def _store(nodes=None, edges=None, groups=None):
    # Task 5's InMemoryKGStore expects groups as a dict[int, ConditionGroup];
    # callers pass a list[ConditionGroup], so index it by id here.
    return InMemoryKGStore(
        nodes=list(nodes or []),
        edges=list(edges or []),
        groups={g.id: g for g in (groups or [])},
    )


def test_skill_level_atom_true_false_and_absent_is_false():
    kg = _store(nodes=[Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack")])
    atom = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70)

    met = AccountState(mode="normal", levels={"skill:attack": 70})
    under = AccountState(mode="normal", levels={"skill:attack": 69})
    absent = AccountState(mode="normal")  # skill levels are observable -> absent means level 1 -> FALSE

    assert atom_satisfied(atom, met, kg) is Tri.TRUE
    assert atom_satisfied(atom, under, kg) is Tri.FALSE
    assert atom_satisfied(atom, absent, kg) is Tri.FALSE


def test_skill_xp_atom():
    kg = _store(nodes=[Node(id="skill:slayer", kind=NodeKind.SKILL, name="Slayer", slug="slayer")])
    atom = ConditionAtom(atom_type=AtomType.SKILL_XP, ref_node="skill:slayer", threshold=100_000)
    assert atom_satisfied(atom, AccountState(mode="normal", xp={"skill:slayer": 100_000}), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal", xp={"skill:slayer": 99_999}), kg) is Tri.FALSE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE  # absent xp = 0


def test_combat_level_atom_reads_derived_scalar():
    kg = _store()
    atom = ConditionAtom(atom_type=AtomType.COMBAT_LEVEL, threshold=100)
    assert atom_satisfied(atom, AccountState(mode="normal", combat_level=100), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal", combat_level=99), kg) is Tri.FALSE
    # default combat_level=3 always exists -> never UNKNOWN
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_quest_points_and_ca_points_atoms():
    kg = _store()
    qp = ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)
    cap = ConditionAtom(atom_type=AtomType.COMBAT_ACHIEVEMENT_POINTS, threshold=500)
    assert atom_satisfied(qp, AccountState(mode="normal", qp=32), kg) is Tri.TRUE
    assert atom_satisfied(qp, AccountState(mode="normal", qp=31), kg) is Tri.FALSE
    assert atom_satisfied(cap, AccountState(mode="normal", ca_points=500), kg) is Tri.TRUE
    assert atom_satisfied(cap, AccountState(mode="normal", ca_points=499), kg) is Tri.FALSE


def test_item_atom_qty_observable_absent_is_false():
    kg = _store(nodes=[Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top")])
    atom = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839", qty=2)
    assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8839": 2}), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8839": 1}), kg) is Tri.FALSE
    # items are observable (bank feed) -> absent = 0 owned = FALSE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_item_atom_qty_defaults_to_one():
    kg = _store(nodes=[Node(id="item:8842", kind=NodeKind.ITEM, name="Void gloves", slug="void-gloves")])
    atom = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8842")  # qty None -> 1
    assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8842": 1}), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_account_type_atom_matches_mode():
    kg = _store()
    atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "ironman"})
    assert atom_satisfied(atom, AccountState(mode="ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


def test_is_unlocked_atom_done_membership_and_unobservable_absent_is_unknown():
    kg = _store(nodes=[Node(id="access:fairy-rings", kind=NodeKind.ACCESS,
                            name="Fairy rings", slug="fairy-rings")])
    atom = ConditionAtom(atom_type=AtomType.IS_UNLOCKED, ref_node="access:fairy-rings")

    has = AccountState(mode="normal", done={"access:fairy-rings"})
    # access is engine-derived/unobservable; absent + not asserted -> UNKNOWN (not a false locked)
    absent = AccountState(mode="normal")
    # but if the family IS observed, absence is a real FALSE
    observed = AccountState(mode="normal", observable_families={"is_unlocked"})

    assert atom_satisfied(atom, has, kg) is Tri.TRUE
    assert atom_satisfied(atom, absent, kg) is Tri.UNKNOWN
    assert atom_satisfied(atom, observed, kg) is Tri.FALSE


def test_combat_achievement_atom_binary_in_done():
    kg = _store(nodes=[Node(id="ca:scurrius:smashing-the-rat", kind=NodeKind.COMBAT_ACHIEVEMENT,
                            name="Smashing the Rat", slug="scurrius:smashing-the-rat")])
    atom = ConditionAtom(atom_type=AtomType.COMBAT_ACHIEVEMENT, ref_node="ca:scurrius:smashing-the-rat")
    done = AccountState(mode="normal", done={"ca:scurrius:smashing-the-rat"})
    absent = AccountState(mode="normal")  # per-task CAs unobservable on Hiscores -> UNKNOWN
    observed = AccountState(mode="normal", observable_families={"combat_achievement"})
    assert atom_satisfied(atom, done, kg) is Tri.TRUE
    assert atom_satisfied(atom, absent, kg) is Tri.UNKNOWN
    assert atom_satisfied(atom, observed, kg) is Tri.FALSE


def test_quest_atom_ordered_state_in_progress_req_met_by_completed():
    kg = _store(nodes=[Node(id="quest:dragon-slayer-i", kind=NodeKind.QUEST,
                            name="Dragon Slayer I", slug="dragon-slayer-i")])
    needs_completed = ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:dragon-slayer-i",
                                    data={"state": "completed"})
    needs_in_progress = ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:dragon-slayer-i",
                                      data={"state": "in_progress"})

    completed = AccountState(mode="normal", quest_state={"quest:dragon-slayer-i": "completed"})
    in_progress = AccountState(mode="normal", quest_state={"quest:dragon-slayer-i": "in_progress"})

    # completed satisfies a 'completed' requirement
    assert atom_satisfied(needs_completed, completed, kg) is Tri.TRUE
    # in_progress does NOT satisfy a 'completed' requirement (ordered <)
    assert atom_satisfied(needs_completed, in_progress, kg) is Tri.FALSE
    # an 'in_progress' requirement is met by BOTH in_progress and completed (ordered >=)
    assert atom_satisfied(needs_in_progress, in_progress, kg) is Tri.TRUE
    assert atom_satisfied(needs_in_progress, completed, kg) is Tri.TRUE


def test_quest_atom_unobservable_absent_is_unknown():
    kg = _store(nodes=[Node(id="quest:cooks-assistant", kind=NodeKind.QUEST,
                            name="Cook's Assistant", slug="cooks-assistant")])
    atom = ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:cooks-assistant",
                         data={"state": "completed"})
    # quests are NOT on the Hiscores -> absent + unobservable -> UNKNOWN
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.UNKNOWN
    # when observed (plugin), absence resolves to not_started -> real FALSE
    observed = AccountState(mode="normal", observable_families={"quest"})
    assert atom_satisfied(atom, observed, kg) is Tri.FALSE


def test_achievement_diary_atom_ordered_and_unobservable():
    kg = _store(nodes=[Node(id="diary:varrock:hard", kind=NodeKind.DIARY,
                            name="Varrock Hard Diary", slug="varrock:hard")])
    atom = ConditionAtom(atom_type=AtomType.ACHIEVEMENT_DIARY, ref_node="diary:varrock:hard",
                         data={"state": "completed"})
    done = AccountState(mode="normal", diary_state={"diary:varrock:hard": "completed"})
    partial = AccountState(mode="normal", diary_state={"diary:varrock:hard": "in_progress"})
    assert atom_satisfied(atom, done, kg) is Tri.TRUE
    assert atom_satisfied(atom, partial, kg) is Tri.FALSE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.UNKNOWN  # not on Hiscores


def test_kill_count_atom_absence_is_unknown_not_zero():
    kg = _store(nodes=[Node(id="npc:7221", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius")])
    atom = ConditionAtom(atom_type=AtomType.KILL_COUNT, ref_node="npc:7221", threshold=100)
    assert atom_satisfied(atom, AccountState(mode="normal", kc={"npc:7221": 100}), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal", kc={"npc:7221": 99}), kg) is Tri.FALSE
    # cardinal rule: absent KC may be below the Hiscores cutoff, NOT zero -> UNKNOWN
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.UNKNOWN
    # when observed (plugin), absence is a real 0 -> FALSE
    observed = AccountState(mode="normal", observable_families={"kill_count"})
    assert atom_satisfied(atom, observed, kg) is Tri.FALSE


def test_evaluate_and_or_not_fold_via_kleene():
    # group 1 = OR( group 2 = AND(att>=70, str>=70), NOT(group 3 = AND(qp>=99)) )
    nodes = [
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
        Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength"),
    ]
    groups = [
        ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 4]),
        ConditionGroup(id=2, op=Op.AND, parent=1, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:strength", threshold=70),
        ]),
        ConditionGroup(id=3, op=Op.AND, parent=4, children=[
            ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=99),
        ]),
        ConditionGroup(id=4, op=Op.NOT, parent=1, children=[3]),
    ]
    kg = _store(nodes=nodes, groups=groups)

    # AND branch TRUE -> whole OR TRUE
    both = AccountState(mode="normal", levels={"skill:attack": 70, "skill:strength": 70})
    assert evaluate(1, both, kg) is Tri.TRUE

    # AND branch FALSE (str 60), but NOT(qp>=99) = NOT(FALSE) = TRUE -> OR TRUE
    low_str = AccountState(mode="normal", levels={"skill:attack": 70, "skill:strength": 60}, qp=0)
    assert evaluate(1, low_str, kg) is Tri.TRUE

    # AND branch FALSE AND NOT(qp>=99)=NOT(TRUE)=FALSE -> OR FALSE
    low_str_high_qp = AccountState(mode="normal",
                                   levels={"skill:attack": 70, "skill:strength": 60}, qp=99)
    assert evaluate(1, low_str_high_qp, kg) is Tri.FALSE


def test_gear_loadout_atom_dynamic_partial_false_full_true():
    # Void composition (kg-schema worked example): AND( OR(helm a/b/c), top, robe, gloves )
    nodes = [
        Node(id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Full Void", slug="void"),
        Node(id="item:11663", kind=NodeKind.ITEM, name="Void mage helm", slug="void-mage-helm"),
        Node(id="item:11664", kind=NodeKind.ITEM, name="Void ranger helm", slug="void-ranger-helm"),
        Node(id="item:11665", kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm"),
        Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top"),
        Node(id="item:8840", kind=NodeKind.ITEM, name="Void robe", slug="void-robe"),
        Node(id="item:8842", kind=NodeKind.ITEM, name="Void gloves", slug="void-gloves"),
    ]
    # composition cond_group 10 lives on gear_loadout:void's dst=NULL requires edge
    groups = [
        ConditionGroup(id=10, op=Op.AND, parent=None, children=[
            11,  # the helm-OR subgroup
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839"),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8840"),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8842"),
        ]),
        ConditionGroup(id=11, op=Op.OR, parent=10, children=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11663"),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11664"),
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11665"),
        ]),
    ]
    edges = [
        Edge(id=9100, type=EdgeType.REQUIRES, src="gear_loadout:void", dst=None, cond_group=10),
    ]
    kg = _store(nodes=nodes, edges=edges, groups=groups)
    atom = ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node="gear_loadout:void")

    # full set (melee helm + top + robe + gloves) -> TRUE
    full = AccountState(mode="normal", counts={
        "item:11665": 1, "item:8839": 1, "item:8840": 1, "item:8842": 1,
    })
    assert atom_satisfied(atom, full, kg) is Tri.TRUE

    # 3/4 pieces (missing gloves) -> FALSE (the false-single-piece-OR guard)
    three = AccountState(mode="normal", counts={
        "item:11665": 1, "item:8839": 1, "item:8840": 1,
    })
    assert atom_satisfied(atom, three, kg) is Tri.FALSE

    # only one piece (a helm) -> FALSE (would be a false TRUE without the AND-of-slots tree)
    one = AccountState(mode="normal", counts={"item:11665": 1})
    assert atom_satisfied(atom, one, kg) is Tri.FALSE


def test_clue_scrolls_cardinality_atom():
    nodes = [
        Node(id="clue:easy", kind=NodeKind.ACTIVITY, name="Easy clue", slug="easy-clue"),
        Node(id="clue:medium", kind=NodeKind.ACTIVITY, name="Medium clue", slug="medium-clue"),
        Node(id="clue:hard", kind=NodeKind.ACTIVITY, name="Hard clue", slug="hard-clue"),
    ]
    kg = _store(nodes=nodes)
    # need >= 2 of the 3 clue tiers completed at least once
    atom = ConditionAtom(atom_type=AtomType.CLUE_SCROLLS, threshold=2,
                         data={"set_ref": ["clue:easy", "clue:medium", "clue:hard"]})

    # 2 satisfied (easy + hard) -> TRUE  (observed family so absent members are real 0)
    obs2 = AccountState(mode="normal",
                        clue_counts={"clue:easy": 4, "clue:hard": 1},
                        observable_families={"clue_scrolls"})
    assert atom_satisfied(atom, obs2, kg) is Tri.TRUE

    # only 1 satisfied, family observed -> the other two are real FALSE -> 1 < 2 -> FALSE
    obs1 = AccountState(mode="normal", clue_counts={"clue:easy": 4},
                        observable_families={"clue_scrolls"})
    assert atom_satisfied(atom, obs1, kg) is Tri.FALSE

    # 1 known-satisfied + 2 UNKNOWN (unobservable): could still reach 2 -> verdict UNKNOWN
    unk = AccountState(mode="normal", clue_counts={"clue:easy": 4})
    assert atom_satisfied(atom, unk, kg) is Tri.UNKNOWN

    # 2 already known-satisfied + 1 UNKNOWN: TRUE regardless of the unknown (k_or short-circuit)
    enough = AccountState(mode="normal", clue_counts={"clue:easy": 4, "clue:medium": 1})
    assert atom_satisfied(atom, enough, kg) is Tri.TRUE


def test_evaluate_unknown_surfaces_only_when_it_flips_the_verdict():
    # G1 = OR( quest:x completed [UNKNOWN when absent], skill:attack >= 70 )
    nodes = [
        Node(id="quest:x", kind=NodeKind.QUEST, name="Quest X", slug="quest-x"),
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
    ]
    groups = [
        ConditionGroup(id=1, op=Op.OR, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:x", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
        ]),
    ]
    kg = _store(nodes=nodes, groups=groups)

    # quest unknown, but attack>=70 TRUE -> OR is TRUE (k_or short-circuits the UNKNOWN)
    high_att = AccountState(mode="normal", levels={"skill:attack": 70})
    assert evaluate(1, high_att, kg) is Tri.TRUE

    # quest unknown AND attack 60 FALSE -> OR is UNKNOWN (the unknown now flips it)
    low_att = AccountState(mode="normal", levels={"skill:attack": 60})
    assert evaluate(1, low_att, kg) is Tri.UNKNOWN


def test_evaluate_and_with_one_false_is_false_despite_unknown():
    # G1 = AND( skill:attack >= 70 [FALSE], quest:x [UNKNOWN] ) -> FALSE
    nodes = [
        Node(id="quest:x", kind=NodeKind.QUEST, name="Quest X", slug="quest-x"),
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
    ]
    groups = [
        ConditionGroup(id=1, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:x", data={"state": "completed"}),
        ]),
    ]
    kg = _store(nodes=nodes, groups=groups)
    st = AccountState(mode="normal", levels={"skill:attack": 60})  # quest absent -> UNKNOWN
    assert evaluate(1, st, kg) is Tri.FALSE  # any FALSE in AND wins over UNKNOWN
