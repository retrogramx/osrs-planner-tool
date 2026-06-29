"""build_shops — the all-shops layer (every Bucket:Storeline shop).

Roster = Storeline sold_by minus the Varrock-owned shops (build_map owns those).
Each shop -> a shop: node (shop_type from the type-category, members from the
infobox), parented located_in a skeleton place via its infobox location (Task 3),
with item-only sells from Storeline (Task 4). Operators are DEFERRED to the NPC
layer. Edges are shop-src -> assemble re-keys them in their OWN seeded call.
Never fabricates: unmatched/unparented -> reported, never invented.
"""
from __future__ import annotations

import re

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, slugify
from kg_ingest.builders.storeline import match_shop, index_by_shop

_EDGE_BAND = 0xF0000000        # shop-src family (shared with build_storeline); cosmetic — rekey replaces it


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _shop_slug(name: str) -> str:
    return "shop:" + slugify(name)


def shop_roster(storeline_records, varrock_shop_names):
    """Distinct Storeline sold_by, minus the Varrock-owned shops (matched town-aware so
    'Zaff's Superior Staffs' owns 'Zaff's Superior Staffs!'). Sorted -> deterministic."""
    soldby = sorted({r["sold_by"] for r in storeline_records if r.get("sold_by")})
    owned = {match_shop(name, soldby) for name in varrock_shop_names}
    owned.discard(None)
    return [s for s in soldby if s not in owned]


def shop_type_for(icon):
    """Derive the shop type from the infobox icon (the in-game map-icon legend IS the type taxonomy):
    '[[File:Archery shop icon.png]]' -> 'Archery shop'. The fine 'X shops' categories don't exist as wiki
    categories, so the icon is the structured source. None if absent/unparseable (never fabricated)."""
    m = re.search(r"File:\s*(.+?)\s+icon\.png", icon or "", re.IGNORECASE)
    return m.group(1).strip() if m else None


def _members(infobox):
    v = (infobox or {}).get("members")
    if v is None:
        return None
    return {"yes": True, "no": False}.get(v.strip().lower())


def build_shops(storeline_records, shop_infoboxes, place_nodes, dict_records, varrock_shop_names):
    nodes: list[Node] = []
    edges: list[Edge] = []                     # located_in (Task 3) + sells (Task 4) land here
    by_shop = index_by_shop(storeline_records)
    infobox_titles = list(shop_infoboxes)

    claimed: dict[str, str] = {}               # slug -> first sold_by (collision guard)
    for name in shop_roster(storeline_records, varrock_shop_names):
        sid = _shop_slug(name)
        if sid in claimed:                     # distinct names, same slug -> NEVER silently merge
            n = 2
            while f"{sid}-{n}" in claimed:
                n += 1
            print(f"[shops] slug collision: {name!r} and {claimed[sid]!r} -> {sid}; using {sid}-{n}")
            sid = f"{sid}-{n}"
        claimed[sid] = name

        ib_title = match_shop(name, infobox_titles)
        ib = shop_infoboxes.get(ib_title) if ib_title else None
        data: dict = {}
        st = shop_type_for((ib or {}).get("icon"))
        if st:
            data["shop_type"] = st
        m = _members(ib)
        if m is not None:
            data["members"] = m
        nodes.append(Node(id=sid, kind=NodeKind.SHOP, name=name, slug=sid.split(":", 1)[1], data=data))

    return nodes, edges, {}
