"""build_recipes — emit reified recipe nodes + consumes/produces edges.

First use: item-charging recipes (data/charge_recipes.json). Pure transform;
builder-local edge ids in a disjoint band, re-keyed by assemble.rekey (owner =
the recipe node, so no cross-builder collision).
"""
from __future__ import annotations

import html, json
from collections import Counter

from osrs_planner.engine.kg.model import AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op
from kg_ingest.ids import _stable_hash, item_id, slugify, skill_id, group_id, edge_id
from kg_ingest.builders.map_varrock import make_item_resolver

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


# ---------------------------------------------------------------------------
# build_recipe_roster — Bucket:recipe production roster (core skills)
# ---------------------------------------------------------------------------

CORE_SKILLS = {"Smithing", "Cooking", "Crafting", "Fletching", "Runecraft", "Herblore"}


def _as_list(v):
    return v if isinstance(v, list) else ([] if v in (None, "") else [v])


def _num(v):
    """Parse a quantity/xp/level string -> int (or float if fractional); None if non-numeric."""
    try:
        f = float(str(v))
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def _facility_lookup(facility_nodes):
    """name / alias -> facility node id, from the committed facility roster."""
    lut: dict[str, str] = {}
    for n in facility_nodes:
        lut.setdefault(n.name, n.id)
        for a in (n.data or {}).get("aliases", []):
            lut.setdefault(a, n.id)
    return lut


def build_recipe_roster(recipe_rows, item_dict_records, facility_nodes, existing_recipe_slugs):
    """Bucket:recipe roster for the core production skills. Reified recipe: nodes +
    consumes(material/tool)/produces/requires_facility/requires(skill_level) edges.
    Item names resolve to ids (html-unescaped); unresolvable -> skipped + disclosed.
    Pure, deterministic; coexists additively with the charge recipes."""
    resolve = make_item_resolver(item_dict_records)

    def resolve_item(name):
        iid = resolve(html.unescape((name or "").strip()))
        return f"item:{iid}" if iid is not None else None

    fac_lut = _facility_lookup(facility_nodes)

    core = []
    for r in recipe_rows:
        if not ({s for s in _as_list(r.get("uses_skill")) if s} & CORE_SKILLS):
            continue
        try:
            pj = json.loads(r.get("production_json") or "{}")
        except Exception:
            pj = {}
        out = pj.get("output")
        if not (isinstance(out, dict) and out.get("name")):
            continue  # output-less XP activity -> deferred (slice 1)
        core.append((r, pj, out))
    page_rows = Counter(r.get("page_name") for r, _, _ in core)

    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}
    claimed = {s: s for s in existing_recipe_slugs}  # reserve charge-recipe slugs
    for r, pj, out in core:
        out_dst = resolve_item(out["name"])
        if out_dst is None:
            continue  # unresolvable OUTPUT -> skip whole recipe (disclosed by coverage)
        out_name = html.unescape(out["name"].strip())
        subtxt = (out.get("subtxt") or "").strip()
        multi = page_rows[r.get("page_name")] > 1
        slug = f"{slugify(out_name)}-{slugify(subtxt)}" if (multi and subtxt) else slugify(out_name)
        if slug in claimed:
            k = 2
            while f"{slug}-{k}" in claimed:
                k += 1
            slug = f"{slug}-{k}"
        claimed[slug] = slug
        rid = f"recipe:{slug}"

        xp = {}
        for s in (pj.get("skills") or []):
            nm, ev = (s.get("name") or "").strip(), _num(s.get("experience"))
            if nm and ev is not None:
                xp[nm] = ev
        page = r.get("page_name") or ""
        token = f"Bucket:recipe page={page} output={out_name}" + (f" method={subtxt}" if (multi and subtxt) else "")
        data = {"source_url": "https://oldschool.runescape.wiki/w/" + page.replace(" ", "_"),
                "source_token": token}
        if xp:
            data["xp"] = xp
        t = _num(pj.get("ticks"))
        if t is not None:
            data["ticks"] = t
        if isinstance(pj.get("members"), bool):
            data["members"] = pj["members"]
        nodes.append(Node(id=rid, kind=NodeKind.RECIPE, name=out_name, slug=slug, data=data))

        slot = 0
        for m in (pj.get("materials") or []):
            dst = resolve_item(m.get("name"))
            if dst is None:
                continue  # unresolvable material -> skip edge (disclosed)
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.CONSUMES, src=rid, dst=dst,
                              cond_group=None, data={"qty": _num(m.get("quantity")) or 1, "role": "material"}))
            slot += 1
        for tname in _as_list(r.get("uses_tool")):
            dst = resolve_item(tname)
            if dst is None:
                continue  # unresolvable tool -> skip edge (disclosed)
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.CONSUMES, src=rid, dst=dst,
                              cond_group=None, data={"qty": 1, "role": "tool"}))
            slot += 1
        edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.PRODUCES, src=rid, dst=out_dst,
                          cond_group=None, data={"qty": _num(out.get("quantity")) or 1}))
        slot += 1
        for fname in _as_list(r.get("uses_facility")):
            fid = fac_lut.get((fname or "").strip())
            if fid is None:
                continue  # unresolved facility -> no requires_facility edge (disclosed)
            edges.append(Edge(id=_edge_id(rid, slot), type=EdgeType.REQUIRES_FACILITY, src=rid, dst=fid,
                              cond_group=None, data={}))
            slot += 1
        atoms = []
        for s in (pj.get("skills") or []):
            nm, lvl = (s.get("name") or "").strip(), _num(s.get("level"))
            if nm and lvl is not None and float(lvl) == int(lvl):
                atoms.append(ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id(nm),
                                           threshold=int(lvl),
                                           data={"boostable": str(s.get("boostable", "")).strip().lower() == "yes"}))
        if atoms:
            gid = group_id(rid, 0)
            groups[gid] = ConditionGroup(id=gid, op=Op.AND, parent=None, children=atoms)
            edges.append(Edge(id=edge_id(rid), type=EdgeType.REQUIRES, src=rid, dst=None, cond_group=gid))
    return nodes, edges, groups
