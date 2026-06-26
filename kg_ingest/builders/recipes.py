"""build_recipes — emit reified recipe nodes + consumes/produces edges.

First use: item-charging recipes (data/charge_recipes.json). Pure transform;
builder-local edge ids in a disjoint band, re-keyed by assemble.rekey (owner =
the recipe node, so no cross-builder collision).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash, item_id

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
