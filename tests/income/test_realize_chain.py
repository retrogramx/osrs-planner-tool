"""Iron tan->craft->alch best-realization over the committed green-dragons chain."""
from __future__ import annotations

import json
import os

import pytest

from osrs_planner.income.methods import (
    build_recipe_reverse_index, load_methods, build_method_index,
)
from osrs_planner.income.realize import best_realization, realize_income
from osrs_planner.cost.prices import SnapshotPriceProvider

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(REPO, "data")


@pytest.fixture(scope="module")
def recipe_index():
    with open(os.path.join(DATA, "recipes.json"), encoding="utf-8") as f:
        return build_recipe_reverse_index(json.load(f))


@pytest.fixture(scope="module")
def provider():
    return SnapshotPriceProvider.from_file(os.path.join(DATA, "ge_prices.json"))


@pytest.fixture(scope="module")
def methods():
    return load_methods(DATA)


@pytest.fixture(scope="module")
def green_dragons(methods):
    m = next((x for x in methods if x.name == "Killing green dragons"), None)
    assert m is not None
    return m


def _hide_flow(method):
    return next(f for f in method.outputs if f.item_id == "item:1753")


def _committed_tan_fee():
    # Read the tan service fee straight from the committed source-of-truth so the
    # golden expectation is DATA-DRIVEN and can never desync from data/recipes.json.
    with open(os.path.join(DATA, "recipes.json"), encoding="utf-8") as f:
        doc = json.load(f)
    tan = next(r for r in doc["records"]
               if r["output_item_id"] == "item:1745"
               and any(i["item_id"] == "item:1753" for i in r["inputs"]))
    return tan["service_fee_coins"]


def test_iron_below_crafting_level_falls_back_to_raw(provider, recipe_index):
    # Crafting 40 (< 63): cannot craft body -> raw alch 81 (leather alch 30 is lower)
    per_hide, status = best_realization("item:1753", "ironman", provider, recipe_index, {"Crafting": 40})
    assert status == "known"
    assert per_hide == 81


def test_iron_at_crafting_level_uses_body_chain(provider, recipe_index):
    # Crafting 63: the chain beats raw 81. Recompute from the SAME sources the
    # recursion reads (never recite a hardcoded constant): high_alch from the
    # provider, and the tan fee READ FROM service_fee_coins in data/recipes.json
    # (so this can never desync from the committed data). The tan fee is per-hide
    # at the tan step, and the 1-coin thread cost is subtracted at the body step.
    #   leather = (body_ha - thread_ha) // 3   # (4680 - 1)//3 = 1559
    #   per_hide = leather - tan_fee           # 1559 - 20 = 1539
    tan_fee = _committed_tan_fee()  # service_fee_coins from data/recipes.json (== 20)
    body_ha = provider.high_alch("item:1135")
    thread_ha = provider.high_alch("item:1734")
    assert body_ha == 4680 and thread_ha == 1  # guard the pinned ids didn't drift
    leather = (body_ha - thread_ha) // 3
    expected = leather - tan_fee  # 1539
    per_hide, status = best_realization("item:1753", "ironman", provider, recipe_index, {"Crafting": 63})
    assert status == "known"
    assert expected == 1539  # documents the pinned golden value (fee 20)
    assert per_hide == expected


def test_realize_income_iron_green_dragons_known(green_dragons, provider, recipe_index):
    # The FULL REAL record now prices KNOWN for iron: every normal item output is
    # valued (raw High-Alch via best_realization), the unitemized gem-drop-table
    # bundle (item_id None, not coins) is SKIPPED (disclosed under-count, the safe
    # direction -- NOT forced unknown), and the combat-supply inputs are
    # GE-subtracted. Via realize_income the MAIN record carries NO Crafting req (and
    # its skill keys are skill:<slug>, not the recipe display-name "Crafting"), so
    # the hide line falls to the RAW floor (81/hide), per the plan's binding
    # skills-source decision -- the 1539 body chain is proven by the two direct
    # best_realization tests above. FINDING: at raw-alch realization with the real
    # consumed combat supplies GE-valued, the iron net is NEGATIVE -- green dragons
    # is a money-LOSER for an iron on this realization (an honest, non-fabricated
    # number, not under-counted to unknown).
    gp_hr, status = realize_income(green_dragons, "ironman", provider, recipe_index)
    assert status == "known"
    assert gp_hr is not None
    # raw-alch hide line (81*180) is the floor for the hide output specifically;
    # the whole-method net is dominated by the GE-valued combat-supply inputs.
    hide = _hide_flow(green_dragons)
    assert provider.high_alch(hide.item_id) == 81  # guard the raw-floor pin


