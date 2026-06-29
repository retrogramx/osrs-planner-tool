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
