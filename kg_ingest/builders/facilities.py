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


def _canonical_page(value, facility_infoboxes):
    """The canonical wiki page a uses_facility value resolves to: its redirect target
    if any, else itself, with MediaWiki underscore<->space title-equivalence normalized."""
    ib = facility_infoboxes.get(value) or {}
    base = ib.get("redirect_target") or value
    return base.replace("_", " ").strip()


def build_facilities(recipe_rows, facility_infoboxes, overrides):
    """Facility taxonomy nodes (pure, deterministic, ZERO edges). Non-force values that resolve
    to the same canonical wiki page collapse into ONE node (recipe_count summed, skills unioned,
    collapsed-in raw values recorded as `aliases`); force_facility values are NEVER collapsed."""
    overrides = overrides or {}
    force_fac = {o["value"] for o in overrides.get("force_facility", [])}
    force_exc = {o["value"] for o in overrides.get("force_exclude", [])}
    ov_src = {o["value"]: o.get("source_url", "") for o in overrides.get("force_facility", [])}

    skills_by, count_by = {}, {}
    for r in recipe_rows:
        sks = [(s or "").strip() for s in _as_list(r.get("uses_skill"))]
        for f in _as_list(r.get("uses_facility")):
            f = (f or "").strip()
            if not f:
                continue
            count_by[f] = count_by.get(f, 0) + 1
            skills_by.setdefault(f, set()).update(s for s in sks if s)

    groups = {}  # group_key -> list[raw value]
    for value in facility_roster(recipe_rows):
        if value in force_exc:
            continue
        if value in force_fac:
            gk = ("force", value)                      # never collapse a forced value
        else:
            ib = facility_infoboxes.get(value) or {}
            if classify_infobox(ib.get("infoboxes", [])) != "facility":
                continue                               # npc/shop/ambiguous -> deferred
            gk = ("canon", _canonical_page(value, facility_infoboxes))
        groups.setdefault(gk, []).append(value)

    def _display(members):
        # prefer the member that is its OWN page (no redirect_target); deterministic by sort
        for m in sorted(members):
            if not (facility_infoboxes.get(m) or {}).get("redirect_target"):
                return m
        return sorted(members)[0]

    rendered = [(_display(ms), ms) for ms in groups.values()]
    nodes, claimed = [], {}
    for display, members in sorted(rendered, key=lambda t: t[0]):
        rc = sum(count_by.get(m, 0) for m in members)
        sk = sorted(set().union(*[skills_by.get(m, set()) for m in members]))
        nid = _facility_slug(display)
        if nid in claimed:
            k = 2
            while f"{nid}-{k}" in claimed:
                k += 1
            print(f"[facilities] slug collision: {display!r} and {claimed[nid]!r} -> {nid}; using {nid}-{k}")
            nid = f"{nid}-{k}"
        claimed[nid] = display
        ib = facility_infoboxes.get(display) or {}
        data = {"recipe_count": rc,
                "source_url": ib.get("source_url") or ov_src.get(display) or "",
                "source_token": f"Bucket:recipe.uses_facility={display}"}
        if sk:
            data["skills"] = sk
        aliases = sorted(m for m in members if m != display)
        if aliases:
            data["aliases"] = aliases
        nodes.append(Node(id=nid, kind=NodeKind.FACILITY, name=display,
                          slug=nid.split(":", 1)[1], data=data))
    return nodes, [], {}
