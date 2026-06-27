"""build_storeline — source-grounded shop stock (slice 7).

Reads the committed Bucket:Storeline snapshot + data/map/varrock.json and emits the
sells edges: Storeline is the stock spine for shops it covers; the owner's canonicalized
gates ride as a cond_group overlay; shops with no Storeline rows (dialogue-shops) fall
back to the owner's authored sells. Shop matching is normalize-but-town-aware. Edges are
shop-src -> assemble re-keys them in their OWN seeded call.
"""
from __future__ import annotations

import re
from collections import defaultdict

from osrs_planner.engine.kg.model import ConditionGroup, Edge, EdgeType, Op
from kg_ingest.ids import _stable_hash, item_id
from kg_ingest.builders.map_varrock import make_item_resolver, _condition_atom

_EDGE_BAND = 0xF0000000
_GROUP_BAND = 0xC0000000


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _gid(owner_id: str, slot: str) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner_id}#group#{slot}")


def _norm(s: str) -> str:
    return s.strip().rstrip(".!").strip().casefold()


def _base(s: str) -> str:
    return _norm(re.sub(r"\s*\(.*?\)\s*$", "", s))


def index_by_shop(records):
    by: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        sb = r.get("sold_by")
        if sb:
            by[sb].append(r)
    return by


def match_shop(shop_name, soldby_keys):
    if shop_name in soldby_keys:
        return shop_name
    n = _norm(shop_name)
    norm_hits = [k for k in soldby_keys if _norm(k) == n]
    if len(norm_hits) == 1:
        return norm_hits[0]
    base = _base(shop_name)
    town_hits = [k for k in soldby_keys if _base(k) == base and "(varrock)" in k.casefold()]
    if len(town_hits) == 1:
        return town_hits[0]
    return None


def _emit_owner_offer(edges, groups, sid, idx, offer, resolve, dict_by_id, prefix):
    """Emit one owner-authored sells offer (slice-6 logic). Returns the resolved item_id or None."""
    iid = resolve(offer["item_name"])
    if iid is None:
        return None  # unresolved -> reported by verify_storeline, never fabricated
    cg = None
    if offer.get("condition"):
        atom = _condition_atom(offer["condition"])
        if atom is None:
            return None  # unknown condition type -> reported/failed by verifier
        gid = _gid(sid, f"{prefix}{idx}")
        groups[gid] = ConditionGroup(id=gid, op=Op.AND, parent=None, children=[atom])
        cg = gid
    data = {"source_token": offer.get("source_token")}   # NO currency/price -> validate_cost Inv 6
    mem = dict_by_id.get(iid, {}).get("members")
    if mem is not None:
        data["members"] = mem
    if offer.get("noted"):
        data["noted"] = True
    edges.append(Edge(id=_edge_id(sid, f"{prefix}#{idx}"), type=EdgeType.SELLS,
                      src=sid, dst=item_id(iid), cond_group=cg, data=data))
    return iid


def build_storeline(storeline_records, map_data, dict_records):
    resolve = make_item_resolver(dict_records)
    dict_by_id = {r["item_id"]: r for r in dict_records}
    by_shop = index_by_shop(storeline_records)
    soldby_keys = list(by_shop)

    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    for sh in map_data["shops"]:
        sid = sh["id"]
        owner_sells = sh.get("sells", [])
        matched = match_shop(sh["name"], soldby_keys)

        if matched is None:
            # NO-STORELINE FALLBACK (dialogue-shops): emit the owner's authored sells
            for i, offer in enumerate(owner_sells):
                _emit_owner_offer(edges, groups, sid, i, offer, resolve, dict_by_id, "own")
            continue

        # COVERED SHOP: owner gates are overlay-owned; Storeline supplies the rest.
        gated = [o for o in owner_sells if o.get("condition")]
        gated_items = set()
        for i, offer in enumerate(gated):
            iid = _emit_owner_offer(edges, groups, sid, i, offer, resolve, dict_by_id, "gate")
            if iid is not None:
                gated_items.add(iid)
        for j, row in enumerate(by_shop[matched]):
            iid = resolve(row.get("sold_item", ""))
            if iid is None:
                continue                      # unresolved -> reported by verify_storeline
            if iid in gated_items:
                continue                      # ownership rule: overlay owns gated items
            data = {"source_token": "Bucket:Storeline"}   # currency stays in the snapshot, NOT the graph
            mem = dict_by_id.get(iid, {}).get("members")
            if mem is not None:
                data["members"] = mem
            edges.append(Edge(id=_edge_id(sid, f"sl#{j}"), type=EdgeType.SELLS,
                              src=sid, dst=item_id(iid), cond_group=None, data=data))

    return [], edges, groups
