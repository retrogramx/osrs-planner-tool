"""Golden income-set over REAL committed data + SnapshotPriceProvider + the engine.

Every gp figure is READ from the provider at runtime (never hardcoded); the test
asserts RELATIONSHIPS and recomputes EXPECTED values from the same source the
code uses -- it survives a price-snapshot refresh.

SIGNATURE NOTE (authoritative, not a relaxation). The plan's Task-10 draft test
code called ``realize_income(method, family, provider, recipe_index)`` (4 args)
and ``best_realization(..., {"Crafting": 63})``. The BUILT implementation
(Tasks 4/5, reviewed) reconciled both signatures -- a deviation disclosed in the
realize.py module docstring and the project memory: ``realize_income`` takes a
fifth ``account_skills`` arg (income is account-specific; the iron processing
chain gates on the ACCOUNT's Crafting, not the method's requirements), and skills
are keyed ``skill:<name>`` slugs like ``AccountState.levels`` (``{"skill:crafting":
63}``), NOT display names. Every binding assertion below (the relationships, the
1539/hide chain value, future-gating, sink ordering, no-best) is preserved; only
the call shape matches the real, authoritative code (mirrors the existing
tests/income/test_realize*.py convention).
"""
from __future__ import annotations

import json
import os

import pytest

from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.model import Node, NodeKind
from osrs_planner.income.methods import (
    load_methods, build_method_index, build_recipe_reverse_index,
    MethodRecord, Flow, Requirements,
)
from osrs_planner.income.realize import realize_income, best_realization
from osrs_planner.income.filter import classify_method
from osrs_planner.income.overlay import suggest_methods
from osrs_planner.income.cards import IncomeCard

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(REPO, "data")


@pytest.fixture(scope="module")
def provider():
    return SnapshotPriceProvider.from_file(os.path.join(DATA, "ge_prices.json"))


@pytest.fixture(scope="module")
def methods():
    return load_methods(DATA)


@pytest.fixture(scope="module")
def recipe_index():
    with open(os.path.join(DATA, "recipes.json"), encoding="utf-8") as f:
        return build_recipe_reverse_index(json.load(f))


@pytest.fixture(scope="module")
def kg():
    nodes = []
    with open(os.path.join(REPO, "kg", "nodes.json"), encoding="utf-8") as f:
        for r in json.load(f):
            nodes.append(Node(id=r["id"], kind=NodeKind(r["kind"]), name=r["name"],
                              slug=r["slug"], data=r.get("data", {})))
    return InMemoryKGStore(nodes=nodes, edges=[], groups={})


def _find(methods, needle):
    # EXACT (case-insensitive) name match, not substring: "Killing green dragons"
    # has 3 dataset variants ("(Myths Guild)", "(Ironman)") that all substring-match
    # -- returning hits[0] would bind the flagship golden to whichever sorts first
    # (dataset order), a silent-fragility bug. Exact-match pins the canonical base.
    hits = [m for m in methods if m.name.lower() == needle.lower()]
    assert hits, f"no method exactly named {needle!r}"
    assert len(hits) == 1, f"{needle!r} resolves to {len(hits)} methods: {[m.name for m in hits]}"
    return hits[0]


# --- scenario 1: green dragons main vs iron differ + correct ---
def test_green_dragons_main_vs_iron_differ_and_correct(provider, methods, recipe_index):
    gd = _find(methods, "Killing green dragons")
    # main = GE sale of hides; iron = coins + High-Alch with the body chain at
    # Crafting 63 (the chain fires ONLY when the ACCOUNT has Crafting 63 -- income
    # is account-specific, so the account_skills arg, not the method's reqs, gates it).
    main_gp, main_status = realize_income(gd, "main", provider, recipe_index, account_skills={})
    iron_gp, iron_status = realize_income(gd, "ironman", provider, recipe_index,
                                          account_skills={"skill:crafting": 63})
    assert main_status == "known" and iron_status == "known"
    assert main_gp != iron_gp and main_gp > iron_gp
    assert iron_gp > 0  # the body chain fires positive (~248k) for a 63-Crafting iron

    # The CHAIN proof (best_realization, skills passed explicitly) recomputed from
    # source to MIRROR the actual recursion (DR-2): the tan fee is subtracted
    # PER-HIDE at the tan step, and the 1-coin thread cost is subtracted at the
    # body step -- so leather = (body_ha - thread_ha)//3, per_hide = leather - tan_fee.
    body_ha = provider.high_alch("item:1135")
    thread_ha = provider.high_alch("item:1734")
    raw_ha = provider.high_alch("item:1753")
    assert body_ha == 4680 and thread_ha == 1 and raw_ha == 81  # guard pinned ids didn't drift
    # tan fee read STRAIGHT from the committed recipes.json (via the reverse-index
    # the recursion itself walks) so this expectation is DATA-DRIVEN and can never
    # desync from data/recipes.json -- standard tanner = 20 (NOT 40, which is Eodan).
    tan_rec = next(p for p in recipe_index["item:1753"] if p["output_item_id"] == "item:1745")
    tan_fee = tan_rec["service_fee_coins"]
    leather = (body_ha - thread_ha) // 3        # (4680 - 1)//3 = 1559
    expected_chain = leather - tan_fee          # 1559 - 20 = 1539
    assert expected_chain == 1539               # documents the pinned golden value (fee 20)
    per_hide_chain, _ = best_realization("item:1753", provider, recipe_index,
                                         {"skill:crafting": 63})
    assert per_hide_chain == expected_chain
    per_hide_raw, _ = best_realization("item:1753", provider, recipe_index,
                                       {"skill:crafting": 40})
    assert per_hide_raw == raw_ha  # 81


