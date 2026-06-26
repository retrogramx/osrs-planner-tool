"""build_repairs — emit repairs edges (broken -> repaired); slice 4.

The structural inverse of degrades_to's broken terminal. One repairs edge per
record, pure transition (no data). Emits NO nodes — endpoints are slice-3 nodes
or auto-imported by build_items. repairs is ITEM-src; assemble re-keys these
TOGETHER with build_items' same_entity AND degrades_to edges (shared per-owner index).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType
from kg_ingest.ids import _stable_hash, item_id

_EDGE_BAND = 0xC0000000  # repairs builder-local edge ids (rekeyed in assemble)


def _edge_id(src_id: str) -> int:
    # one outgoing repairs edge per broken item, so a single per-src slot suffices
    return _EDGE_BAND | _stable_hash(f"{src_id}#repairs")


def build_repairs(records):
    nodes = []
    edges = []
    for rec in records:
        src = item_id(rec["broken"])
        edges.append(Edge(id=_edge_id(src), type=EdgeType.REPAIRS, src=src,
                          dst=item_id(rec["repaired"]), cond_group=None, data={}))
    return nodes, edges, {}
