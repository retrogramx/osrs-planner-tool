# kg_ingest/builders/farming.py
"""build_farming_patches — the farming-patch roster (objects/resources slice 2).

One node per (patch_type x place). Each parsed row's TRAILING [[Place]] link is resolved
to a committed place: node (place_overrides > _norm name-index; else FLAG, no edge). Rows
sharing (patch_type, place) COLLAPSE in the builder to one byte-identical Node + one
located_in edge (dedup_nodes raises on same-id-different-content, so we must). The group
winner PREFERS a row with a non-empty gardener (a gardener'd source out-ranks a
gardener-less one for the same instance — e.g. the coral page vs the Special-patches
umbrella table), then falls back to the deterministic (location_raw, source_url,
row_index) sort so the pick is still order-independent. The group's place_id is a
property of the GROUP, not the display winner: it is ANY resolved place_id among the
group's rows, carried forward independent of which row wins the sort (never silently
dropped because the winner happens to be unresolved). id is injective by a fail-fast;
NO order-dependent -k fallback (spec D7). Never fabricates.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, slugify
from kg_ingest.builders.world import _norm

_EDGE_BAND = 0xE8000000        # farming-src family; cosmetic — assemble.rekey replaces it

# Display names for the closed patch_type vocab (spec D8). Special crops fall back to Title-case.
_TYPE_NAME = {
    "herb": "Herb", "allotment": "Allotment", "flower": "Flower", "bush": "Bush",
    "hops": "Hops", "tree": "Tree", "fruit_tree": "Fruit tree", "spirit_tree": "Spirit tree",
    "coral": "Coral",
}


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _name_index(place_nodes):
    """_norm(place name) -> place id over the committed place graph (shops.py pattern)."""
    idx: dict[str, str] = {}
    for n in sorted(place_nodes, key=lambda n: n.id):
        if n.id.startswith("place:"):
            idx.setdefault(_norm(n.name), n.id)
    return idx


def resolve_place(place_link, name_index, place_overrides):
    """place_override (by link text) > _norm name-index. None -> FLAG (caller emits no edge)."""
    if place_link is None:
        return None
    for o in place_overrides or []:
        if o["location"] == place_link:
            return o["place_id"]
    return name_index.get(_norm(place_link))


def _type_name(pt: str) -> str:
    return _TYPE_NAME.get(pt) or pt.replace("_", " ").capitalize()


def build_farming_patches(patch_rows, place_nodes, overrides):
    overrides = overrides or {}
    place_overrides = overrides.get("place_overrides", [])
    name_index = _name_index(place_nodes)

    # group rows by (patch_type, place_component). place_component = resolved place slug, else
    # slugify(place_link) for a FLAG. Each group -> ONE node (deterministic pick), one edge if resolved.
    groups: dict[tuple, dict] = {}
    for r in patch_rows:
        pt = r["patch_type"]
        pid = resolve_place(r.get("place_link"), name_index, place_overrides)
        place_comp = pid.split(":", 1)[1] if pid else slugify(r.get("place_link") or "unknown")
        key = (pt, place_comp)
        gardeners = r.get("gardeners") or []
        cand = {
            "patch_type": pt, "place_id": pid, "place_comp": place_comp,
            "gardener": " or ".join(gardeners) or None,
            "source_url": r.get("source_url", ""),
            "source_token": r.get("location_raw", ""),
            # gardener'd rows win ties first (REVISION); then deterministic + order-independent.
            "sort": (0 if gardeners else 1, r.get("location_raw", ""), r.get("source_url", ""),
                     r.get("row_index", 0)),
        }
        prev = groups.get(key)
        # resolved place_id is a property of the GROUP, not the display winner: carry forward
        # whichever of {cand, prev} is resolved BEFORE picking the winner by sort, so a losing
        # row's resolved place_id is never silently dropped just because it didn't win the sort.
        resolved_pid = cand["place_id"] or (prev["place_id"] if prev is not None else None)
        if prev is None or cand["sort"] < prev["sort"]:
            cand["place_id"] = resolved_pid
            groups[key] = cand
        else:
            prev["place_id"] = resolved_pid

    nodes: list[Node] = []
    edges: list[Edge] = []
    by_id: dict[str, tuple] = {}
    for (pt, place_comp), g in sorted(groups.items()):
        nid = _farming_slug(pt, place_comp)
        if nid in by_id and by_id[nid] != (pt, place_comp):
            raise ValueError(
                f"farming_patch id collision at {nid!r}: (patch_type,place) "
                f"{by_id[nid]} and {(pt, place_comp)} produce the same id (unrecoverable; "
                f"disambiguate via farming_overrides, never a -k fallback)")
        by_id[nid] = (pt, place_comp)
        data = {"patch_type": pt, "source_url": g["source_url"], "source_token": g["source_token"]}
        if g["gardener"]:
            data["gardener"] = g["gardener"]
        place_name = (g["place_id"] or "").split(":", 1)[-1].replace("-", " ").title() \
            if g["place_id"] else place_comp.replace("-", " ").title()
        nodes.append(Node(id=nid, kind=NodeKind.FARMING_PATCH,
                          name=f"{_type_name(pt)} patch ({place_name})",
                          slug=nid.split(":", 1)[1], data=data))
        if g["place_id"]:
            edges.append(Edge(id=_edge_id(nid, "located_in"), type=EdgeType.LOCATED_IN,
                              src=nid, dst=g["place_id"], cond_group=None, data={}))
        # place_id None -> unparented FLAG (no edge), reported by verify_farming_coverage
    return nodes, edges, {}


def _farming_slug(patch_type: str, place_component: str) -> str:
    return f"farming_patch:{slugify(patch_type)}-{place_component}"
