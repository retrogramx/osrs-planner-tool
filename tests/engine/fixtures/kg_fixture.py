# tests/engine/fixtures/kg_fixture.py
"""Hand-authored KG fixture for the goal-engine tests.

Encodes the kg-schema-v1 worked examples as an InMemoryKGStore:
  - Scurrius (npc:7221) access tree: located_in -> region:scurrius-lair,
    region gated_by access:scurrius-lair, region:varrock-sewers GRANTS that access,
    and npc:7221 REQUIRES access:scurrius-lair (+ the flagship combat condition).
  - The flagship requires condition on npc:7221:
        OR( AND(70 Attack, 70 Strength), gear_loadout:void )
  - gear_loadout:void composition (dst=NULL requires edge, "the constraint IS the tree"):
        AND( OR(item:11663, item:11664, item:11665),  # any one Void helm (mage/ranger/melee)
             item:8839,  # Void top
             item:8840,  # Void robe
             item:8842 ) # Void gloves
  - Two quests: quest:cooks-assistant (no reqs) and quest:rag-and-bone-man-ii whose
    requires tree carries an IN_PROGRESS quest prereq (kg-schema scale-gap G1 worked case).
  - One diary tier: diary:varrock:hard, requiring quest:cooks-assistant COMPLETED.

IDs/atoms cross-checked against research/kg-schema-v1.md "Worked example -- Scurrius"
and the flagship "(70 Attack AND 70 Strength) OR full Void" condition.

This is TEST INFRA: a builder function + a pytest fixture + sample AccountStates.
"""

from __future__ import annotations

import pytest

from osrs_planner.engine.kg.model import (
    AtomType,
    ConditionAtom,
    ConditionGroup,
    Edge,
    EdgeType,
    Node,
    NodeKind,
    Op,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState

# ---------------------------------------------------------------------------
# condition_group ids (match the kg-schema worked example where it pins them):
#   1 = OR root on npc:7221 ; 2 = AND(70 Att, 70 Str) ; 3 = AND(gear_loadout:void)
#   10 = gear_loadout:void composition root ; 11 = OR of the three Void helms
#   20 = AND on diary:varrock:hard ; 30 = AND on quest:rag-and-bone-man-ii
# ---------------------------------------------------------------------------
G_SCURRIUS_OR = 1
G_STATS_AND = 2
G_VOID_BRANCH = 3
G_VOID_SET = 10
G_VOID_HELM = 11
G_DIARY_AND = 20
G_RAGII_AND = 30


def build_nodes() -> list[Node]:
    """Every node the fixture's edges/atoms reference (spine + worked example)."""
    return [
        # --- Scurrius reach subgraph ---
        Node(id="npc:7221", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius",
             data={"is_boss": True, "combat_level": 250}),
        Node(id="region:scurrius-lair", kind=NodeKind.REGION,
             name="Scurrius's Lair (instance)", slug="scurrius-lair",
             data={"instanced": True}),
        Node(id="region:varrock-sewers", kind=NodeKind.REGION, name="Varrock Sewers",
             slug="varrock-sewers", data={}),
        Node(id="access:scurrius-lair", kind=NodeKind.ACCESS, name="Scurrius Lair Access",
             slug="scurrius-lair",
             data={"note": "ability to enter the Scurrius fight instance"}),
        # --- skills referenced by the flagship stats branch ---
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={}),
        Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength", data={}),
        Node(id="skill:cooking", kind=NodeKind.SKILL, name="Cooking", slug="cooking", data={}),
        # --- full Void loadout + its piece items ---
        Node(id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Full Void Knight",
             slug="void", data={"styles": ["melee", "ranged", "magic"]}),
        Node(id="item:11663", kind=NodeKind.ITEM, name="Void mage helm", slug="void-mage-helm",
             data={"slot": "head"}),
        Node(id="item:11664", kind=NodeKind.ITEM, name="Void ranger helm", slug="void-ranger-helm",
             data={"slot": "head"}),
        Node(id="item:11665", kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm",
             data={"slot": "head"}),
        Node(id="item:8839", kind=NodeKind.ITEM, name="Void knight top", slug="void-knight-top",
             data={"slot": "body"}),
        Node(id="item:8840", kind=NodeKind.ITEM, name="Void knight robe", slug="void-knight-robe",
             data={"slot": "legs"}),
        Node(id="item:8842", kind=NodeKind.ITEM, name="Void knight gloves", slug="void-knight-gloves",
             data={"slot": "hands"}),
        # --- account types (mode-conditional branches read account:* data) ---
        Node(id="account:normal", kind=NodeKind.ACCOUNT_TYPE, name="Normal", slug="normal",
             data={"must_self_acquire": False, "can_ge": True}),
        Node(id="account:ironman", kind=NodeKind.ACCOUNT_TYPE, name="Ironman", slug="ironman",
             data={"must_self_acquire": True, "can_ge": False}),
        # --- quests (one no-req, one with an in_progress prereq: scale-gap G1) ---
        Node(id="quest:cooks-assistant", kind=NodeKind.QUEST, name="Cook's Assistant",
             slug="cooks-assistant", data={"no_requirements": True}),
        Node(id="quest:rag-and-bone-man-ii", kind=NodeKind.QUEST, name="Rag and Bone Man II",
             slug="rag-and-bone-man-ii", data={}),
        # --- one diary tier (task-based 3-state) ---
        Node(id="diary:varrock:hard", kind=NodeKind.DIARY, name="Varrock Diary (Hard)",
             slug="varrock:hard", data={"region": "varrock", "tier": "hard"}),
    ]


