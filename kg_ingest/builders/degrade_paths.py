"""build_degrade_paths — emit degrades_to downgrade-ladder edges (slice 3).

Per family: a degrades_to edge between each consecutive `sequence` item, then a
terminal edge from the last sequence item (dst=None=destroyed, else dst=the
uncharged/broken terminal_item). Emits NO nodes — every endpoint is a slice-1
node or auto-imported by build_items. degrades_to is ITEM-src; assemble re-keys
these TOGETHER with build_items' same_entity edges (shared per-owner index).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType
from kg_ingest.ids import _stable_hash, item_id

_EDGE_BAND = 0xA0000000  # degrade-paths builder-local edge ids (rekeyed in assemble)


def _edge_id(src_id: str) -> int:
    # one outgoing degrades_to per variant, so a single per-src slot suffices
    return _EDGE_BAND | _stable_hash(f"{src_id}#degrades_to")


def build_degrade_paths(records):
    nodes: list = []
    edges: list[Edge] = []
    for rec in records:
        seq = rec["sequence"]
        trigger = rec["trigger"]
        for i in range(len(seq) - 1):
            src = item_id(seq[i])
            edges.append(Edge(id=_edge_id(src), type=EdgeType.DEGRADES_TO, src=src,
                              dst=item_id(seq[i + 1]), cond_group=None, data={"trigger": trigger}))
        last = item_id(seq[-1])
        terminal = rec["terminal"]
        dst = None if terminal == "destroyed" else item_id(rec["terminal_item"])
        edges.append(Edge(id=_edge_id(last), type=EdgeType.DEGRADES_TO, src=last, dst=dst,
                          cond_group=None, data={"trigger": trigger, "terminal": terminal}))
    return nodes, edges, {}
