"""build_supporting — emit the leaf nodes that condition atoms reference (K9).

Maps a set of referenced ref_node ids (skill:/item:/access:/minigame:/
gear_loadout:/npc:/diary:) to one correctly-typed, correctly-named engine Node
each (deduped, sorted by id). Pure transform; only external read is the committed
data/items_equipment.json (numeric item ids -> display names, memoized).
"""
from __future__ import annotations

import json
import os

from osrs_planner.engine.kg.model import Node, NodeKind

# Repo root = three levels up from kg_ingest/builders/supporting.py.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ITEMS_PATH = os.path.join(_REPO_ROOT, "data", "items_equipment.json")

# region slug -> display label; module-level so validate_kg / future builders can reuse
DIARY_REGION_LABELS: dict[str, str] = {
    "ardougne": "Ardougne", "desert": "Desert", "falador": "Falador",
    "fremennik": "Fremennik", "kandarin": "Kandarin", "karamja": "Karamja",
    "kourend": "Kourend & Kebos", "lumbridge": "Lumbridge & Draynor",
    "morytania": "Morytania", "varrock": "Varrock",
    "western": "Western Provinces", "wilderness": "Wilderness",
}

_ITEM_NAMES: dict[int, str] | None = None


def _item_names() -> dict[int, str]:
    global _ITEM_NAMES
    if _ITEM_NAMES is None:
        with open(_ITEMS_PATH, encoding="utf-8") as fh:
            doc = json.load(fh)
        _ITEM_NAMES = {rec["item_id"]: rec["item"] for rec in doc["records"]}
    return _ITEM_NAMES


def _spaced(slug: str) -> str:
    return slug.replace("-", " ")


def _build_one(ref_id: str) -> Node:
    domain, _, rest = ref_id.partition(":")
    if domain == "skill":
        return Node(id=ref_id, kind=NodeKind.SKILL, name=_spaced(rest).title(), slug=rest)
    if domain == "item":
        names = _item_names()
        try:
            item_id = int(rest)
        except ValueError:
            raise ValueError(f"{ref_id}: item id must be a numeric item_id, got {rest!r}") from None
        if item_id not in names:
            raise KeyError(f"{ref_id}: item_id not found in data/items_equipment.json")
        return Node(id=ref_id, kind=NodeKind.ITEM, name=names[item_id], slug=rest)
    if domain == "access":
        return Node(id=ref_id, kind=NodeKind.ACCESS, name=_spaced(rest).capitalize(), slug=rest)
    if domain == "minigame":
        return Node(id=ref_id, kind=NodeKind.MINIGAME, name=_spaced(rest).capitalize(), slug=rest)
    if domain == "gear_loadout":
        return Node(id=ref_id, kind=NodeKind.GEAR_LOADOUT, name=_spaced(rest).capitalize(), slug=rest)
    if domain == "npc":
        # NPC display names aren't in the data layer yet; name stays numeric-ish for v1.
        return Node(id=ref_id, kind=NodeKind.MONSTER, name=f"NPC {rest}", slug=rest)
    if domain == "diary":
        region, _, tier = rest.partition(":")
        if not tier:
            raise ValueError(f"{ref_id}: diary id must be diary:<region>:<tier>")
        region_label = DIARY_REGION_LABELS.get(region, region.capitalize())
        return Node(id=ref_id, kind=NodeKind.DIARY,
                    name=f"{region_label} {tier.capitalize()}",
                    slug=f"{region}-{tier}", data={"region": region, "tier": tier})
    raise ValueError(f"unknown ref_node domain in {ref_id!r}")


def build_supporting(referenced_ids: set[str]) -> list[Node]:
    """Return one leaf Node per referenced id, deduped and sorted by id (K9)."""
    return [_build_one(ref_id) for ref_id in sorted(referenced_ids)]
