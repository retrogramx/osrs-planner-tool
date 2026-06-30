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


def classify_infobox(infoboxes) -> str:
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
