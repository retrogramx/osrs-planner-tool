"""build_recipes — emit reified recipe nodes + consumes/produces edges.

First use: item-charging recipes (data/charge_recipes.json). Pure transform;
builder-local edge ids in a disjoint band, re-keyed by assemble.rekey (owner =
the recipe node, so no cross-builder collision).
"""
from __future__ import annotations

import html
from collections import defaultdict

from osrs_planner.engine.kg.model import AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op
from kg_ingest.ids import _stable_hash, item_id, group_id, edge_id
from kg_ingest.builders.map_varrock import make_item_resolver
from kg_ingest.recipe_identity import (
    resolve_recipe_payload, recipe_identity_hash, is_method_suffixed, _facility_lookup)

_EDGE_BAND = 0x80000000  # recipes-domain builder-local edge ids (rekeyed in assemble)


def _edge_id(recipe_id: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{recipe_id}#edge#{slot}")


def build_recipes(records):
    nodes: list[Node] = []
    edges: list[Edge] = []
    for rec in records:
        rid = f"recipe:{rec['slug']}"
        data = {"charge_yield": rec["charge_yield"], "charge_capacity": rec["charge_capacity"]}
        if rec.get("notes"):
            data["notes"] = rec["notes"]
        if rec.get("source_token"):
            data["source_token"] = rec["source_token"]
        nodes.append(Node(id=rid, kind=NodeKind.RECIPE, name=rec["name"], slug=rec["slug"], data=data))
        slot = 0
        # materials (consumes, role=material) in a deterministic order (by item_id)
        for m in sorted(rec["materials"], key=lambda x: x["item_id"]):
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.CONSUMES, src=rid,
                              dst=item_id(m["item_id"]), cond_group=None,
                              data={"qty": m["qty"], "role": "material"}))
            slot += 1
        # subject (consumes, role=subject) = the uncharged variant (transformed, not destroyed)
        sub = rec["subject"]
        edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.CONSUMES, src=rid,
                          dst=item_id(sub["item_id"]), cond_group=None,
                          data={"qty": sub["qty"], "role": "subject"}))
        slot += 1
        # produces (the charged variant)
        prod = rec["produces"]
        edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.PRODUCES, src=rid,
                          dst=item_id(prod["item_id"]), cond_group=None, data={"qty": prod["qty"]}))
        slot += 1
    return nodes, edges, {}


# ---------------------------------------------------------------------------
# build_recipe_roster — Bucket:recipe roster; ids come from the committed
# data/recipe_slug_registry.json (identity -> slug). Order/sibling-independent.
# ---------------------------------------------------------------------------


def build_recipe_roster(recipe_rows, item_dict_records, facility_nodes, registry):
    """Bucket:recipe roster. Each recipe's id is looked up in `registry`
    (identity hash -> {slugs:[...]}); an unregistered recipe FAILS the build
    (run data/update_recipe_registry.py). Reified: consumes(material/tool)/produces/
    requires_facility/requires(skill_level). Pure, deterministic; coexists with charge recipes."""
    resolve = make_item_resolver(item_dict_records)

    def resolve_item(name):
        iid = resolve(html.unescape((name or "").strip()))
        return f"item:{iid}" if iid is not None else None

    fac_lut = _facility_lookup(facility_nodes)
    reg = registry.get("recipes", {})

    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}
    seen = defaultdict(int)          # per-identity occurrence counter (emission order)
    unregistered: list[str] = []

    for r in recipe_rows:
        payload = resolve_recipe_payload(r, resolve_item, fac_lut)
        if payload is None:
            continue                 # unresolvable / absent output -> skip (disclosed by coverage)
        h = recipe_identity_hash(payload)
        entry = reg.get(h)
        idx = seen[h]
        if entry is None or idx >= len(entry["slugs"]):
            unregistered.append(f"{payload['out_name']} (page={payload['page']})")
            seen[h] += 1
            continue
        slug = entry["slugs"][idx]
        seen[h] += 1
        rid = f"recipe:{slug}"

        out_name, subtxt = payload["out_name"], payload["subtxt"]
        token = (f"Bucket:recipe page={payload['page']} output={out_name}"
                 + (f" method={subtxt}" if is_method_suffixed(slug, out_name, subtxt) else ""))
        data = {"source_url": "https://oldschool.runescape.wiki/w/" + payload["page"].replace(" ", "_"),
                "source_token": token}
        if payload["xp"]:
            data["xp"] = payload["xp"]
        if payload["ticks"] is not None:
            data["ticks"] = payload["ticks"]
        if payload["members"] is not None:
            data["members"] = payload["members"]
        nodes.append(Node(id=rid, kind=NodeKind.RECIPE, name=out_name, slug=slug, data=data))

        slot = 0
        for dst, qty, role in payload["consumes"]:
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.CONSUMES, src=rid, dst=dst,
                              cond_group=None, data={"qty": qty, "role": role}))
            slot += 1
        for dst, qty in payload["produces"]:
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.PRODUCES, src=rid, dst=dst,
                              cond_group=None, data={"qty": qty}))
            slot += 1
        for fid in payload["facilities"]:
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.REQUIRES_FACILITY, src=rid, dst=fid,
                              cond_group=None, data={}))
            slot += 1
        if payload["atoms"]:
            gid = group_id(rid, 0)
            atoms = [ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=sk, threshold=th,
                                   data={"boostable": bo}) for sk, th, bo in payload["atoms"]]
            groups[gid] = ConditionGroup(id=gid, op=Op.AND, parent=None, children=atoms)
            edges.append(Edge(id=edge_id(rid), type=EdgeType.REQUIRES, src=rid, dst=None, cond_group=gid))

    if unregistered:
        raise ValueError(
            f"{len(unregistered)} unregistered recipes — run "
            f"data/update_recipe_registry.py: {unregistered[:5]}")
    return nodes, edges, groups
