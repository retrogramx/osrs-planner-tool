"""build_world — the comprehensive location graph (world skeleton).

Reads data/map/world.json (owner-authored geographic backbone) + the committed
wiki location-category snapshot, filters by the IN/OUT granularity rule, types each
place (coarse place_type + fine content_kind), parents it (region-category ->
name-heuristic -> FLAG), and emits place nodes + located_in + same_entity. Edges are
place-src -> assemble re-keys them in their OWN seeded call. Never fabricates.
"""
from __future__ import annotations

import re

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash

_EDGE_BAND = 0xB0000000


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s*\(.*?\)\s*$", "", s.lower()))


# priority-ordered IN type-categories -> (place_type, content_kind). First match wins.
IN_TYPE = [("Raids", "dungeon", "raid"), ("Slayer dungeons", "dungeon", "slayer dungeon"),
           ("Dungeons", "dungeon", "dungeon"), ("Caves", "dungeon", "cave"),
           ("Minigames", "point_of_interest", "minigame"), ("Guilds", "point_of_interest", "guild"),
           ("Agility courses", "point_of_interest", "agility course"), ("Hunter areas", "point_of_interest", "hunter area"),
           ("Castles", "point_of_interest", "castle"), ("Mines", "point_of_interest", "mine"),
           ("Islands", "island", "island"), ("Settlements", "settlement", "settlement")]


def classify(page_categories):
    for cat, pt, ck in IN_TYPE:
        if cat in page_categories:
            return (pt, ck)
    return None


def parent_for(title, page_categories, name_to_id):
    # (1) a backbone place whose name is among the page's region/area categories.
    # name_to_id is built deepest-wins (Task 5) so a name resolves to its deepest id;
    # sorted() makes the pick deterministic when a page sits in several region categories.
    cands = [name_to_id[_norm(c)] for c in sorted(page_categories) if _norm(c) in name_to_id]
    if cands:
        return (cands[0], False)
    # (2) name minus a type suffix -> match a backbone place
    base = re.sub(r"\b(dungeon|caves?|mine|lair|tunnels?|cellar|crypt|vault)\b.*$", "", title.lower())
    base = re.sub(r"\s*\(.*?\)\s*$", "", base).strip()
    if _norm(base) and _norm(base) in name_to_id:
        return (name_to_id[_norm(base)], False)
    # (3) unresolved -> FLAG (never guess)
    return ("place:gielinor", True)


def members_of(title, fpts, mbrs):
    if title in mbrs:
        return True
    if title in fpts:
        return False
    return None
