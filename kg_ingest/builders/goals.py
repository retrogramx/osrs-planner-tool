"""Builder for the v1 goal set (spec §3, decision K8).

build_goals() emits goal NODES + their requires EDGES + AND condition GROUPS for
the wiki-verified v1 goals. Part 1 (Task 5) = the first three; Task 6 appends
Barrows gloves, full Infinity, Voidwaker to the SAME function.

Each goal = one Node + one REQUIRES edge (dst=None: "the constraint IS the tree",
§6.2) whose cond_group is an AND of the locked atoms (K3/§6.1):
  item possession  -> AtomType.ITEM (qty>=1),
  wield skill gate -> AtomType.SKILL_LEVEL (threshold, data.boostable),
  quest gate       -> AtomType.QUEST (data.state from the chain stage).

B2 two-node pattern: a "wield item X" goal is modelled as a SEPARATE
gear_loadout:<slug> node whose ITEM atom references the item:<id> LEAF (created by
build_supporting), NOT as the item node owning an atom about itself. That avoids a
self-loop in store.requires_dag() (owner == ref_node) that find_cycles() would flag
as UNSATISFIABLE_CYCLE — and that Task 8's acyclicity check is meant to CATCH.
Mirrors gear_loadout:void referencing its piece items in the engine fixture.

IDs (K9): item:<item_id>, access:<slug>, gear_loadout:<slug>. Group/edge ints are
builder-local DETERMINISTIC via _group_id/_edge_id(owner_id, slot) — implemented
using _stable_hash from kg_ingest/ids.py (single source of truth; no duplication);
assemble.py re-keys to global ids. Atoms reference quest/skill nodes by quest:<slug>
/ skill:<slug> (slug = lowercased name, spaces and '/' collapsed to single hyphens,
other punctuation removed; e.g. Monkey Madness I -> quest:monkey-madness-i).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import (
    _stable_hash, access_id, gear_loadout_id, item_id, quest_id, skill_id, slugify,
)

# Goal-domain id bands, disjoint from the quest bands in kg_ingest/ids.py
# (0x10000000 group / 0x20000000 edge). assemble.py re-keys to global ids anyway.
_GROUP_BAND = 0x30000000
_EDGE_BAND = 0x40000000


def _group_id(owner_id: str, slot: int) -> int:
    """Deterministic builder-local condition_group id for owner_id's slot-th group."""
    return _GROUP_BAND | _stable_hash(f"{owner_id}#group#{slot}")


def _edge_id(owner_id: str, slot: int) -> int:
    """Deterministic builder-local requires-edge id for owner_id's slot-th edge."""
    return _EDGE_BAND | _stable_hash(f"{owner_id}#edge#{slot}")


def _add_goal(
    node_id: str,
    kind: NodeKind,
    name: str,
    slug: str,
    atoms: list[ConditionAtom],
    nodes: list[Node],
    edges: list[Edge],
    groups: dict[int, ConditionGroup],
    node_data: dict | None = None,
) -> None:
    """Append one goal node + its AND requires edge + cond_group (the common shape).

    Covers every goal that maps cleanly to: ONE node + ONE dst=None REQUIRES edge
    whose cond_group is an AND of the given atoms (K3/§6.2).  Infinity's two-node
    pattern (B2/B3) wires two calls to this helper — one for the loadout, one for
    the wield-gate goal — with the loadout call passing ITEM atoms and the goal call
    passing a GEAR_LOADOUT atom referencing the loadout node.

    Group/edge ids use slot 0 (each node has exactly one requires edge here; B3).
    """
    gid = _group_id(node_id, 0)
    eid = _edge_id(node_id, 0)
    nodes.append(Node(id=node_id, kind=kind, name=name, slug=slug,
                      data=node_data or {}))
    groups[gid] = ConditionGroup(id=gid, op=Op.AND, parent=None, children=list(atoms))
    edges.append(Edge(id=eid, type=EdgeType.REQUIRES,
                      src=node_id, dst=None, cond_group=gid))


