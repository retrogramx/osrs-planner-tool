"""Scratch scenario runner on a SMALL, WIKI-VERIFIED real KG (NOT committed — a testing aid).

Every gate below is taken from the OSRS Wiki (completion semantics: a goal-tracker
tracks COMPLETING a quest). Sources fetched 2026-06-18:
  - Cook's Assistant: no requirements.
  - Dragon Slayer I: 32 Quest Points (to enter Champions' Guild to start).
  - Tree Gnome Village: no skill/quest/QP requirement (combat only).
  - The Grand Tree: 25 Agility (needed to COMPLETE; "not required to start").
  - Monkey Madness I: The Grand Tree + Tree Gnome Village (both completed).
  - Lost City: 31 Crafting + 36 Woodcutting (to complete); no quest prereqs.
  - Nature Spirit: The Restless Ghost + Priest in Peril (both completed).
  - Fairytale I - Growing Pains: Lost City + Nature Spirit (completed).
  - Fairytale II - Cure a Queen: Fairytale I (completed).
  - Fairy rings: Fairytale II STARTED (in-progress) -- the real 3-state in-progress gate.

Run from repo root:  ./venv/bin/python scenario_runner.py
"""
from __future__ import annotations

from osrs_planner.engine.engine import Engine
from osrs_planner.engine.result import Ok, Empty, Problem
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from osrs_planner.engine.kg.store import InMemoryKGStore

# ---- condition-group ids ----
G_DS1, G_GRANDTREE, G_MM1, G_NATURE, G_LOSTCITY, G_FT1, G_FT2, G_FAIRY = 1, 2, 3, 4, 5, 6, 7, 8
G_DSCIM_WIELD, G_DSCIM_BUY = 9, 10
G_RFD, G_BGLOVES = 11, 12
G_TORSO, G_MA2, G_CAPE = 13, 14, 15
G_OBBYMAUL = 16


def _q(slug, name):
    return Node(id=f"quest:{slug}", kind=NodeKind.QUEST, name=name, slug=slug, data={})


