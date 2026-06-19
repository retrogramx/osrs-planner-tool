"""Golden-set acceptance: the engine reproduces the hand-verified verdicts when it
loads the REAL committed KG (kg/*.json) through JsonKGStore. spec §8, spec success-criterion #3.

The KG is the source of truth; if an id below does not resolve, the upstream
builder changed the id — fix the constant here, never the KG.
"""
from __future__ import annotations

import pathlib

import pytest

from osrs_planner.engine.engine import Engine
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.result import Ok, Empty, Problem, TerminalReason
from osrs_planner.engine.state import AccountState

KG_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

DRAGON_SCIMITAR = "item:4587"
BARROWS_GLOVES = "item:7462"
FAIRY_RINGS = "access:fairy-rings"
OBBY_MAUL = "item:6528"
MONKEY_MADNESS_I = "quest:monkey-madness-i"
RECIPE_FOR_DISASTER = "quest:recipe-for-disaster"

OBSERVABLE = {"skill_level", "skill_xp", "combat_level", "quest", "item",
              "achievement_diary", "combat_achievement", "is_unlocked",
              "gear_loadout", "kill_count", "account_type", "clue_scrolls",
              "combat_achievement_points"}


@pytest.fixture(scope="module")
def kg() -> JsonKGStore:
    return JsonKGStore.from_dir(KG_DIR)


@pytest.fixture(scope="module")
def engine(kg) -> Engine:
    return Engine(kg)


def _fresh_main() -> AccountState:
    return AccountState(mode="main", observable_families=set(OBSERVABLE))


def test_real_kg_loads_and_is_acyclic(kg):
    assert kg.nodes
    assert kg.edges
    assert kg.find_cycles() == []


def test_golden_nodes_all_resolve(kg):
    for nid in (DRAGON_SCIMITAR, BARROWS_GLOVES, FAIRY_RINGS, OBBY_MAUL,
                MONKEY_MADNESS_I, RECIPE_FOR_DISASTER):
        assert kg.node(nid) is not None, f"golden node {nid!r} missing from kg/nodes.json"


def test_dragon_scimitar_locked_for_fresh_main(engine):
    res = engine.is_unlocked(_fresh_main(), DRAGON_SCIMITAR)
    assert isinstance(res, Ok)
    assert res.card.status == "locked"
    reasons = {b.reason for b in res.card.blockers}
    assert "skill_level" in reasons, reasons
    assert "quest" in reasons, reasons


def test_dragon_scimitar_unlocked_once_attack_and_mmi(engine):
    state = AccountState(mode="main", levels={"skill:attack": 60},
                         quest_state={MONKEY_MADNESS_I: "completed"},
                         counts={DRAGON_SCIMITAR: 1}, observable_families=set(OBSERVABLE))
    res = engine.is_unlocked(state, DRAGON_SCIMITAR)
    assert isinstance(res, Ok)
    assert res.card.status == "unlocked", [b.name for b in res.card.blockers]


def test_fairy_rings_locked_for_fresh_main(engine):
    res = engine.is_unlocked(_fresh_main(), FAIRY_RINGS)
    assert isinstance(res, Ok)
    assert res.card.status == "locked"


def test_fairy_rings_already_satisfied_when_chain_met(engine, kg):
    chain_quests = {nid for nid in kg.descendants(FAIRY_RINGS) if nid.startswith("quest:")}
    assert chain_quests, "fairy rings access has no quest prereqs in the closure"
    state = AccountState(mode="main",
                         quest_state={q: "completed" for q in chain_quests},
                         observable_families=set(OBSERVABLE))
    res = engine.prereqs_for(state, FAIRY_RINGS)
    assert isinstance(res, Empty), res
    assert res.reason == TerminalReason.ALREADY_SATISFIED


def test_barrows_gloves_locked_for_fresh_main(engine):
    res = engine.is_unlocked(_fresh_main(), BARROWS_GLOVES)
    assert isinstance(res, Ok)
    assert res.card.status == "locked"


def test_barrows_gloves_deep_plan_includes_rfd_and_subquests(engine):
    res = engine.prereqs_for(_fresh_main(), BARROWS_GLOVES)
    assert isinstance(res, Ok), res
    step_ids = {s.node_id for s in res.card.steps}
    assert RECIPE_FOR_DISASTER in step_ids, sorted(step_ids)
    subquests = {sid for sid in step_ids
                 if sid and sid.startswith("quest:recipe-for-disaster-")}
    assert len(subquests) >= 5, sorted(subquests)
    assert len(res.card.steps) >= 10, len(res.card.steps)


