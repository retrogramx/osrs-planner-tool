"""build_items — import item nodes from the Wiki-Bucket dictionary (slice 1).

Two-level variant model (decision 5): L1 auto intra-page variants (page node +
variant children + same_entity), L2 curated cross-page families (Task 3). Pure
transform; builder-local edge ids in a disjoint band, re-keyed by assemble.rekey.
"""
from __future__ import annotations

from collections import defaultdict

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, item_id, slugify

_EDGE_BAND = 0x50000000  # items-domain builder-local same_entity edge ids (rekeyed in assemble)


def _se_edge_id(src: str, dst: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src}#same_entity#{dst}")


def _page_id(page_name: str) -> str:
    return f"item:{slugify(page_name)}"


def _variant_node(rec: dict) -> Node:
    data = {"members": bool(rec.get("members")), "is_canonical": bool(rec.get("is_canonical"))}
    if rec.get("version_anchor"):
        data["version_anchor"] = rec["version_anchor"]
    return Node(id=item_id(rec["item_id"]), kind=NodeKind.ITEM,
                name=rec["name"], slug=str(rec["item_id"]), data=data)


def build_items(dict_records, exemplar_page_names, family_records,
                referenced_item_ids, owned_ids=frozenset()):
    by_id = {r["item_id"]: r for r in dict_records}
    by_page = defaultdict(list)
    for r in dict_records:
        by_page[r["page_name"]].append(r)

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    def emit(node: Node) -> None:
        if node.id in owned_ids:          # another builder owns it: link-don't-merge, skip
            return
        nodes.setdefault(node.id, node)

    family_member_pages = {m["page"] for fam in family_records for m in fam["members"]}
    full_pages = set(exemplar_page_names) | family_member_pages

    # --- L1: full intra-page import for exemplar + family-member pages ---
    for page in sorted(full_pages):
        recs = sorted(by_page.get(page, []), key=lambda r: r["item_id"])
        if len(recs) > 1:
            pid = _page_id(page)
            emit(Node(id=pid, kind=NodeKind.ITEM, name=page, slug=slugify(page),
                      data={"is_page": True}))
            for r in recs:
                vid = item_id(r["item_id"])
                if vid in owned_ids:
                    continue   # another builder owns this variant: skip node AND bridge
                               # (its same_entity edge would collide on the rekeyed global id)
                emit(_variant_node(r))
                edges.append(Edge(id=_se_edge_id(vid, pid), type=EdgeType.SAME_ENTITY,
                                  src=vid, dst=pid, cond_group=None,
                                  data={"basis": f"shares wiki page '{page}'"}))
        elif len(recs) == 1:
            emit(_variant_node(recs[0]))   # single-variant page: no page node / no bridge

    # --- L1: referenced single items not already covered/owned ---
    for ref in sorted(referenced_item_ids):
        num = int(ref.split(":")[1])
        if num in by_id:
            emit(_variant_node(by_id[num]))

    # --- L2: cross-page families (curated) ---
    for fam in sorted(family_records, key=lambda f: f["slug"]):
        fam_id = f"item:{fam['slug']}"
        emit(Node(id=fam_id, kind=NodeKind.ITEM, name=fam["family_name"],
                  slug=fam["slug"], data={"is_family": True}))
        for m in fam["members"]:
            recs = by_page.get(m["page"], [])
            if len(recs) > 1:
                anchor = _page_id(m["page"])
            elif len(recs) == 1:
                anchor = item_id(recs[0]["item_id"])
                if anchor in owned_ids:
                    continue   # single-variant anchor owned by another builder: skip bridge
                               # (its rekeyed global edge id would collide)
            else:
                continue   # member page absent from dict; verify_item_families.py (Task 4) gates this
            edges.append(Edge(id=_se_edge_id(anchor, fam_id), type=EdgeType.SAME_ENTITY,
                              src=anchor, dst=fam_id, cond_group=None,
                              data={"basis": m["basis"]}))

    return list(nodes.values()), edges, {}
