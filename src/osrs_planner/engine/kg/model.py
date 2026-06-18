"""KG static value types — frozen, hashable, JSON/SQL-serializable.

Mirrors the node/edge/condition tables of research/kg-schema-v1.md. These
instances are GLOBAL static game-data shared across all accounts and requests
(schema principle (c)), so every type is a frozen dataclass and every enum is
a str-subclass (its .value is the SQL TEXT column verbatim).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeKind(str, Enum):
    """node.kind closed enum (schema: type taxonomy). v1-CORE + id-reserved kinds."""
    SKILL = "skill"
    ITEM = "item"
    MONSTER = "monster"
    QUEST = "quest"
    ACCESS = "access"
    REGION = "region"
    ACCOUNT_TYPE = "account_type"
    GEAR_LOADOUT = "gear_loadout"
    ACTIVITY = "activity"
    DIARY = "diary"
    COMBAT_ACHIEVEMENT = "combat_achievement"
    MINIGAME = "minigame"
    CLOG_SLOT = "clog_slot"


class EdgeType(str, Enum):
    """The 5 FACT edge types (schema: fact edge-type table). Opinion edges
    (recommended_for / recommended_method) are out of the engine's fact spine."""
    REQUIRES = "requires"
    GRANTS = "grants"
    DROPS = "drops"
    LOCATED_IN = "located_in"
    GATED_BY = "gated_by"


class Op(str, Enum):
    """condition_group.op (schema: CHECK op IN AND/OR/NOT). NOT => exactly one child."""
    AND = "and"
    OR = "or"
    NOT = "not"


class AtomType(str, Enum):
    """condition_atom.atom_type closed enum (schema: condition_atom CHECK +
    atom-semantics list). COMBAT_ACHIEVEMENT (binary per-task) and
    COMBAT_ACHIEVEMENT_POINTS (accumulator tier total) are deliberately split."""
    SKILL_LEVEL = "skill_level"
    SKILL_XP = "skill_xp"
    COMBAT_LEVEL = "combat_level"
    QUEST = "quest"
    ACHIEVEMENT_DIARY = "achievement_diary"
    COMBAT_ACHIEVEMENT = "combat_achievement"
    ITEM = "item"
    IS_UNLOCKED = "is_unlocked"
    GEAR_LOADOUT = "gear_loadout"
    KILL_COUNT = "kill_count"
    QUEST_POINTS = "quest_points"
    ACCOUNT_TYPE = "account_type"
    CLUE_SCROLLS = "clue_scrolls"
    COMBAT_ACHIEVEMENT_POINTS = "combat_achievement_points"


@dataclass(frozen=True)
class Node:
    """A row of the `node` spine (schema: Node model). One row per game entity.
    `data` is the kind-specific JSON blob the engine does NOT hot-filter
    (e.g. account_type {'must_self_acquire','can_ge'}, diary {'region','tier'})."""
    id: str
    kind: NodeKind
    name: str
    slug: str
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConditionAtom:
    """A leaf of a condition tree (schema: condition_atom). One testable
    predicate. `data` carries non-scalar payloads per the atom-semantics list:
    quest/diary 'state' (3-state ORDERED enum), account_type 'value',
    clue_scrolls 'set_ref' (list of node ids). ref_node/threshold/qty are
    optional because ref-less atoms (quest_points, combat_level, clue_scrolls,
    combat_achievement_points) carry none of them."""
    atom_type: AtomType
    ref_node: Optional[str] = None
    threshold: Optional[int] = None
    qty: Optional[int] = None
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConditionGroup:
    """An internal node of a condition tree (schema: condition_group).
    `children` is a heterogeneous list of child-group ids (int) and/or
    ConditionAtom objects — the exact shape conditions.evaluate folds over.
    parent is None for the root. NOT => exactly one child (enforced by load-time
    QA invariant I5, not here)."""
    id: int
    op: Op
    parent: Optional[int]
    children: list


@dataclass(frozen=True)
class Edge:
    """A FACT edge (schema: edge table, fact subset). Direction: requires reads
    `src needs dst`; producer edges read `src -> produced`. `dst` is None for a
    pure-condition edge (the constraint IS the cond_group tree, e.g. the
    `(70 Att AND 70 Str) OR full-Void` requires edge and gear_loadout
    compositions). `cond_group` None => unconditional; multiple requires
    edges out of one src are implicitly AND-ed (D5: is_unlocked folds ALL
    requires edges)."""
    id: int
    type: EdgeType
    src: str
    dst: Optional[str] = None
    cond_group: Optional[int] = None
