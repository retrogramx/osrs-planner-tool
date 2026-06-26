"""build_equipment_bonuses — reified combat-stat facet nodes + has_bonuses edges (slice 5).

Reads data/items_equipment.json. The dataset carries MULTIPLE records per item_id
(stat-variants + (beta)-page duplicates), so select_bonus_record picks the canonical
one (page == item_dictionary page, dropping beta; preferring stat_variant_index 0).
Bounded to items already in the graph (owned_item_ids) — no auto-import. has_bonuses
is ITEM-src; assemble re-keys it TOGETHER with same_entity/degrades_to/repairs.
"""
from __future__ import annotations

from collections import defaultdict

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, item_id

_EDGE_BAND = 0xD0000000  # equipment-bonuses builder-local edge ids (rekeyed in assemble)
_WEAPON_SLOTS = {"weapon", "2h"}


def _is_beta(page: str | None) -> bool:
    return "(beta)" in (page or "").lower()


def select_bonus_record(records: list[dict], canonical_page: str | None) -> dict:
    canon = [r for r in records if r.get("page_name") == canonical_page]
    pool = canon or [r for r in records if not _is_beta(r.get("page_name"))] or records

    def rank(r):
        vi = r.get("stat_variant_index")
        if vi == 0:
            return (0, 0)
        if vi is None:
            return (1, 0)
        return (2, vi)

    return sorted(pool, key=rank)[0]


def _edge_id(src_id: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#has_bonuses")


def build_equipment_bonuses(eq_records, owned_item_ids, canonical_pages):
    by_id: dict[int, list[dict]] = defaultdict(list)
    for r in eq_records:
        if r.get("item_id") is not None:
            by_id[r["item_id"]].append(r)

    nodes: list[Node] = []
    edges: list[Edge] = []
    for iid in sorted(by_id):
        src = item_id(iid)
        if src not in owned_item_ids:
            continue
        rec = select_bonus_record(by_id[iid], canonical_pages.get(iid))
        data = {"item_id": iid, "slot": rec.get("slot"), "stats": rec["stats"]}
        if rec.get("slot") in _WEAPON_SLOTS and rec.get("weapon"):
            data["weapon"] = rec["weapon"]
        bonus_id = f"equipment_bonuses:{iid}"
        nodes.append(Node(id=bonus_id, kind=NodeKind.EQUIPMENT_BONUSES,
                          name=f"{rec['item']} (equipment bonuses)",
                          slug=f"equipment-bonuses-{iid}", data=data))
        edges.append(Edge(id=_edge_id(src), type=EdgeType.HAS_BONUSES, src=src,
                          dst=bonus_id, cond_group=None, data={}))
    return nodes, edges, {}
