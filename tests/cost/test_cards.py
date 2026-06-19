from osrs_planner.cost.cards import (
    CostCard,
    Route,
    rank_by_gold,
    roll_up_gold_status,
)


def _route(channel, gold, status="known"):
    return Route(
        channel=channel, currency="currency:coins", gold_cost=gold,
        gold_status=status, account_allowed=True, source=channel,
    )


def test_costcard_constructs_and_dumps():
    card = CostCard(
        item_id="item:4587", name="Dragon scimitar", account_family="main",
        routes=[_route("ge", 60748)],
        rankings={"by_gold": [0], "by_time": []},
        notes=[], gold_status="known",
    )
    assert card.item_id == "item:4587"
    assert card.account_family == "main"
    assert card.rankings["by_time"] == []
    dumped = card.model_dump()
    assert dumped["routes"][0]["gold_cost"] == 60748
    assert "best" not in dumped


def test_rank_by_gold_ascending_unavailable_last():
    routes = [
        _route("shop", 100000),
        _route("ge", 60748),
        _route("craft", None, status="unavailable"),
        _route("spawn", 0),
    ]
    # spawn(0) < ge(60748) < shop(100000) < craft(unavailable)
    assert rank_by_gold(routes) == [3, 1, 0, 2]


def test_roll_up_gold_status_modes():
    assert roll_up_gold_status([_route("ge", 1)]) == "known"
    assert roll_up_gold_status([_route("ge", None, "unavailable")]) == "unavailable"
    assert roll_up_gold_status(
        [_route("ge", 1), _route("craft", None, "unavailable")]
    ) == "partial"
    assert roll_up_gold_status([]) == "unavailable"