def build_groups() -> dict[int, ConditionGroup]:
    """Condition trees. children = list of (sub-group ids as int) and/or ConditionAtom objects.

    Per D2: children hold ONLY int (sub-group id) or ConditionAtom (inline leaf) -- never a raw
    ConditionGroup object. Sub-group references are int ids; all sub-groups appear in this dict.
    """
    return {
        # npc:7221 flagship: OR( AND(70 Att, 70 Str), gear_loadout:void )
        G_SCURRIUS_OR: ConditionGroup(
            id=G_SCURRIUS_OR, op=Op.OR, parent=None,
            children=[G_STATS_AND, G_VOID_BRANCH]),
        G_STATS_AND: ConditionGroup(
            id=G_STATS_AND, op=Op.AND, parent=G_SCURRIUS_OR,
            children=[
                ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack",
                              threshold=70),
                ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:strength",
                              threshold=70),
            ]),
        G_VOID_BRANCH: ConditionGroup(
            id=G_VOID_BRANCH, op=Op.AND, parent=G_SCURRIUS_OR,
            children=[
                ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node="gear_loadout:void"),
            ]),
        # gear_loadout:void composition: AND( OR(3 helms), top, robe, gloves )
        # G_VOID_HELM (11) is a sub-group referenced by int id, not inline object (D2).
        G_VOID_SET: ConditionGroup(
            id=G_VOID_SET, op=Op.AND, parent=None,
            children=[
                G_VOID_HELM,
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8840", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8842", qty=1),
            ]),
        G_VOID_HELM: ConditionGroup(
            id=G_VOID_HELM, op=Op.OR, parent=G_VOID_SET,
            children=[
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11663", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11664", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11665", qty=1),
            ]),
        # diary:varrock:hard requires quest:cooks-assistant COMPLETED
        G_DIARY_AND: ConditionGroup(
            id=G_DIARY_AND, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:cooks-assistant",
                              data={"state": "completed"}),
            ]),
        # quest:rag-and-bone-man-ii requires quest:cooks-assistant only IN_PROGRESS (G1)
        G_RAGII_AND: ConditionGroup(
            id=G_RAGII_AND, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:cooks-assistant",
                              data={"state": "in_progress"}),
            ]),
    }


