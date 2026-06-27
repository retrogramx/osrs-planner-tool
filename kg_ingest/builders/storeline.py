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

from osrs_planner.engine.kg.model import ConditionGroup, Edge, EdgeType, Node, Op
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
