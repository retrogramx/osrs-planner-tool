"""build_shops — the all-shops layer (every Bucket:Storeline shop).

Roster = Storeline sold_by minus the Varrock-owned shops (build_map owns those).
Each shop -> a shop: node (shop_type from the type-category, members from the
infobox), parented located_in a skeleton place via its infobox location (Task 3),
with item-only sells from Storeline (Task 4). Operators are DEFERRED to the NPC
layer. assemble assigns SEQUENTIAL global ids to shop edges (the builder-local ids
below are deterministic placeholders, overwritten in assemble); rekey() is NOT used
for shop edges because stable_edge_id's SPAN=2M birthday-collides at ~6k edges.
Never fabricates: unmatched/unparented -> reported, never invented.
"""
from __future__ import annotations

import re

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, slugify, item_id
from kg_ingest.builders.map_varrock import make_item_resolver
from kg_ingest.builders.storeline import match_shop, index_by_shop
from kg_ingest.builders.world import parse_infobox_links, _norm

_EDGE_BAND = 0xF0000000        # shop-src family (shared with build_storeline); cosmetic — assemble's sequential overwrite replaces it


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _shop_slug(name: str) -> str:
    return "shop:" + slugify(name)


def build_place_name_index(place_nodes):
    """Map _norm(place name) -> place id over the committed place graph. setdefault +
    sorted-by-id -> deterministic first-wins on a name collision."""
    idx: dict[str, str] = {}
    for n in sorted(place_nodes, key=lambda n: n.id):
        if n.id.startswith("place:"):
            idx.setdefault(_norm(n.name), n.id)
    return idx


def resolve_shop_places(locations, name_index):
    """Parse each infobox location value -> wikilink targets -> place ids, distinct + ordered.
    A link that doesn't resolve to a place is dropped (reported as unparented, never guessed)."""
    out: list[str] = []
    for raw in locations:
        for target in parse_infobox_links(raw):
            pid = name_index.get(_norm(target))
            if pid and pid not in out:
                out.append(pid)
    return out


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
    # by_shop + Edge/EdgeType: consumed by Task 3 (located_in) and Task 4 (sells) — not dead code
    by_shop = index_by_shop(storeline_records)
    infobox_titles = list(shop_infoboxes)
    name_index = build_place_name_index(place_nodes)

    resolve = make_item_resolver(dict_records)
    dict_by_id = {r["item_id"]: r for r in dict_records}

    claimed: dict[str, str] = {}               # slug -> first sold_by (collision guard)
    for name in shop_roster(storeline_records, varrock_shop_names):
        sid = _shop_slug(name)
        # sid here is the ORIGINAL base slug; on collision the while-loop finds the next free
        # f"{sid}-{n}" id (deterministic; terminates because the roster is finite).
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
        places = resolve_shop_places((ib or {}).get("locations", []), name_index)
        if len(places) > 1:
            data["multi_location"] = True                    # deferred to the NPC layer (no arbitrary primary)
        nodes.append(Node(id=sid, kind=NodeKind.SHOP, name=name, slug=sid.split(":", 1)[1], data=data))
        if len(places) == 1:
            edges.append(Edge(id=_edge_id(sid, "located_in"), type=EdgeType.LOCATED_IN,
                              src=sid, dst=places[0], cond_group=None, data={}))
        # len(places) == 0 -> unparented FLAG (no edge), reported by verify_shop_coverage

        for j, row in enumerate(by_shop.get(name, [])):
            iid = resolve(row.get("sold_item", ""))
            if iid is None:
                continue                                     # unresolved -> reported by verify_shops
            edata = {"source_token": "Bucket:Storeline"}     # NO currency/price -> validate_cost Inv 6
            mem = dict_by_id.get(iid, {}).get("members")
            if mem is not None:
                edata["members"] = mem
            edges.append(Edge(id=_edge_id(sid, f"sl#{j}"), type=EdgeType.SELLS,
                              src=sid, dst=item_id(iid), cond_group=None, data=edata))

    return nodes, edges, {}