def build_edges() -> list[Edge]:
    """Fact edges. requires reads dependent->prerequisite; grants reads producer->produced."""
    return [
        # Scurrius reach (kg-schema edge ids 9001-9004)
        Edge(id=9001, type=EdgeType.LOCATED_IN, src="npc:7221",
             dst="region:scurrius-lair", cond_group=None),
        Edge(id=9002, type=EdgeType.GATED_BY, src="region:scurrius-lair",
             dst="access:scurrius-lair", cond_group=None),
        Edge(id=9003, type=EdgeType.GRANTS, src="region:varrock-sewers",
             dst="access:scurrius-lair", cond_group=None),
        Edge(id=9004, type=EdgeType.REQUIRES, src="npc:7221",
             dst="access:scurrius-lair", cond_group=None),
        # npc:7221 flagship condition (dst=None: the constraint IS the tree)
        Edge(id=9005, type=EdgeType.REQUIRES, src="npc:7221",
             dst=None, cond_group=G_SCURRIUS_OR),
        # gear_loadout:void composition (dst=None requires edge, kg-schema edge 9100)
        Edge(id=9100, type=EdgeType.REQUIRES, src="gear_loadout:void",
             dst=None, cond_group=G_VOID_SET),
        # diary tier requires (dst=None: the constraint IS the tree)
        Edge(id=9200, type=EdgeType.REQUIRES, src="diary:varrock:hard",
             dst=None, cond_group=G_DIARY_AND),
        # rag-and-bone-man-ii requires an in_progress quest (dst=None)
        Edge(id=9300, type=EdgeType.REQUIRES, src="quest:rag-and-bone-man-ii",
             dst=None, cond_group=G_RAGII_AND),
    ]


def build_store() -> InMemoryKGStore:
    """Assemble the hand-authored store from the three lists/dicts above."""
    return InMemoryKGStore(
        nodes=build_nodes(),
        edges=build_edges(),
        groups=build_groups(),
    )


# ---------------------------------------------------------------------------
# Sample account states
# ---------------------------------------------------------------------------
def fresh_main() -> AccountState:
    """A brand-new NORMAL account: combat level 3, nothing trained, nothing done."""
    return AccountState(mode="normal")


def iron_75atk_60str_novoid() -> AccountState:
    """The kg-schema flagship counter-example: ironman, 75 Atk / 60 Str, no Void.
    OR( AND(75>=70=T, 60>=70=F)=F, gear_loadout:void=F ) -> FALSE."""
    return AccountState(
        mode="ironman",
        levels={"skill:attack": 75, "skill:strength": 60},
        # observable_families lets the absent void items read as a real FALSE (owned-count 0),
        # not UNKNOWN, so this counter-example evaluates deterministically.
        observable_families={"skill_level", "item", "quest", "achievement_diary"},
    )


def main_70atk_70str() -> AccountState:
    """A NORMAL account that satisfies the stats branch (70/70) of the flagship OR."""
    return AccountState(
        mode="normal",
        levels={"skill:attack": 70, "skill:strength": 70},
        observable_families={"skill_level", "item", "quest", "achievement_diary"},
    )


def main_full_void() -> AccountState:
    """A NORMAL account that owns full Void (melee helm + top + robe + gloves),
    but has only 60/60 Attack/Strength. The gear_loadout branch alone satisfies the OR."""
    return AccountState(
        mode="normal",
        levels={"skill:attack": 60, "skill:strength": 60},
        counts={
            "item:11665": 1,  # Void melee helm (one helm suffices for OR)
            "item:8839": 1,   # Void knight top
            "item:8840": 1,   # Void knight robe
            "item:8842": 1,   # Void knight gloves
        },
        observable_families={"skill_level", "item", "quest", "achievement_diary"},
    )


# ---------------------------------------------------------------------------
# pytest fixtures (thin wrappers; the build_* functions are importable directly)
# ---------------------------------------------------------------------------
@pytest.fixture
def kg() -> InMemoryKGStore:
    """The shared hand-authored KG store."""
    return build_store()


@pytest.fixture
def states() -> dict[str, AccountState]:
    """Named sample account states for engine tests."""
    return {
        "fresh_main": fresh_main(),
        "iron_75atk_60str_novoid": iron_75atk_60str_novoid(),
        "main_70atk_70str": main_70atk_70str(),
        "main_full_void": main_full_void(),
    }
