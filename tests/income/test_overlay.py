import json
import os

import pytest

from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.engine.state import AccountState
from osrs_planner.income.methods import load_methods, build_method_index, build_recipe_reverse_index
from osrs_planner.income.overlay import suggest_methods, _outputs_summary
from osrs_planner.income.cards import IncomeCard
from osrs_planner.income.methods import Flow, MethodRecord

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(REPO, "data")


@pytest.fixture(scope="module")
def provider():
    return SnapshotPriceProvider.from_file(os.path.join(DATA, "ge_prices.json"))


@pytest.fixture(scope="module")
def index():
    return build_method_index(load_methods(DATA))


@pytest.fixture(scope="module")
def recipe_index():
    with open(os.path.join(DATA, "recipes.json"), encoding="utf-8") as f:
        return build_recipe_reverse_index(json.load(f))


def _gd(card):
    return next((m for m in card.methods if m.name == "Killing green dragons"), None)


def _stub_method(outputs):
    return MethodRecord(
        id="method:x", name="X", category="c", members=True, audience="main",
        requires_ge=False, iron_eligible=True, realization_channel="coins",
        outputs=outputs, inputs=[], net_sign="earner", source="t", url="u",
        accessed_at="2026-06-19",
    )


def test_outputs_summary_unknown_rate_renders_question_mark_not_zero():
    """never-fabricate in the display string: a None rate is 'x?/hr', not 'x0/hr'
    (0 would falsely read as 'yields nothing')."""
    summary = _outputs_summary(_stub_method([Flow(item_id="item:1", qty_per_hour=None)]))
    assert "x?/hr" in summary
    assert "x0/hr" not in summary


def test_outputs_summary_known_rate_renders_number():
    summary = _outputs_summary(_stub_method([Flow(item_id="item:1", qty_per_hour=180)]))
    assert "x180/hr" in summary


def test_main_card_is_ranked_incomecard(provider, index, recipe_index):
    card = suggest_methods(AccountState(mode="main"), provider, index, recipe_index)
    assert isinstance(card, IncomeCard)
    assert card.account_family == "main"
    assert len(card.methods) > 0
    order = card.rankings["by_gp_hr"]
    assert sorted(order) == list(range(len(card.methods)))
    known = [card.methods[i].gp_hr for i in order
             if card.methods[i].gp_hr is not None and card.methods[i].net_sign == "earner"]
    assert known == sorted(known, reverse=True)


def test_green_dragons_present_both_families_different_gp(provider, index, recipe_index):
    main = suggest_methods(AccountState(mode="main"), provider, index, recipe_index)
    iron = suggest_methods(
        AccountState(mode="ironman", levels={"skill:crafting": 63}),
        provider, index, recipe_index,
    )
    gm, gi = _gd(main), _gd(iron)
    assert gm is not None and gi is not None
    assert gm.gp_hr_status == "known" and gi.gp_hr_status == "known"
    assert gm.gp_hr != gi.gp_hr  # main GE vs iron alch/chain


def test_no_best_or_recommended_field(provider, index, recipe_index):
    card = suggest_methods(AccountState(mode="main"), provider, index, recipe_index)
    dumped = card.model_dump()
    assert "best" not in dumped and "recommended" not in dumped
    assert set(dumped["rankings"].keys()) == {"by_gp_hr"}


def test_current_gold_accepted_and_ignored(provider, index, recipe_index):
    state = AccountState(mode="main")
    a = suggest_methods(state, provider, index, recipe_index)
    b = suggest_methods(state, provider, index, recipe_index, current_gold=5_000_000)
    assert a.model_dump() == b.model_dump()
