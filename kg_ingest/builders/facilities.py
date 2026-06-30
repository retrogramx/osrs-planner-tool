# kg_ingest/builders/facilities.py
"""build_facilities — the facility taxonomy (objects/resources slice 1).

Roster = the distinct non-empty Bucket:recipe.uses_facility page names. The filter is
the wiki's own {{Infobox X}} on each value's (redirect-resolved) page: Scenery/Construction
-> facility; NPC/Shop -> defer (a character/store, not a facility); else -> ambiguous (owner
review queue). Each facility node is skill-tagged from uses_skill + provenance. Pure,
deterministic, ZERO edges. Never fabricates.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Node, NodeKind
from kg_ingest.ids import slugify

_FACILITY_INFOBOXES = {"Infobox Scenery", "Infobox Construction"}
_NPC_INFOBOXES = {"Infobox NPC"}
_SHOP_INFOBOXES = {"Infobox Shop"}


def classify_infobox(infoboxes: list[str]) -> str:
    """Classify a uses_facility page by the infobox template(s) on its page.
    NPC/Shop presence DEFERS (character/store); Scenery/Construction ADMITS; else ambiguous."""
    s = set(infoboxes or [])
    if s & _NPC_INFOBOXES:
        return "npc"
    if s & _SHOP_INFOBOXES:
        return "shop"
    if s & _FACILITY_INFOBOXES:
        return "facility"
    return "ambiguous"


def _as_list(v):
    if isinstance(v, list):
        return v
    if v in (None, ""):
        return []
    return [v]


def _facility_slug(name: str) -> str:
    return "facility:" + slugify(name)


def facility_roster(recipe_rows) -> list[str]:
    """Sorted distinct non-empty uses_facility page names across the recipe rows."""
    vals: set[str] = set()
    for r in recipe_rows:
        for f in _as_list(r.get("uses_facility")):
            f = (f or "").strip()
            if f:
                vals.add(f)
    return sorted(vals)


def build_facilities(recipe_rows, facility_infoboxes, overrides):
    """Facility taxonomy nodes (pure, deterministic, ZERO edges). See module docstring."""
    overrides = overrides or {}
    force_fac = {o["value"] for o in overrides.get("force_facility", [])}
    force_exc = {o["value"] for o in overrides.get("force_exclude", [])}
    ov_src = {o["value"]: o.get("source_url", "") for o in overrides.get("force_facility", [])}

    skills_by: dict[str, set[str]] = {}
    count_by: dict[str, int] = {}
    for r in recipe_rows:
        sks = [(s or "").strip() for s in _as_list(r.get("uses_skill"))]
        for f in _as_list(r.get("uses_facility")):
            f = (f or "").strip()
            if not f:
                continue
            count_by[f] = count_by.get(f, 0) + 1
            skills_by.setdefault(f, set()).update(s for s in sks if s)

    nodes: list[Node] = []
    claimed: dict[str, str] = {}
    for value in facility_roster(recipe_rows):
        if value in force_exc:
            continue
        if value not in force_fac:
            ib = facility_infoboxes.get(value) or {}
            if classify_infobox(ib.get("infoboxes", [])) != "facility":
                continue                       # npc/shop/ambiguous -> deferred (coverage reports)
        nid = _facility_slug(value)
        if nid in claimed:                     # distinct names, same slug -> NEVER silently merge
            k = 2
            while f"{nid}-{k}" in claimed:
                k += 1
            print(f"[facilities] slug collision: {value!r} and {claimed[nid]!r} -> {nid}; using {nid}-{k}")
            nid = f"{nid}-{k}"
        claimed[nid] = value
        ib = facility_infoboxes.get(value) or {}
        data = {"recipe_count": count_by.get(value, 0),
                "source_url": ib.get("source_url") or ov_src.get(value) or "",
                "source_token": f"Bucket:recipe.uses_facility={value}"}
        sk = sorted(skills_by.get(value, set()))
        if sk:
            data["skills"] = sk
        nodes.append(Node(id=nid, kind=NodeKind.FACILITY, name=value,
                          slug=nid.split(":", 1)[1], data=data))
    return nodes, [], {}
