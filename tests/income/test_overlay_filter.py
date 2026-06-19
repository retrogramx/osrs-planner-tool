import json
import os

from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.model import Node, NodeKind
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.income.methods import load_methods, build_method_index, build_recipe_reverse_index
from osrs_planner.income.overlay import suggest_methods

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(REPO, "data")


def _kg() -> InMemoryKGStore:
    nodes = []
    with open(os.path.join(REPO, "kg", "nodes.json"), encoding="utf-8") as f:
        for r in json.load(f):  # kg/nodes.json is a bare list
            nodes.append(Node(id=r["id"], kind=NodeKind(r["kind"]), name=r["name"],
                              slug=r["slug"], data=r.get("data", {})))
    return InMemoryKGStore(nodes=nodes, edges=[], groups={})


def _bits():
    provider = SnapshotPriceProvider.from_file(os.path.join(DATA, "ge_prices.json"))
    index = build_method_index(load_methods(DATA))
    with open(os.path.join(DATA, "recipes.json"), encoding="utf-8") as f:
        recipe_index = build_recipe_reverse_index(json.load(f))
    return provider, index, recipe_index, _kg()


def _state():
    return AccountState(mode="main", levels={}, qp=0,
                        observable_families={"skill_level", "quest", "quest_points"})


def test_card_methods_carry_requirements_status():
    provider, index, recipe_index, kg = _bits()
    card = suggest_methods(_state(), provider, index, recipe_index, kg=kg)
    statuses = {m.requirements_status.get("status") for m in card.methods}
    assert statuses <= {"doable_now", "future_gated", "unverified"}
    assert "future_gated" in statuses  # high-level methods exist on real data


def test_doable_now_ranked_above_future_gated():
    provider, index, recipe_index, kg = _bits()
    card = suggest_methods(_state(), provider, index, recipe_index, kg=kg)
    seen_future = False
    for idx in card.rankings["by_gp_hr"]:
        st = card.methods[idx].requirements_status.get("status")
        # skip unknown-gp and sinks (tiers 2/3); within known earners doable precedes future
        m = card.methods[idx]
        if m.gp_hr is None or m.gp_hr_status != "known" or m.net_sign == "sink":
            continue
        if st == "future_gated":
            seen_future = True
        elif st == "doable_now":
            assert not seen_future, "a doable_now method ranked below a future_gated one"