def build_real_store() -> InMemoryKGStore:
    nodes = [
        # skills referenced by skill_level atoms
        Node(id="skill:agility", kind=NodeKind.SKILL, name="Agility", slug="agility", data={}),
        Node(id="skill:crafting", kind=NodeKind.SKILL, name="Crafting", slug="crafting", data={}),
        Node(id="skill:woodcutting", kind=NodeKind.SKILL, name="Woodcutting", slug="woodcutting", data={}),
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={}),
        # Dragon scimitar: the item + the "wielding it" goal node
        Node(id="item:4587", kind=NodeKind.ITEM, name="Dragon scimitar", slug="dragon-scimitar",
             data={"members": True, "buy_from": "Daga (Ape Atoll)", "buy_cost": 100000}),
        Node(id="gear_loadout:dragon-scimitar", kind=NodeKind.GEAR_LOADOUT,
             name="Wielding a Dragon scimitar", slug="dragon-scimitar", data={}),
        # --- Barrows gloves / Recipe for Disaster (a grandmaster capstone) ---
        Node(id="skill:cooking", kind=NodeKind.SKILL, name="Cooking", slug="cooking", data={}),
        Node(id="skill:mining", kind=NodeKind.SKILL, name="Mining", slug="mining", data={}),
        Node(id="skill:fishing", kind=NodeKind.SKILL, name="Fishing", slug="fishing", data={}),
        Node(id="skill:thieving", kind=NodeKind.SKILL, name="Thieving", slug="thieving", data={}),
        Node(id="skill:herblore", kind=NodeKind.SKILL, name="Herblore", slug="herblore", data={}),
        Node(id="skill:magic", kind=NodeKind.SKILL, name="Magic", slug="magic", data={}),
        Node(id="skill:smithing", kind=NodeKind.SKILL, name="Smithing", slug="smithing", data={}),
        Node(id="skill:firemaking", kind=NodeKind.SKILL, name="Firemaking", slug="firemaking", data={}),
        Node(id="skill:ranged", kind=NodeKind.SKILL, name="Ranged", slug="ranged", data={}),
        Node(id="skill:fletching", kind=NodeKind.SKILL, name="Fletching", slug="fletching", data={}),
        Node(id="item:7462", kind=NodeKind.ITEM, name="Barrows gloves", slug="barrows-gloves",
             data={"members": True, "tradeable": False, "buy_from": "Culinaromancer's Chest",
                   "buy_cost": 130000, "buy_cost_elite_lumbridge": 104000}),
        _q("recipe-for-disaster", "Recipe for Disaster"),
        _q("fishing-contest", "Fishing Contest"),
        _q("goblin-diplomacy", "Goblin Diplomacy"),
        _q("big-chompy-bird-hunting", "Big Chompy Bird Hunting"),
        _q("murder-mystery", "Murder Mystery"),
        _q("witchs-house", "Witch's House"),
        _q("gertrudes-cat", "Gertrude's Cat"),
        _q("shadow-of-the-storm", "Shadow of the Storm"),
        _q("legends-quest", "Legends' Quest"),
        _q("desert-treasure-1", "Desert Treasure I"),
        _q("horror-from-the-deep", "Horror from the Deep"),
        # --- Fighter torso (Barbarian Assault) + Mage Arena 2 cape (non-gold, activity rewards) ---
        Node(id="skill:defence", kind=NodeKind.SKILL, name="Defence", slug="defence", data={}),
        Node(id="npc:penance-queen", kind=NodeKind.MONSTER, name="Penance Queen",
             slug="penance-queen", data={"minigame": "Barbarian Assault"}),
        Node(id="item:10551", kind=NodeKind.ITEM, name="Fighter torso", slug="fighter-torso",
             data={"members": True, "tradeable": False,
                   "cost_currency": "Honour points", "cost": "375 per role (x4) + 1 Penance Queen kill"}),
        _q("mage-arena-1", "Mage Arena I"),
        _q("mage-arena-2", "Mage Arena II"),
        Node(id="item:21791", kind=NodeKind.ITEM, name="Imbued saradomin cape",
             slug="imbued-saradomin-cape",
             data={"members": True, "tradeable": False, "source": "Mage Arena II reward"}),
        # --- TzHaar-ket-om (obsidian maul): TRADEABLE -> the divergence case ---
        Node(id="item:6528", kind=NodeKind.ITEM, name="TzHaar-ket-om", slug="tzhaar-ket-om",
             data={"members": True, "tradeable": True,
                   "acq_ge_coins": 209000, "acq_tokkul": 75001, "acq_tokkul_karamja_gloves": 65001,
                   "acq_drop": "TzHaar-Ket 1/512"}),
        Node(id="gear_loadout:obby-maul", kind=NodeKind.GEAR_LOADOUT,
             name="Wielding a TzHaar-ket-om", slug="obby-maul", data={}),
        # quests
        _q("cooks-assistant", "Cook's Assistant"),
        _q("dragon-slayer-1", "Dragon Slayer I"),
        _q("tree-gnome-village", "Tree Gnome Village"),
        _q("the-grand-tree", "The Grand Tree"),
        _q("monkey-madness-1", "Monkey Madness I"),
        _q("restless-ghost", "The Restless Ghost"),
        _q("priest-in-peril", "Priest in Peril"),
        _q("nature-spirit", "Nature Spirit"),
        _q("lost-city", "Lost City"),
        _q("fairytale-1", "Fairytale I - Growing Pains"),
        _q("fairytale-2", "Fairytale II - Cure a Queen"),
        # access unlock (the in-progress showcase)
        Node(id="access:fairy-rings", kind=NodeKind.ACCESS, name="Fairy ring network",
             slug="fairy-rings", data={"note": "use the fairy ring transport network"}),
    ]

    def C(state):  # quest-completion atom helper
        return state

    groups = {
        G_DS1: ConditionGroup(id=G_DS1, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)]),
        G_GRANDTREE: ConditionGroup(id=G_GRANDTREE, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:agility", threshold=25)]),
        G_MM1: ConditionGroup(id=G_MM1, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:the-grand-tree", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:tree-gnome-village", data={"state": "completed"})]),
        G_NATURE: ConditionGroup(id=G_NATURE, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:restless-ghost", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:priest-in-peril", data={"state": "completed"})]),
        G_LOSTCITY: ConditionGroup(id=G_LOSTCITY, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:crafting", threshold=31),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:woodcutting", threshold=36)]),
        G_FT1: ConditionGroup(id=G_FT1, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:lost-city", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:nature-spirit", data={"state": "completed"})]),
        G_FT2: ConditionGroup(id=G_FT2, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:fairytale-1", data={"state": "completed"})]),
        # fairy rings: Fairytale II merely STARTED (in_progress) -- the real 3-state gate
        G_FAIRY: ConditionGroup(id=G_FAIRY, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:fairytale-2", data={"state": "in_progress"})]),
        # WIELD a dragon scimitar = own it AND 60 Attack AND Monkey Madness I completed
        G_DSCIM_WIELD: ConditionGroup(id=G_DSCIM_WIELD, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:4587", qty=1),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=60),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:monkey-madness-1", data={"state": "completed"})]),
        # OBTAIN the scimitar (buy from Daga) = Monkey Madness I completed (coins NOT modeled here)
        G_DSCIM_BUY: ConditionGroup(id=G_DSCIM_BUY, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:monkey-madness-1", data={"state": "completed"})]),
        # Recipe for Disaster (FULL): 175 QP + 13 skills + 12 prerequisite quests.
        # MM1 and Nature Spirit chain deeper (already modeled); the rest are leaf quests
        # in this slice (their own sub-trees -- e.g. Desert Treasure's 6 -- not expanded).
        G_RFD: ConditionGroup(id=G_RFD, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=175),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:cooking", threshold=70),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:agility", threshold=48),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:mining", threshold=50),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:fishing", threshold=53),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:thieving", threshold=53),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:herblore", threshold=25),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:magic", threshold=59),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:smithing", threshold=40),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:firemaking", threshold=50),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:ranged", threshold=40),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:crafting", threshold=40),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:fletching", threshold=10),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:woodcutting", threshold=36),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:fishing-contest", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:goblin-diplomacy", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:big-chompy-bird-hunting", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:murder-mystery", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:nature-spirit", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:witchs-house", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:gertrudes-cat", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:shadow-of-the-storm", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:legends-quest", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:monkey-madness-1", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:desert-treasure-1", data={"state": "completed"}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:horror-from-the-deep", data={"state": "completed"})]),
        # OBTAIN Barrows gloves = Recipe for Disaster completed (untradeable -> no GE; coins not modeled)
        G_BGLOVES: ConditionGroup(id=G_BGLOVES, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:recipe-for-disaster", data={"state": "completed"})]),
        # Fighter torso: 1 Penance Queen kill (proxy for full BA) + 40 Defence to wear.
        # NOTE: the real cost is 375 Honour points PER ROLE (x4) -- a minigame currency the
        # engine has NO atom for. Modeled only via the kill_count proxy; honour points unmodeled.
        G_TORSO: ConditionGroup(id=G_TORSO, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.KILL_COUNT, ref_node="npc:penance-queen", threshold=1),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:defence", threshold=40)]),
        # Mage Arena II miniquest: 75 Magic + Mage Arena I completed (+ casting activity, folded in)
        G_MA2: ConditionGroup(id=G_MA2, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:magic", threshold=75),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:mage-arena-1", data={"state": "completed"})]),
        # OBTAIN the imbued god cape = Mage Arena II completed (untradeable; no gold)
        G_CAPE: ConditionGroup(id=G_CAPE, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:mage-arena-2", data={"state": "completed"})]),
        # WIELD the obby maul = own it + 60 Strength (NO Attack/Defence -> the pure weapon).
        # NOTE: acquiring item:6528 has NO graph prereq (no quest/access) -- it's pure COST:
        # main buys GE ~209k coins; iron grinds 75,001 Tokkul or a 1/512 drop. That account-type
        # divergence is the deferred expand_for_account cost layer, NOT in the engine's requires tree.
        G_OBBYMAUL: ConditionGroup(id=G_OBBYMAUL, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:6528", qty=1),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:strength", threshold=60)]),
    }

    def req(src, gid):
        return Edge(id=hash(src) & 0xffff, type=EdgeType.REQUIRES, src=src, dst=None, cond_group=gid)

    edges = [
        req("quest:dragon-slayer-1", G_DS1),
        req("quest:the-grand-tree", G_GRANDTREE),
        req("quest:monkey-madness-1", G_MM1),
        req("quest:nature-spirit", G_NATURE),
        req("quest:lost-city", G_LOSTCITY),
        req("quest:fairytale-1", G_FT1),
        req("quest:fairytale-2", G_FT2),
        req("access:fairy-rings", G_FAIRY),
        req("gear_loadout:dragon-scimitar", G_DSCIM_WIELD),
        req("item:4587", G_DSCIM_BUY),
        req("quest:recipe-for-disaster", G_RFD),
        req("item:7462", G_BGLOVES),
        req("item:10551", G_TORSO),
        req("quest:mage-arena-2", G_MA2),
        req("item:21791", G_CAPE),
        req("gear_loadout:obby-maul", G_OBBYMAUL),
        # item:6528 has NO requires edge -- acquiring it is pure cost (GE/Tokkul/drop), not a graph prereq.
        # cooks-assistant, tree-gnome-village, restless-ghost, priest-in-peril: no requires edges
    ]
    return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


