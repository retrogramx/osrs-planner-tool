"""build_map — the connective Varrock vertical (slice 6).

Reads data/map/varrock.json (owner-authored) and emits the containment spine:
place/npc(operators)/shop nodes + located_in/operates/same_entity edges.
Sells edges and their conditional gates (reusing QUEST/ACHIEVEMENT_DIARY atoms)
are now emitted by build_storeline (slice 7). These edges are place/npc/shop-src
(NOT item-src) -> assemble re-keys them in their own call.
"""
from __future__ import annotations

from collections import defaultdict

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, item_id, slugify

_EDGE_BAND = 0xE0000000
_GROUP_BAND = 0xD0000000


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _gid(owner_id: str, slot: str) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner_id}#group#{slot}")


def make_item_resolver(dict_records):
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in dict_records:
        for key in {r.get("name"), r.get("page_name")} - {None}:
            by_name[key].append(r)

    def resolve(name: str):
        def _lookup(n):
            cands = by_name.get(n) or []
            if not cands:
                return None
            canon = [r for r in cands if r.get("is_canonical")] or cands
            ids = {r["item_id"] for r in canon}
            if len(ids) == 1:
                return next(iter(ids))
            # multiple canonical ids: prefer the record whose page_name is the bare name
            # (no parenthetical qualifier) -> Beer page "Beer" not "Beer (Player-owned house)"
            exact = {r["item_id"] for r in canon if r.get("page_name") == n}
            if len(exact) == 1:
                return next(iter(exact))
            return None  # still ambiguous -> None (reported as a residual)
        hit = _lookup(name)
        if hit is None and name.endswith(" (noted)"):
            hit = _lookup(name[: -len(" (noted)")])  # noted items share the base item_id
        return hit

    return resolve


def _diary_ref_to_id(ref: str) -> str:
    region_part, tier = ref.rsplit(" - ", 1) if " - " in ref else (ref, "Easy")
    region = slugify(region_part.replace(" Diary", "").strip())
    return f"diary:{region}:{tier.strip().lower()}"


def _condition_atom(cond: dict):
    t, ref, state = cond.get("type"), cond.get("ref"), cond.get("state")
    if t == "quest":
        return ConditionAtom(atom_type=AtomType.QUEST, ref_node=f"quest:{slugify(ref)}", data={"state": state})
    if t == "achievement_diary":
        return ConditionAtom(atom_type=AtomType.ACHIEVEMENT_DIARY, ref_node=_diary_ref_to_id(ref), data={"state": state})
    return None  # unknown type -> caller skips + verifier flags


def _slug(node_id: str) -> str:
    return node_id.split(":", 1)[1]


def build_map(map_data, resolve, region_ids):
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    # places (the containment hierarchy) + same_entity bridge to a legacy region node
    for p in map_data["places"]:
        data = {k: p[k] for k in ("place_type", "ruled_by", "faction") if p.get(k) is not None}
        nodes.append(Node(id=p["id"], kind=NodeKind.PLACE, name=p["name"], slug=_slug(p["id"]), data=data))
        if p.get("located_in"):
            edges.append(Edge(id=_edge_id(p["id"], "located_in"), type=EdgeType.LOCATED_IN,
                              src=p["id"], dst=p["located_in"], cond_group=None, data={}))
        region = f"region:{_slug(p['id'])}"
        if region in region_ids:
            edges.append(Edge(id=_edge_id(p["id"], "same_entity"), type=EdgeType.SAME_ENTITY,
                              src=p["id"], dst=region, cond_group=None, data={}))

    # npcs: only the shop operators
    npc_by_id = {n["id"]: n for n in map_data["npcs"]}
    for nid in sorted({sh["operator"] for sh in map_data["shops"] if sh.get("operator")}):
        n = npc_by_id[nid]
        nodes.append(Node(id=nid, kind=NodeKind.NPC, name=n["name"], slug=_slug(nid),
                          data={"role": n.get("role")}))
        if n.get("located_in"):
            edges.append(Edge(id=_edge_id(nid, "located_in"), type=EdgeType.LOCATED_IN,
                              src=nid, dst=n["located_in"], cond_group=None, data={}))
        for shid in n.get("operates", []):
            edges.append(Edge(id=_edge_id(nid, f"operates#{shid}"), type=EdgeType.OPERATES,
                              src=nid, dst=shid, cond_group=None, data={}))

    # shops (containment only; sells now come from build_storeline — slice 7)
    for sh in map_data["shops"]:
        nodes.append(Node(id=sh["id"], kind=NodeKind.SHOP, name=sh["name"], slug=_slug(sh["id"]),
                          data={"operator": sh.get("operator"), "shop_type": sh.get("shop_type")}))
        if sh.get("located_in"):
            edges.append(Edge(id=_edge_id(sh["id"], "located_in"), type=EdgeType.LOCATED_IN,
                              src=sh["id"], dst=sh["located_in"], cond_group=None, data={}))

    return nodes, edges, groups
