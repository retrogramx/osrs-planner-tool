"""Golden-set: Managing Miscellania flagged as a sink (not ranked above earners);
a constructed main-only (requires_ge) method present on a main card, absent from iron."""
from __future__ import annotations

import json
import os

from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.model import Node, NodeKind
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.income.methods import load_methods, build_method_index, MethodRecord, Flow, Requirements
from osrs_planner.income.overlay import suggest_methods

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(REPO, "data")


def _kg() -> InMemoryKGStore:
    nodes = []
    with open(os.path.join(REPO, "kg", "nodes.json"), encoding="utf-8") as f:
        for r in json.load(f):
            nodes.append(Node(id=r["id"], kind=NodeKind(r["kind"]), name=r["name"],
                              slug=r["slug"], data=r.get("data", {})))
    return InMemoryKGStore(nodes=nodes, edges=[], groups={})


def _provider():
    return SnapshotPriceProvider.from_file(os.path.join(DATA, "ge_prices.json"))


def _main_state():
    return AccountState(mode="main", observable_families={"skill_level", "quest", "quest_points"})


def _iron_state():
    return AccountState(mode="ironman", observable_families={"skill_level", "quest", "quest_points"})


def test_managing_miscellania_is_sink_and_not_ranked_above_earners():
    methods = load_methods(DATA)
    misc = next(m for m in methods if "miscellania" in m.name.lower())
    assert misc.net_sign == "sink", "Managing Miscellania must compute to a sink"

    index = build_method_index(methods)
    card = suggest_methods(_main_state(), _provider(), index, recipe_index={}, kg=_kg())
    misc_idx = next(i for i, m in enumerate(card.methods) if m.id == misc.id)
    assert card.methods[misc_idx].net_sign == "sink"
    order = card.rankings["by_gp_hr"]
    pos = order.index(misc_idx)
    after = order[pos + 1:]
    assert all(card.methods[i].net_sign == "sink" for i in after), "a sink must not rank above an earner"


def _main_only_method() -> MethodRecord:
    # All 377 money_making records are requires_ge=False (main-only live in _excluded),
    # so construct the exemplar (consistent with the golden-set scenario 2).
    return MethodRecord(
        id="method:grinding-chocolate-bars", name="Grinding chocolate bars", category="Processing",
        members=False, audience="main", requires_ge=True, iron_eligible=False, realization_channel="ge",
        outputs=[Flow(item_id="item:1753", is_coins=False, qty_per_hour=1.0)], inputs=[],
        requirements=Requirements(skills={}, quests=[], items=[]),
        stage=None, tags={}, processing_dependent=False, net_sign="earner",
        source="OSRS Wiki MMG", url="https://oldschool.runescape.wiki/w/Money_making_guide/Grinding_chocolate_bars",
        accessed_at="2026-06-18",
    )


def test_main_only_method_present_on_main_absent_from_iron():
    methods = load_methods(DATA)
    index = build_method_index(list(methods) + [_main_only_method()])
    provider, kg = _provider(), _kg()
    main_ids = {m.id for m in suggest_methods(_main_state(), provider, index, recipe_index={}, kg=kg).methods}
    iron_ids = {m.id for m in suggest_methods(_iron_state(), provider, index, recipe_index={}, kg=kg).methods}
    assert "method:grinding-chocolate-bars" in main_ids
    assert "method:grinding-chocolate-bars" not in iron_ids