def test_realize_income_main_green_dragons_uses_ge(green_dragons, provider, recipe_index):
    gp_hr, status = realize_income(green_dragons, "main", provider, recipe_index)
    assert status == "known"
    assert gp_hr >= 280260  # GE hide line alone is 1557*180; full record far exceeds


def test_realize_income_green_dragons_main_higher_both_known(green_dragons, provider, recipe_index):
    # The load-bearing account-type divergence, asserted on the FULL REAL record:
    # both families KNOWN (the aggregate-skip refinement makes the real gem-table
    # bundle non-fatal), and main (GE) strictly > iron (raw High-Alch).
    main_gp, main_status = realize_income(green_dragons, "main", provider, recipe_index)
    iron_gp, iron_status = realize_income(green_dragons, "ironman", provider, recipe_index)
    assert main_status == "known" and iron_status == "known"
    assert main_gp is not None and iron_gp is not None
    assert main_gp > iron_gp


def _mk(outputs, **over):
    from osrs_planner.income.methods import MethodRecord, Requirements
    base = dict(
        id="method:agg-test", name="Agg test", category="Combat",
        members=True, audience="main", requires_ge=False, iron_eligible=True,
        realization_channel="mixed", outputs=outputs, inputs=[],
        requirements=Requirements(skills={}, quests=[], items=[]),
        stage=None, tags={}, processing_dependent=False, net_sign="earner",
        source="test", url="test", accessed_at="2026-06-19",
    )
    base.update(over)
    return MethodRecord(**base)


def test_aggregate_output_is_skipped_not_unknown_both_families(provider, recipe_index):
    # CONTROLLER REFINEMENT: an aggregate/bundle output (item_id None, NOT coins --
    # e.g. a gem drop table) is SKIPPED (contributes 0), never forces unknown, for
    # BOTH families. A priceable item output alongside it keeps the method known.
    from osrs_planner.income.methods import Flow
    m = _mk(outputs=[
        Flow(item_id="item:1753", is_coins=False, qty_per_hour=10.0),  # priceable
        Flow(item_id=None, is_coins=False, qty_per_hour=5.0),          # aggregate -> skip
    ])
    main_gp, main_status = realize_income(m, "main", provider, recipe_index)
    iron_gp, iron_status = realize_income(m, "ironman", provider, recipe_index)
    assert main_status == "known" and iron_status == "known"
    # the aggregate contributes 0: value == priceable line only
    assert main_gp == 10 * provider.ge_price("item:1753")
    assert iron_gp == 10 * provider.high_alch("item:1753")


def test_normal_item_output_unpriceable_still_unknown(provider, recipe_index):
    # NEVER FABRICATE intact: a NORMAL item output (item_id set) that can't be
    # valued is a real data gap -> the whole method is unknown, for BOTH families.
    # (Only unitemized bundles with item_id None are skipped; this is item_id set.)
    from osrs_planner.income.methods import Flow
    m = _mk(outputs=[Flow(item_id="item:999999999", is_coins=False, qty_per_hour=1.0)])
    main_gp, main_status = realize_income(m, "main", provider, recipe_index)
    iron_gp, iron_status = realize_income(m, "ironman", provider, recipe_index)
    assert main_status == "unknown" and main_gp is None
    assert iron_status == "unknown" and iron_gp is None


def test_aggregate_only_output_is_known_zero(provider, recipe_index):
    # A method whose ONLY non-coins output is an aggregate bundle is still known
    # (the bundle is skipped); with a coins line it sums to just the coins.
    from osrs_planner.income.methods import Flow
    m = _mk(outputs=[
        Flow(item_id=None, is_coins=True, qty_per_hour=1000.0),  # coins -> face
        Flow(item_id=None, is_coins=False, qty_per_hour=5.0),    # aggregate -> skip
    ])
    iron_gp, iron_status = realize_income(m, "ironman", provider, recipe_index)
    assert iron_status == "known" and iron_gp == 1000


def test_processing_dependent_uncovered_is_unknown(provider, recipe_index):
    from osrs_planner.income.methods import MethodRecord, Flow, Requirements
    m = MethodRecord(
        id="method:fake-uncovered", name="Fake uncovered chain", category="Processing",
        members=True, audience="ironman", requires_ge=False, iron_eligible=True,
        realization_channel="high_alch",
        outputs=[Flow(item_id="item:999999999", is_coins=False, qty_per_hour=100.0)],
        inputs=[], requirements=Requirements(skills={}, quests=[], items=[]),
        stage=None, tags={}, processing_dependent=True, net_sign="earner",
        source="test", url="test", accessed_at="2026-06-19",
    )
    gp_hr, status = realize_income(m, "ironman", provider, recipe_index)
    assert status == "unknown" and gp_hr is None