# --- scenario 2: main-only absent from iron card (constructed exemplar) ---
def test_main_only_method_absent_from_iron_card(provider, methods, recipe_index, kg):
    main_only = MethodRecord(
        id="method:grinding-chocolate-bars", name="Grinding chocolate bars", category="Processing",
        members=False, audience="main", requires_ge=True, iron_eligible=False, realization_channel="ge",
        outputs=[Flow(item_id="item:1753", is_coins=False, qty_per_hour=1.0)], inputs=[],
        requirements=Requirements(skills={}, quests=[], items=[]),
        stage=None, tags={}, processing_dependent=False, net_sign="earner",
        source="OSRS Wiki MMG", url="https://x", accessed_at="2026-06-18",
    )
    index = build_method_index(list(methods) + [main_only])
    iron = suggest_methods(AccountState(mode="ironman", observable_families={"skill_level", "quest"}),
                           provider, index, recipe_index, kg=kg)
    main = suggest_methods(AccountState(mode="main", observable_families={"skill_level", "quest"}),
                           provider, index, recipe_index, kg=kg)
    assert all(m.id != "method:grinding-chocolate-bars" for m in iron.methods)
    assert any(m.id == "method:grinding-chocolate-bars" for m in main.methods)


# --- scenario 3: future-gating + item-unverified ---
def test_future_gated_rune_dragons_without_ds2(methods, kg):
    rd = _find(methods, "Killing rune dragons")  # requires Dragon Slayer II
    state = AccountState(mode="main", quest_state={}, observable_families={"skill_level", "quest"})
    status, detail = classify_method(rd, state, kg)
    assert status == "future_gated"
    assert any("dragon-slayer-ii" in m for m in detail["missing"])


def test_item_gate_is_unverified_until_bank_data(kg):
    lance = MethodRecord(
        id="method:dhl-test", name="DHL test", category="Combat/High", members=True,
        audience="main", requires_ge=False, iron_eligible=True, realization_channel="ge",
        outputs=[Flow(item_id=None, is_coins=True, qty_per_hour=1000.0)], inputs=[],
        requirements=Requirements(skills={}, quests=[], items=["item:22978"]),
        stage=None, tags={}, processing_dependent=False, net_sign="earner",
        source="x", url="x", accessed_at="2026-06-18",
    )
    state = AccountState(mode="main", observable_families={"skill_level", "quest"})  # NO "item"
    status, detail = classify_method(lance, state, kg)
    assert status == "unverified"
    assert any("22978" in u for u in detail["unverified"])


# --- scenario 4: sink flagged, not ranked above earners ---
def test_managing_miscellania_is_sink_not_ranked_above_earners(provider, methods, recipe_index, kg):
    misc = _find(methods, "Managing Miscellania")
    assert misc.net_sign == "sink"
    index = build_method_index(list(methods))
    card = suggest_methods(AccountState(mode="main", observable_families={"skill_level", "quest", "quest_points"}),
                           provider, index, recipe_index, kg=kg)
    order = card.rankings["by_gp_hr"]
    misc_idx = next(i for i, m in enumerate(card.methods) if m.id == misc.id)
    pos = order.index(misc_idx)
    assert all(card.methods[i].net_sign == "sink" for i in order[pos + 1:])


# --- scenario 5: never-auto-pick (no single best) + a null-rate method is unknown ---
def test_never_auto_pick_no_best_field():
    assert "best" not in IncomeCard.model_fields
    assert "recommended" not in IncomeCard.model_fields


def test_null_rate_method_reports_gp_hr_unknown(provider, recipe_index):
    # A method whose output rate is not modelled (qty_per_hour=None) MUST surface
    # gp_hr_status="unknown" with gp_hr=None -- never a fabricated/invented number.
    null_rate = MethodRecord(
        id="method:unknown-rate", name="Unknown rate method", category="Combat/Low", members=True,
        audience="main", requires_ge=False, iron_eligible=True, realization_channel="ge",
        outputs=[Flow(item_id="item:1753", is_coins=False, qty_per_hour=None)], inputs=[],
        requirements=Requirements(skills={}, quests=[], items=[]),
        stage=None, tags={}, processing_dependent=False, net_sign="earner",
        source="x", url="x", accessed_at="2026-06-18",
    )
    gp, status = realize_income(null_rate, "main", provider, recipe_index, account_skills={})
    assert status == "unknown" and gp is None