GOAL = {
    "cooks_assistant": "quest:cooks-assistant",
    "dragon_slayer_1": "quest:dragon-slayer-1",
    "grand_tree": "quest:the-grand-tree",
    "tree_gnome_village": "quest:tree-gnome-village",
    "monkey_madness_1": "quest:monkey-madness-1",
    "lost_city": "quest:lost-city",
    "nature_spirit": "quest:nature-spirit",
    "fairytale_1": "quest:fairytale-1",
    "fairytale_2": "quest:fairytale-2",
    "fairy_rings": "access:fairy-rings",
    "dragon_scimitar": "gear_loadout:dragon-scimitar",
    "barrows_gloves": "item:7462",
    "recipe_for_disaster": "quest:recipe-for-disaster",
    "fighter_torso": "item:10551",
    "mage_arena_2_cape": "item:21791",
    "obby_maul": "gear_loadout:obby-maul",
}

FULLY_SYNCED = {"skill_level", "skill_xp", "item", "quest", "achievement_diary",
                "combat_achievement", "kill_count", "clue_scrolls", "quest_points"}


def make_state(mode="normal", levels=None, quests=None, qp=0, kc=None, synced=True, observed=None) -> AccountState:
    """levels: {"agility": 30}.  quests: {"the-grand-tree": "completed", "fairytale-2": "in_progress"}.
    kc: {"penance-queen": 1} (kill counts, keyed by npc slug).
    synced=True -> absence reads as real FALSE; synced=False -> absence reads as UNKNOWN (can't verify)."""
    fams = set(observed) if observed is not None else (set(FULLY_SYNCED) if synced else set())
    return AccountState(
        mode=mode,
        levels={f"skill:{k}": v for k, v in (levels or {}).items()},
        quest_state={f"quest:{k}": v for k, v in (quests or {}).items()},
        kc={f"npc:{k}": v for k, v in (kc or {}).items()},
        qp=qp,
        observable_families=fams,
    )


