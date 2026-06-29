"""build_npcs — the operator layer (shop operators).

Roster = the distinct `owner` NPCs the shop brick captured over the derived shop
roster (Storeline minus Varrock). Each operator -> an npc: node (NO role: the
operates edge + the shop's shop_type encode it relationally), located_in a skeleton
place via its {{Infobox NPC}} location, with operates edges to the shops it runs.
The npc-infobox brick is the NPC filter (no infobox -> not an npc). Operators close
the shop layer's deferred operates AND its multi-location shops (the slayer masters
operate Slayer Rewards). Edges are npc-src -> assemble re-keys them in their OWN
seeded call. Never fabricates.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, slugify
from kg_ingest.builders.storeline import match_shop
from kg_ingest.builders.world import parse_infobox_links
from kg_ingest.builders.shops import shop_roster, build_place_name_index, resolve_shop_places, _shop_slug

_EDGE_BAND = 0xF0000000        # npc-src; cosmetic — rekey replaces it


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _npc_slug(name: str) -> str:
    return "npc:" + slugify(name)


def operator_map(storeline_records, shop_infoboxes, varrock_shop_names):
    """{shop_name: [operator NPC page-names]} over the derived roster (Storeline minus Varrock),
    parsed from each shop's brick `owner` field (link TARGETS, distinct + ordered). Shops with no
    owner are omitted."""
    titles = list(shop_infoboxes)
    out: dict[str, list[str]] = {}
    for name in shop_roster(storeline_records, varrock_shop_names):
        t = match_shop(name, titles)
        owner = (shop_infoboxes.get(t) or {}).get("owner") if t else None
        if not owner:
            continue
        npcs: list[str] = []
        for raw in owner:
            for tgt in parse_infobox_links(raw):
                if tgt not in npcs:
                    npcs.append(tgt)
        if npcs:
            out[name] = npcs
    return out


def operator_roster(storeline_records, shop_infoboxes, varrock_shop_names):
    """Sorted distinct operator NPC page-names across the derived roster (the npc-fetch page list)."""
    m = operator_map(storeline_records, shop_infoboxes, varrock_shop_names)
    return sorted({npc for npcs in m.values() for npc in npcs})


def build_npcs(storeline_records, shop_infoboxes, npc_infoboxes, place_nodes,
               varrock_shop_names, varrock_npc_names):
    """Operator npcs. varrock_shop_names excludes Varrock shops from the roster (via operator_map);
    varrock_npc_names excludes the 15 hand-authored Varrock npcs (build_map owns them)."""
    nodes: list[Node] = []
    edges: list[Edge] = []                     # located_in (Task 3) + operates (Task 4) land here
    roster = operator_roster(storeline_records, shop_infoboxes, varrock_shop_names)

    claimed: dict[str, str] = {}               # slug -> first name (collision guard)
    for name in roster:
        ib = npc_infoboxes.get(name)
        if not ib or not ib.get("is_npc"):
            continue                           # owner link with no {{Infobox NPC}} (quest/item) -> not an npc
        if name in varrock_npc_names:
            continue                           # build_map owns the Varrock npcs
        nid = _npc_slug(name)
        if nid in claimed:                     # distinct names, same slug -> NEVER silently merge
            k = 2
            while f"{nid}-{k}" in claimed:
                k += 1
            print(f"[npcs] slug collision: {name!r} and {claimed[nid]!r} -> {nid}; using {nid}-{k}")
            nid = f"{nid}-{k}"
        claimed[nid] = name
        nodes.append(Node(id=nid, kind=NodeKind.NPC, name=name, slug=nid.split(":", 1)[1], data={}))

    return nodes, edges, {}
