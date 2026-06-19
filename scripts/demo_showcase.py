"""Narrative showcase: the deterministic engine reasoning over the REAL committed
knowledge graph (kg/*.json via JsonKGStore). A human-eyeball demo of quality
results across several account states and account types; not used by the app.

Run from repo root: ./venv/bin/python scripts/demo_showcase.py
"""
from __future__ import annotations

import pathlib

from osrs_planner.engine.engine import Engine
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.result import Ok, Empty, Problem
from osrs_planner.engine.state import AccountState, account_family

# scripts/ -> repo root -> kg/
KG_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "kg")

# Every Hiscores-observable family (so "absent" reads as a real zero, not UNKNOWN).
OBSERVABLE = {"skill_level", "skill_xp", "combat_level", "quest", "item",
              "achievement_diary", "combat_achievement", "is_unlocked",
              "gear_loadout", "kill_count", "account_type", "clue_scrolls",
              "combat_achievement_points"}

engine = Engine(JsonKGStore.from_dir(KG_DIR))
KG = JsonKGStore.from_dir(KG_DIR)


def name(node_id: str) -> str:
    n = KG.node(node_id)
    return n.name if n else node_id


def acct(mode="main", **kw) -> AccountState:
    return AccountState(mode=mode, observable_families=set(OBSERVABLE), **kw)


def show_unlock(state, goal_id):
    res = engine.is_unlocked(state, goal_id)
    if isinstance(res, Ok):
        icon = {"unlocked": "[OK]   UNLOCKED", "locked": "[X]    LOCKED",
                "indeterminate": "[?]    CAN'T VERIFY"}[res.card.status]
        print(f"   is_unlocked  -> {icon}")
        for b in res.card.blockers:
            print(f"                    - needs: {b.name}  ({b.reason}, {b.status})")
    elif isinstance(res, Empty):
        print(f"   is_unlocked  -> (nothing to do: {res.reason.value})")
    else:
        print(f"   is_unlocked  -> problem: {res.message}")


def show_plan(state, goal_id, sample=6):
    res = engine.prereqs_for(state, goal_id)
    if isinstance(res, Ok):
        steps = res.card.steps
        unmet = [s for s in steps if s.status != "satisfied"]
        print(f"   prereqs_for  -> {len(steps)} steps in the plan "
              f"({len(unmet)} still to do)")
        for s in unmet[:sample]:
            print(f"                    * {s.name}  ({s.reason})")
        if len(unmet) > sample:
            print(f"                    * ... and {len(unmet) - sample} more")
    elif isinstance(res, Empty):
        print(f"   prereqs_for  -> done already ({res.reason.value})")
    else:
        print(f"   prereqs_for  -> problem: {res.message}")


def header(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------------
header("SCENARIO 1  -  The Dragon scimitar journey (a main account)")
print("\nA brand-new main (level 3, no quests) asks: can I wield a Dragon scimitar?")
new_main = acct()
show_unlock(new_main, "item:4587")
show_plan(new_main, "item:4587")

print("\nSame main after training Attack to 60 and finishing Monkey Madness I:")
trained = acct(levels={"skill:attack": 60},
               quest_state={"quest:monkey-madness-i": "completed"})
show_unlock(trained, "item:4587")

# ---------------------------------------------------------------------------
header("SCENARIO 2  -  'You can wield it, but your quest log is inconsistent'")
print("\nA main who marked Monkey Madness I done -- but NOT its own prerequisite")
print("quests. The engine answers two DIFFERENT questions honestly:")
inconsistent = acct(levels={"skill:attack": 60},
                    quest_state={"quest:monkey-madness-i": "completed"})
show_unlock(inconsistent, "item:4587")       # immediate gate: satisfied
show_plan(inconsistent, "item:4587")          # full closure: flags the gap
print("\n   -> is_unlocked checks the IMMEDIATE gate (met). prereqs_for walks the")
print("      WHOLE chain and surfaces the ancestor quests that were never done.")

# ---------------------------------------------------------------------------
header("SCENARIO 3  -  Barrows gloves: immediate blocker vs the whole mountain")
print("\nFresh main. is_unlocked shows only the NEXT wall; prereqs_for shows it all:")
fresh = acct()
show_unlock(fresh, "item:7462")
show_plan(fresh, "item:7462", sample=8)

# ---------------------------------------------------------------------------
header("SCENARIO 4  -  Same quest, different account types (the divergence)")
print("\nDoric's Quest has a Mining 15 requirement modelled as an OR:")
print("'be a main (just buy/trade the bar) OR have Mining 15 (self-source it)'.")
print("Watch the same quest answer differently by account type:\n")
for mode in ("main", "ironman", "ultimate_ironman", "hardcore_group_ironman"):
    st = acct(mode=mode)
    res = engine.is_unlocked(st, "quest:dorics-quest")
    blk = res.card.blockers if isinstance(res, Ok) else []
    # The display/advisor layer drops the 'or be a main' branch a non-main can't act on.
    actionable = [b.name for b in blk if b.reason != "account_type"]
    fam = account_family(mode)
    if not blk:
        verdict = "no extra requirement (a main just buys it)"
    elif actionable:
        verdict = f"must self-source: {', '.join(actionable)} 15"
    else:
        verdict = "blocked"
    print(f"   {mode:<24} (family={fam:<7}) -> {verdict}")
print("\n   -> The engine faithfully reports BOTH OR-branches; the advisor/UI layer")
print("      hides 'or be a main' from an ironman (it's not an action they can take).")

# ---------------------------------------------------------------------------
header("SCENARIO 5  -  Voidwaker: a 3-component build (AND logic)")
print("\nOwning only 2 of the 3 parts (hilt + blade, no gem):")
two_parts = acct(counts={"item:27681": 1, "item:27684": 1})
show_unlock(two_parts, "item:27690")
print("\nOwning all 3 parts:")
all_parts = acct(counts={"item:27681": 1, "item:27684": 1, "item:27687": 1})
show_unlock(all_parts, "item:27690")

# ---------------------------------------------------------------------------
header("SCENARIO 6  -  Full Infinity: a gear set AND the stats to use it")
print("\nOwning 4 of 5 pieces (missing the hat), Magic 50 / Defence 25:")
pieces = ["item:6916", "item:6924", "item:6922", "item:6920"]  # top/bottoms/gloves/boots
partial = acct(levels={"skill:magic": 50, "skill:defence": 25},
               counts={p: 1 for p in pieces})
show_unlock(partial, "gear_loadout_goal:infinity")
print("\nAll 5 pieces + Magic 50 / Defence 25:")
full = acct(levels={"skill:magic": 50, "skill:defence": 25},
            counts={p: 1 for p in pieces + ["item:6918"]})
show_unlock(full, "gear_loadout_goal:infinity")

print("\n" + "=" * 70)
print("All verdicts above are computed live by the engine over the real KG.")
print("=" * 70)
