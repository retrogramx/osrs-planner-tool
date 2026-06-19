from osrs_planner.income.cards import Method, IncomeCard, rank_by_gp_hr


def _m(id_, gp_hr, status="known", net_sign="earner"):
    return Method(
        id=id_, name=id_, category="Combat/Mid", members=True,
        gp_hr=gp_hr, gp_hr_status=status, realization_channel="mixed",
        requirements_status={"status": "doable_now", "missing": [], "unverified": []},
        tags={}, net_sign=net_sign, outputs_summary="", source="wiki", url="http://x",
    )


def test_rank_descending_by_gp_hr():
    methods = [_m("a", 100), _m("b", 500), _m("c", 250)]
    assert rank_by_gp_hr(methods) == [1, 2, 0]  # 500, 250, 100


def test_unknown_gp_hr_sorts_last():
    methods = [_m("a", 100), _m("u", None, status="unknown"), _m("b", 500)]
    order = rank_by_gp_hr(methods)
    assert order[-1] == 1
    assert order[:2] == [2, 0]


def test_sinks_sort_last_even_if_high_gp():
    methods = [_m("earn", 100), _m("sink", 9_000_000, net_sign="sink")]
    order = rank_by_gp_hr(methods)
    assert order[-1] == 1 and order[0] == 0


def test_incomecard_has_no_best_field():
    card = IncomeCard(account_family="main", methods=[_m("a", 100)], rankings={"by_gp_hr": [0]}, notes=[])
    assert not hasattr(card, "best") and not hasattr(card, "recommended")
    assert "best" not in IncomeCard.model_fields
    assert "recommended" not in IncomeCard.model_fields
    assert "by_gp_hr" in card.rankings
