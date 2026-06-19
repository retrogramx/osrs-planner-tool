"""Builder for the v1 goal set (spec §3, decision K8).

build_goals() emits goal NODES + their requires EDGES + AND condition GROUPS for
the wiki-verified v1 goals. Part 1 (this task) = the first three; Task 6 appends
Barrows gloves, full Infinity, Voidwaker to the SAME function.

Each goal = one Node + one REQUIRES edge (dst=None: "the constraint IS the tree",
§6.2) whose cond_group is an AND of the locked atoms (K3/§6.1):
  item possession  -> AtomType.ITEM (qty>=1),
  wield skill gate -> AtomType.SKILL_LEVEL (threshold, data.boostable),
  quest gate       -> AtomType.QUEST (data.state from the chain stage).

IDs (K9): item:<item_id>, access:<slug>, gear_loadout:<slug>. Group/edge ints are
builder-local DETERMINISTIC via _group_id/_edge_id(owner_id, slot); assemble.py
re-keys to global ids. Atoms reference quest/skill nodes by quest:<slug> /
skill:<slug> (slug = lowercased name, spaces and '/' collapsed to single hyphens,
other punctuation removed; e.g. Monkey Madness I -> quest:monkey-madness-i).
"""
from __future__ import annotations

import hashlib

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import (
    access_id, gear_loadout_id, item_id, quest_id, skill_id, slugify,
)

# Goal-domain id bands, disjoint from the quest bands in kg_ingest/ids.py
# (0x10000000 group / 0x20000000 edge). assemble.py re-keys to global ids anyway.
_GROUP_BAND = 0x30000000
_EDGE_BAND = 0x40000000
_MASK = 0x0FFFFFFF


def _stable(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) & _MASK


def _group_id(owner_id: str, slot: int) -> int:
    """Deterministic builder-local condition_group id for owner_id's slot-th group."""
    return _GROUP_BAND | _stable(f"{owner_id}#group#{slot}")


def _edge_id(owner_id: str, slot: int) -> int:
    """Deterministic builder-local requires-edge id for owner_id's slot-th edge."""
    return _EDGE_BAND | _stable(f"{owner_id}#edge#{slot}")


def build_goals() -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    # --- Goal 1: Dragon scimitar (item:4587) ---
    # M2: ids minted via the locked helpers (item_id/skill_id/quest_id) so slugs
    # are never hand-duplicated; the helper output IS the ref_node string.
    scim = item_id(4587)
    g_scim = _group_id(scim, 0)
    nodes.append(Node(id=scim, kind=NodeKind.ITEM, name="Dragon scimitar",
                      slug="dragon-scimitar", data={"tradeable": True}))
    groups[g_scim] = ConditionGroup(id=g_scim, op=Op.AND, parent=None, children=[
        ConditionAtom(atom_type=AtomType.ITEM, ref_node=scim, qty=1),
        ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id("Attack"),
                      threshold=60, data={"boostable": True}),
        ConditionAtom(atom_type=AtomType.QUEST, ref_node=quest_id("Monkey Madness I"),
                      data={"state": "completed"}),
    ])
    edges.append(Edge(id=_edge_id(scim, 0), type=EdgeType.REQUIRES,
                      src=scim, dst=None, cond_group=g_scim))

    # --- Goal 2: Fairy rings (access:fairy-rings) ---
    # The in-progress quest-gate pattern (§3): fairy-ring travel unlocks during
    # Fairytale II - Cure a Queen, so the gate is that quest IN_PROGRESS (>=).
    fairy = access_id("Fairy rings")
    g_fairy = _group_id(fairy, 0)
    nodes.append(Node(id=fairy, kind=NodeKind.ACCESS, name="Fairy rings",
                      slug="fairy-rings",
                      data={"note": "fairy-ring travel network; unlocks during Fairytale II"}))
    groups[g_fairy] = ConditionGroup(id=g_fairy, op=Op.AND, parent=None, children=[
        ConditionAtom(atom_type=AtomType.QUEST,
                      ref_node=quest_id("Fairytale II - Cure a Queen"),
                      data={"state": "in_progress"}),
    ])
    edges.append(Edge(id=_edge_id(fairy, 0), type=EdgeType.REQUIRES,
                      src=fairy, dst=None, cond_group=g_fairy))

    # --- Goal 3: Tzhaar-ket-om / obby maul (item:6528) ---
    maul = item_id(6528)
    g_maul = _group_id(maul, 0)
    # Name casing MUST match data/items_equipment.json exactly ('Tzhaar-ket-om',
    # lowercase z/k) — that is the wiki/data casing the golden set asserts (M3).
    nodes.append(Node(id=maul, kind=NodeKind.ITEM, name="Tzhaar-ket-om",
                      slug="tzhaar-ket-om", data={"tradeable": True}))
    groups[g_maul] = ConditionGroup(id=g_maul, op=Op.AND, parent=None, children=[
        ConditionAtom(atom_type=AtomType.ITEM, ref_node=maul, qty=1),
        ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id("Strength"),
                      threshold=60, data={"boostable": True}),
    ])
    edges.append(Edge(id=_edge_id(maul, 0), type=EdgeType.REQUIRES,
                      src=maul, dst=None, cond_group=g_maul))

    return nodes, edges, groups