def _steps(steps):
    return "\n".join(f"    - {s.name} [{s.reason}] -> {s.status}" for s in steps) if steps else "    (none)"


def show(label, state, goal_key):
    eng = Engine(build_real_store())
    goal = GOAL.get(goal_key, goal_key)
    print("=" * 74)
    print(f"SCENARIO: {label}")
    print(f"  account: mode={state.mode} qp={state.qp} levels={state.levels or '{}'} quests={state.quest_state or '{}'}")
    print(f"  synced: {sorted(state.observable_families) or '(nothing synced)'}")
    print(f"  GOAL: {goal}")
    print("-" * 74)
    r = eng.is_unlocked(state, goal)
    if isinstance(r, Ok):
        print(f"is_unlocked: {r.card.status.upper()}")
        if r.card.blockers:
            print("  blockers:\n" + _steps(r.card.blockers))
    elif isinstance(r, Empty):
        print(f"is_unlocked: (empty) {r.reason}")
    else:
        print(f"is_unlocked: PROBLEM {r.kind.value} — {r.message}")
    r = eng.prereqs_for(state, goal)
    if isinstance(r, Ok):
        print("prereqs_for (ordered, prereqs first):\n" + _steps(r.card.steps))
    elif isinstance(r, Empty):
        print(f"prereqs_for: (empty) {r.reason}  <- already satisfied / nothing to do")
    else:
        print(f"prereqs_for: PROBLEM {r.kind.value} — {r.message}")
    r = eng.next_steps(state, goal)
    if isinstance(r, Ok):
        print("next_steps (do now):\n" + _steps(r.card.steps))
    elif isinstance(r, Empty):
        print(f"next_steps: (empty) {r.reason}")
    else:
        print(f"next_steps: PROBLEM {r.kind.value} — {r.message}")
    print()


