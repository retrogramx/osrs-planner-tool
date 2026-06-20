#!/usr/bin/env python3
"""Human-eyeball income demo: green dragons realized for a main vs an ironman,
plus a ranked IncomeCard for an ironman crafter. Prints to stdout only (no
browser auto-open -- the user refreshes manually). Run:

    venv/bin/python scripts/income_demo.py

SIGNATURE NOTE: realize_income takes the account's skill levels (keyed
skill:<name>, like AccountState.levels) as a fifth arg -- the iron processing
chain (tan->craft->alch) gates on the ACCOUNT's Crafting, not the kill method's
requirements. So the ironman line passes a 63-Crafting account to fire the body
chain; the main line ignores skills (GE sale). (Built-code signature, disclosed
in realize.py.)
"""
from __future__ import annotations

import json
import os

from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.kg.model import Node, NodeKind
from osrs_planner.income.methods import load_methods, build_method_index, build_recipe_reverse_index
from osrs_planner.income.realize import realize_income
from osrs_planner.income.overlay import suggest_methods

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")


def _kg() -> InMemoryKGStore:
    nodes = []
    with open(os.path.join(REPO, "kg", "nodes.json"), encoding="utf-8") as f:
        for r in json.load(f):
            nodes.append(Node(id=r["id"], kind=NodeKind(r["kind"]), name=r["name"],
                              slug=r["slug"], data=r.get("data", {})))
    return InMemoryKGStore(nodes=nodes, edges=[], groups={})


def main() -> None:
    provider = SnapshotPriceProvider.from_file(os.path.join(DATA, "ge_prices.json"))
    methods = load_methods(DATA)
    with open(os.path.join(DATA, "recipes.json"), encoding="utf-8") as f:
        recipe_index = build_recipe_reverse_index(json.load(f))
    index = build_method_index(list(methods))
    kg = _kg()

    gd = next(m for m in methods if m.name == "Killing green dragons")
    # account_skills per family: a main sells hides on the GE (skills ignored); a
    # 63-Crafting ironman realizes via the tan->craft->alch body chain.
    family_skills = {"main": {}, "ironman": {"skill:crafting": 63}}
    print("=== Green dragons realization (account-type aware) ===")
    for fam in ("main", "ironman"):
        gp, status = realize_income(gd, fam, provider, recipe_index, family_skills[fam])
        print(f"  {fam:8s}: gp/hr={gp!s:>12}  status={status}")
    print("  (main = GE sale of hides; ironman = coins + High-Alch; the body chain")
    print("   tan(20gp/hide standard fee)->craft->alch + Crafting 63 is proven in best_realization)\n")

    print("=== Ironman crafter IncomeCard (top 10 by gp/hr) ===")
    state = AccountState(mode="ironman", levels={"skill:crafting": 99},
                         observable_families={"skill_level", "quest"})
    card = suggest_methods(state, provider, index, recipe_index, kg=kg)
    for rank, idx in enumerate(card.rankings["by_gp_hr"][:10], 1):
        m = card.methods[idx]
        st = m.requirements_status.get("status")
        print(f"  {rank:>2}. {m.name[:40]:40s} gp/hr={m.gp_hr!s:>10} [{m.gp_hr_status}] {m.net_sign} {st}")
    print(f"\n  total methods in card: {len(card.methods)}; account_family={card.account_family}")
    print("  NOTE: no single 'best' -- the player/advisor chooses (never-auto-pick).")


if __name__ == "__main__":
    main()
