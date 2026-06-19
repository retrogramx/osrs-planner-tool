"""Shared id + slug helpers for the KG builders (K9, spec §6.6).

Node ids use locked prefixes: quest:<slug>, skill:<slug>, item:<item_id>, ...
Group/edge integer ids are builder-local DETERMINISTIC (stable hash of owner id
+ per-owner sub-index), masked into a fixed positive-int band per domain.
assemble.py re-keys these to GLOBAL ids before writing kg/*.json (Task 7).
"""
from __future__ import annotations

import hashlib
import re

_GROUP_BAND = 0x10000000  # quest condition-group ids live at >= this
_EDGE_BAND = 0x20000000   # quest requires-edge ids live at >= this
_MASK = 0x0FFFFFFF        # 28-bit hash payload


def slugify(name: str) -> str:
    """Lowercase slug: drop apostrophes, every other non-alphanumeric run -> one
    dash, strip leading/trailing dashes. 'Cook's Assistant' -> 'cooks-assistant'."""
    s = name.lower().replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def quest_id(name: str) -> str:
    return f"quest:{slugify(name)}"


def skill_id(name: str) -> str:
    return f"skill:{slugify(name)}"


def item_id(item_id_num: int | str) -> str:
    """Node id for a numeric item id (K9: item:<item_id>). Accepts int or str."""
    return f"item:{int(item_id_num)}"


def access_id(name: str) -> str:
    return f"access:{slugify(name)}"


def gear_loadout_id(name: str) -> str:
    return f"gear_loadout:{slugify(name)}"


def _stable_hash(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) & _MASK


def group_id(owner_id: str, sub_index: int) -> int:
    """Deterministic condition_group id for owner_id's sub_index-th group.
    sub_index 0 = the owner's requires-edge root AND group; 1.. = nested sub-groups."""
    return _GROUP_BAND | _stable_hash(f"{owner_id}#group#{sub_index}")


def edge_id(owner_id: str) -> int:
    """Deterministic requires-edge id for owner_id (one requires edge per quest)."""
    return _EDGE_BAND | _stable_hash(f"{owner_id}#requires")