def build_goals() -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    # --- Goal 1: Dragon scimitar (gear_loadout:dragon-scimitar) ---
    # B2 two-node pattern: the GOAL node is distinct from the ITEM node it gates on.
    # The ITEM atom references item:4587 — a LEAF created by build_supporting in the
    # full pipeline (mirrors gear_loadout:void referencing its piece items) — so the
    # goal never references itself: no self-loop in requires_dag(), no spurious cycle.
    # M2: ids minted via the locked helpers (gear_loadout_id/item_id/skill_id/quest_id)
    # so slugs are never hand-duplicated; the helper output IS the ref_node string.
    _add_goal(
        node_id=gear_loadout_id("Dragon scimitar"),
        kind=NodeKind.GEAR_LOADOUT,
        name="Wielding a Dragon scimitar",
        slug="dragon-scimitar",
        atoms=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=item_id(4587), qty=1),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id("Attack"),
                          threshold=60, data={"boostable": True}),
            ConditionAtom(atom_type=AtomType.QUEST, ref_node=quest_id("Monkey Madness I"),
                          data={"state": "completed"}),
        ],
        nodes=nodes, edges=edges, groups=groups,
    )

    # --- Goal 2: Fairy rings (access:fairy-rings) ---
    # The in-progress quest-gate pattern (§3): fairy-ring travel unlocks during
    # Fairytale II - Cure a Queen, so the gate is that quest IN_PROGRESS (>=).
    _add_goal(
        node_id=access_id("Fairy rings"),
        kind=NodeKind.ACCESS,
        name="Fairy rings",
        slug="fairy-rings",
        atoms=[
            ConditionAtom(atom_type=AtomType.QUEST,
                          ref_node=quest_id("Fairytale II - Cure a Queen"),
                          data={"state": "in_progress"}),
        ],
        nodes=nodes, edges=edges, groups=groups,
        node_data={"note": "fairy-ring travel network; unlocks during Fairytale II"},
    )

    # --- Goal 3: Tzhaar-ket-om / obby maul (gear_loadout:obby-maul) ---
    # B2 two-node pattern again: the goal node is distinct from item:6528, which the
    # ITEM atom references as a LEAF (built by build_supporting) — no self-loop.
    _add_goal(
        node_id=gear_loadout_id("Obby maul"),
        kind=NodeKind.GEAR_LOADOUT,
        name="Wielding a Tzhaar-ket-om",
        slug="obby-maul",
        atoms=[
            ConditionAtom(atom_type=AtomType.ITEM, ref_node=item_id(6528), qty=1),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id("Strength"),
                          threshold=60, data={"boostable": True}),
        ],
        nodes=nodes, edges=edges, groups=groups,
    )

    # ---- Barrows gloves (item:7462) — untradeable RFD reward (K8). ----
    # Convergence: requires RFD *completed*; the quest:recipe-for-disaster node is
    # created by build_quests (K2), NOT here — we only reference it (via quest_id, M2).
    #
    # B2 / no-self-loop: the requires group holds ONLY the quest atom (the exclusive
    # prerequisite for obtaining the item). We do NOT add a self-referential ITEM atom
    # referencing item:7462 here — that would create a cond_dep self-loop in the
    # requires_dag (owner == ref_node), flagged as UNSATISFIABLE_CYCLE by find_cycles.
    # Ownership is expressed by the item leaf existing as a node; the engine's is_unlocked
    # logic drives from the player's bank state, not from a self-atom.
    _add_goal(
        node_id=item_id(7462),
        kind=NodeKind.ITEM,
        name="Barrows gloves",
        slug="barrows-gloves",
        atoms=[
            ConditionAtom(atom_type=AtomType.QUEST, ref_node=quest_id("Recipe for Disaster"),
                          data={"state": "completed"}),
        ],
        nodes=nodes, edges=edges, groups=groups,
        node_data={"tradeable": False},
    )

    # ---- Full Infinity — canonical two-node Void pattern (K8; B2/B3). ----
    # Mirrors tests/engine/fixtures/kg_fixture.py (gear_loadout:void + npc:7221):
    #  (a) the LOADOUT node holds ONLY its composition (one dst=None requires edge,
    #      AND of the 5 piece item atoms) — no gear_loadout atom, no skill atoms.
    #      composition_of returns this group; one such edge => unambiguous (B3).
    #  (b) a SEPARATE goal node holds the wield gate, AND(gear_loadout atom -> the
    #      loadout node, 50 Magic, 25 Def). It references a DIFFERENT node, so there
    #      is no self-loop (B2); the gear_loadout atom re-evaluates the loadout's
    #      composition against live counts (engine D3).
    _INFINITY_PIECES = [6918, 6916, 6924, 6922, 6920]  # hat, top, bottoms, gloves, boots
    infinity_loadout = gear_loadout_id("Infinity")          # gear_loadout:infinity
    infinity_goal = f"gear_loadout_goal:{slugify('Infinity')}"  # gear_loadout_goal:infinity
    # (a) loadout node + its single composition edge.
    _add_goal(
        node_id=infinity_loadout,
        kind=NodeKind.GEAR_LOADOUT,
        name="Full Infinity",
        slug="infinity",
        atoms=[ConditionAtom(atom_type=AtomType.ITEM, ref_node=item_id(p), qty=1)
               for p in _INFINITY_PIECES],
        nodes=nodes, edges=edges, groups=groups,
    )
    # (b) separate goal node "wielding full Infinity" + its single wield-gate edge.
    _add_goal(
        node_id=infinity_goal,
        kind=NodeKind.GEAR_LOADOUT,
        name="Wielding full Infinity",
        slug="infinity-wield",
        atoms=[
            ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node=infinity_loadout),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id("Magic"),
                          threshold=50, data={"boostable": False}),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id("Defence"),
                          threshold=25, data={"boostable": False}),
        ],
        nodes=nodes, edges=edges, groups=groups,
        node_data={"loadout": infinity_loadout},
    )

    # ---- Voidwaker (item:27690) — multi-component assembly (K8/§6.2; B1). ----
    # Own the 3 components; acquiring each (drop vs GE) is the deferred cost layer.
    # The 3 COMPONENT items are NOT in data/items_equipment.json (only the assembled
    # 27690 is), so build_goals emits the component item NODES DIRECTLY here
    # (goal-supplied; ids + names wiki-verified at build). assemble.py subtracts these
    # owner ids before calling build_supporting, so the components are never looked up
    # there (which would KeyError). The assembled node requires an AND of the 3
    # component item-possession atoms.
    _VOIDWAKER_COMPONENTS = [
        (27681, "Voidwaker hilt"),
        (27684, "Voidwaker blade"),
        (27687, "Voidwaker gem"),
    ]
    # emit the 3 component item nodes directly (goal-supplied, bypass build_supporting).
    for (cid, cname) in _VOIDWAKER_COMPONENTS:
        nodes.append(Node(id=item_id(cid), kind=NodeKind.ITEM, name=cname,
                          slug=str(cid), data={}))
    _add_goal(
        node_id=item_id(27690),
        kind=NodeKind.ITEM,
        name="Voidwaker",
        slug="voidwaker",
        atoms=[ConditionAtom(atom_type=AtomType.ITEM, ref_node=item_id(cid), qty=1)
               for (cid, _name) in _VOIDWAKER_COMPONENTS],
        nodes=nodes, edges=edges, groups=groups,
        node_data={"tradeable": True},
    )

    return nodes, edges, groups