if __name__ == "__main__":
    # Mid-game main, partway in: MM1 + its gnome chain done, Nature Spirit chain done,
    # ~100 QP, several skills trained but several still short of the RFD gates. Wants Barrows gloves.
    acct = make_state(
        mode="normal", qp=100,
        levels={"cooking": 72, "agility": 50, "mining": 45, "fishing": 60, "thieving": 40,
                "herblore": 30, "magic": 70, "smithing": 45, "firemaking": 55, "ranged": 70,
                "crafting": 50, "fletching": 30, "woodcutting": 50, "attack": 70},
        quests={"monkey-madness-1": "completed", "the-grand-tree": "completed",
                "tree-gnome-village": "completed", "nature-spirit": "completed",
                "priest-in-peril": "completed", "restless-ghost": "completed",
                "goblin-diplomacy": "completed", "witchs-house": "completed"},
        synced=True)
    show("Mid-game main, partway through the reqs — wants BARROWS GLOVES", acct, "barrows_gloves")
    # Same account, but query Recipe for Disaster DIRECTLY -- this is where the skill/QP gates surface.
    show("...same account, querying Recipe for Disaster directly", acct, "recipe_for_disaster")

    # FIGHTER TORSO (Barbarian Assault, Honour-point currency): 40 Def but never beaten the Queen.
    torso_acct = make_state(mode="normal", levels={"defence": 60}, kc={}, synced=True)
    show("60 Defence, never finished a BA wave — wants FIGHTER TORSO", torso_acct, "fighter_torso")

    # MAGE ARENA 2 CAPE: 70 Magic (below 75), Mage Arena I not done.
    cape_acct = make_state(mode="ironman", levels={"magic": 70}, quests={}, synced=True)
    show("Ironman, 70 Magic, no Mage Arena I — wants MAGE ARENA 2 CAPE", cape_acct, "mage_arena_2_cape")

    # OBBY MAULER PURE (1 Att / 1 Def / 60 Str, no maul yet) -- TWIN ACCOUNTS, same goal.
    pure = dict(levels={"attack": 1, "defence": 1, "strength": 60, "hitpoints": 30}, synced=True)
    show("Obby-mauler pure (IRONMAN) — wants TzHaar-ket-om", make_state(mode="ironman", **pure), "obby_maul")
    show("Obby-mauler pure (REGULAR) — wants TzHaar-ket-om", make_state(mode="normal", **pure), "obby_maul")