def test_obby_maul_locked_below_60_strength(engine):
    state = AccountState(mode="main", levels={"skill:strength": 59},
                         counts={OBBY_MAUL: 1}, observable_families=set(OBSERVABLE))
    res = engine.is_unlocked(state, OBBY_MAUL)
    assert isinstance(res, Ok)
    assert res.card.status == "locked"
    assert any(b.reason == "skill_level" for b in res.card.blockers), \
        [(b.name, b.reason) for b in res.card.blockers]


def test_obby_maul_unlocked_at_60_strength(engine):
    state = AccountState(mode="main", levels={"skill:strength": 60},
                         counts={OBBY_MAUL: 1}, observable_families=set(OBSERVABLE))
    res = engine.is_unlocked(state, OBBY_MAUL)
    assert isinstance(res, Ok)
    assert res.card.status == "unlocked", [b.name for b in res.card.blockers]


def test_main_never_blocked_by_account_type_leaf(engine, kg):
    """A main must never see an 'impossible_for_mode' (account_type) blocker on any
    quest (K4: account_type=='main' is TRUE for a main -> OR satisfied -> req invisible).

    kg.nodes is a dict[str, Node]; iterating it yields the string keys, so we
    collect ids by iterating the keys directly (NOT n.id for n in kg.nodes).
    """
    main = _fresh_main()
    quest_ids = [nid for nid in kg.nodes if nid.startswith("quest:")]
    assert quest_ids
    for qid in quest_ids:
        res = engine.is_unlocked(main, qid)
        assert isinstance(res, (Ok, Empty, Problem)), f"{qid}: {res!r}"
        if isinstance(res, Ok):
            offenders = [b for b in res.card.blockers if b.status == "impossible_for_mode"]
            assert not offenders, f"main hit account_type wall on {qid!r}: " \
                                  f"{[(b.name, b.reason) for b in offenders]}"


DORICS = "quest:dorics-quest"  # data: one skill_req Mining 15, ironman:true, no prereqs


@pytest.mark.parametrize("mode", ["ironman", "hardcore_ironman", "group_ironman",
                                  "hardcore_group_ironman", "ultimate_ironman"])
def test_iron_and_uim_see_ironman_skill_req_on_loaded_kg(engine, kg, mode):
    """A real ironman-wrapped skill_req (OR(account_type=='main', req)) applies to
    EVERY non-main account — 'ironman'-family variants (standard/HCIM/GIM/HCGIM)
    AND UIM — on the LOADED KG, and stays invisible to mains."""
    if kg.node(DORICS) is None:
        pytest.skip("Doric's Quest absent from KG; pick another ironman-wrapped quest")
    non_main = AccountState(mode=mode, observable_families=set(OBSERVABLE))
    res = engine.is_unlocked(non_main, DORICS)
    assert isinstance(res, Ok), res
    assert any(b.reason == "skill_level" and b.name == "Mining"
               for b in res.card.blockers), \
        f"{mode}: expected the iron-only Mining req to apply, got " \
        f"{[(b.name, b.reason) for b in res.card.blockers]}"
    main = AccountState(mode="main", observable_families=set(OBSERVABLE))
    mres = engine.is_unlocked(main, DORICS)
    assert isinstance(mres, Ok), mres
    assert not any(b.reason == "skill_level" and b.name == "Mining"
                   for b in mres.card.blockers), \
        f"main saw the iron-only Mining req: {[(b.name, b.reason) for b in mres.card.blockers]}"


def test_uim_sees_iron_req_applied(engine, kg):
    """UIM is NOT main-family so the OR(account_type=='main', req) wrapper does NOT
    satisfy for UIM — the iron-only req applies."""
    if kg.node(DORICS) is None:
        pytest.skip("Doric's Quest absent from KG; pick another ironman-wrapped quest")
    uim = AccountState(mode="ultimate_ironman", observable_families=set(OBSERVABLE))
    res = engine.is_unlocked(uim, DORICS)
    assert isinstance(res, Ok), res
    assert any(b.reason == "skill_level" and b.name == "Mining"
               for b in res.card.blockers), \
        f"UIM did not see the iron-only Mining req (should apply to UIM): " \
        f"{[(b.name, b.reason) for b in res.card.blockers]}"
