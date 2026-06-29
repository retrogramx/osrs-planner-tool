#!/usr/bin/env python3
"""Narrative showcase: the connective vertical (slices 6-7) answering real OSRS
acquisition questions over the REAL committed knowledge graph (kg/*.json), with
the actual account-aware three-valued evaluator (src/osrs_planner/engine).

Nothing is mocked: every fact is traversed from the graph and every "can I buy
it" verdict comes from engine.conditions.evaluate against an AccountState.

Run from repo root:  ./venv/bin/python scripts/demo_connective.py
"""
from __future__ import annotations

import pathlib
import sys

from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType
from osrs_planner.engine.conditions import evaluate
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kleene import Tri

# scripts/ -> repo root -> kg/
KG_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "kg")
kg = JsonKGStore.from_dir(KG_DIR)

_COLOR = sys.stdout.isatty()
def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _COLOR else s

def name(nid: str) -> str:
    n = kg.node(nid)
    return n.name if n else nid

def es(edge_type: EdgeType) -> list:
    return [e for e in kg.edges if e.type is edge_type]

VERDICT = {Tri.TRUE: _c("92", "✓ CAN BUY"), Tri.FALSE: _c("91", "✗ BLOCKED"),
           Tri.UNKNOWN: _c("93", "? UNKNOWN")}

def hr(title: str) -> None:
    print("\n" + "═" * 78 + f"\n  {title}\n" + "═" * 78)

_TIER = {"easy": 1, "medium": 2, "hard": 3, "elite": 4}
def offer_key(e):  # quest gate first, then diary tiers easy->elite
    a = kg.children_of(e.cond_group)[0]
    if a.atom_type.value == "quest":
        return (0, 0)
    return (1, _TIER.get(a.ref_node.split(":")[-1], 9))


def q1_acquisition_and_evaluator() -> None:
    hr('Q1.  "Where can I buy a Battlestaff — and can MY account?"  (spine + evaluator)')
    BSTAFF = "item:1391"
    print(f"\n  Target: {name(BSTAFF)}  ({BSTAFF})\n")
    sellers = [e for e in es(EdgeType.SELLS) if e.dst == BSTAFF]
    for shid in sorted({e.src for e in sellers}):
        op = next((e.src for e in es(EdgeType.OPERATES) if e.dst == shid), None)
        chain, cur = [], shid
        while True:
            nxt = next((e.dst for e in es(EdgeType.LOCATED_IN) if e.src == cur), None)
            if not nxt:
                break
            chain.append(name(nxt))
            cur = nxt
        shop_offers = [e for e in sellers if e.src == shid]
        gated = sorted([e for e in shop_offers if e.cond_group is not None], key=offer_key)
        item_only = [e for e in shop_offers if e.cond_group is None]
        print(f"  {name(shid)}")
        print(f"     run by:   {name(op) if op else '(operator not recorded)'}")
        print(f"     found at: {'  ▸  '.join(chain) if chain else '(unplaced in skeleton)'}")
        if item_only:
            print(f"     stocks it item-only — buy freely (currency layer deferred)")
        if gated:
            print(f"     plus {len(gated)} gated offer(s) the evaluator can reason about:")
            for e in gated:
                a = kg.children_of(e.cond_group)[0]
                print(f"        • gated on: {a.atom_type.value} {name(a.ref_node)} = {a.data.get('state')}")

    accounts = {
        "Fresh main (Hiscores synced, nothing done)":
            AccountState(mode="main", observable_families={"quest", "achievement_diary"}),
        "Mid-game main (What Lies Below done, Varrock Hard diary)":
            AccountState(mode="main", observable_families={"quest", "achievement_diary"},
                         quest_state={"quest:what-lies-below": "completed"},
                         diary_state={"diary:varrock:easy": "completed",
                                      "diary:varrock:medium": "completed",
                                      "diary:varrock:hard": "completed"}),
        "Unsynced account (no quest/diary plugin yet)":
            AccountState(mode="main"),  # nothing observable -> the planner refuses to guess
    }
    zaff_offers = sorted([e for e in sellers if e.src == "shop:zaffs-superior-staffs"], key=offer_key)
    for label, st in accounts.items():
        print(f"\n  ── {label} ──")
        for e in zaff_offers:
            a = kg.children_of(e.cond_group)[0]
            v = evaluate(e.cond_group, st, kg)
            print(f"     {VERDICT[v]}  battlestaff via {a.atom_type.value.replace('_', ' ')} "
                  f"'{name(a.ref_node)}'")


def q2_storeline_stock() -> None:
    hr('Q2.  "What does Lowe\'s Archery Emporium ACTUALLY stock?"  (the Storeline win)')
    LOWES = "shop:lowes-archery-emporium"
    stock = sorted((e.dst for e in es(EdgeType.SELLS) if e.src == LOWES), key=name)
    print('\n  The owner wrote shorthand: "Bows", "Crossbows", "Ammunition".')
    print(f"  The graph now knows the exact {len(stock)} items (from the wiki Storeline table):\n")
    for d in stock:
        print(f"     • {name(d)}")


def q3_reverse_acquisition() -> None:
    hr('Q3.  "Where can I buy a Bronze arrow?"  (reverse acquisition — any item)')
    by_name = {}
    for e in es(EdgeType.SELLS):
        by_name.setdefault(name(e.dst), e.dst)
    for item_name in ["Bronze arrow", "Tinderbox", "Beer", "Battlestaff"]:
        tgt = by_name.get(item_name)
        if not tgt:
            print(f"  {item_name}: (no shop in the graph stocks this yet)")
            continue
        shops = sorted({name(e.src) for e in es(EdgeType.SELLS) if e.dst == tgt})
        print(f"  {item_name} ({tgt}) — sold by: {', '.join(shops)}")


def q4_item_facets() -> None:
    hr("Q4.  The catalog underneath is deep too  (item-facet layer, slices 1-5)")
    in_e = lambda t, dst: [e for e in es(t) if e.dst == dst]
    out_e = lambda t, src: [e for e in es(t) if e.src == src]

    variants = sorted(name(e.src) for e in in_e(EdgeType.SAME_ENTITY, "item:amulet-of-glory"))
    print(f"\n  • Every variant of the Amulet of glory:  {len(variants)} found")
    print(f"      {', '.join(variants[:6])}{' …' if len(variants) > 6 else ''}")

    mats = [name(e.dst) for e in out_e(EdgeType.CONSUMES, "recipe:charge-scythe-of-vitur")
            if (e.data or {}).get("role") == "material"]
    print(f"\n  • To CHARGE a Scythe of vitur it consumes:  {', '.join(mats)}")

    rod = {e.src for e in in_e(EdgeType.SAME_ENTITY, "item:ring-of-dueling")}
    destroyed = any(e.dst is None for e in es(EdgeType.DEGRADES_TO) if e.src in rod)
    print(f"\n  • Is a Ring of dueling DESTROYED on its last charge?  "
          f"{'Yes — it vanishes' if destroyed else 'no'}")

    hb = next(iter(out_e(EdgeType.HAS_BONUSES, "item:22325")), None)
    if hb:
        print(f"\n  • Scythe of vitur slash attack bonus:  +{kg.node(hb.dst).data['stats']['slash_attack_bonus']}")

    print(f"\n  Graph: {len(kg.nodes)} nodes / {len(kg.edges)} edges — all source-grounded, on main.\n")


if __name__ == "__main__":
    q1_acquisition_and_evaluator()
    q2_storeline_stock()
    q3_reverse_acquisition()
    q4_item_facets()
