"""build_content_nodes — the content-node layer for the effect→content map
(diaries spec §4, Task 6).

A diary effect's `dst` is the content it benefits (Barrows, Burgh de Rott, an
abyssal demon). This builder turns committed `data/diary_content_nodes.json`
records into one correctly-typed engine Node each — *existence only*: id, kind,
name, slug, optional data. Their facts (drops, location, stats) are out of scope
here and accrete onto the same stable id in later bricks.

Restricted to the content kinds that have zero instances today and which diary
effects target: `activity` / `monster` / `region`. `skill:` targets are NOT
minted here (skills already exist as nodes); `item:` targets resolve via
build_supporting. Pure transform; no external reads.
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import Node, NodeKind

# content kind -> (NodeKind, id-prefix). Only these three are content-node-created.
_KINDS: dict[str, tuple[NodeKind, str]] = {
    "activity": (NodeKind.ACTIVITY, "activity:"),
    "monster": (NodeKind.MONSTER, "monster:"),
    "region": (NodeKind.REGION, "region:"),
}


def _build_one(rec: dict) -> Node:
    kind = rec["kind"]
    if kind not in _KINDS:
        if kind == "skill":
            raise ValueError(
                f"content_nodes: skill ids are not minted here ({rec['id']!r}); "
                f"skills already exist as nodes")
        raise ValueError(
            f"content_nodes: unknown content kind {kind!r} for {rec['id']!r} "
            f"(expected one of {sorted(_KINDS)})")
    node_kind, prefix = _KINDS[kind]
    if not rec["id"].startswith(prefix):
        raise ValueError(
            f"content_nodes: id {rec['id']!r} does not match its kind prefix "
            f"{prefix!r}")
    return Node(id=rec["id"], kind=node_kind, name=rec["name"], slug=rec["slug"],
                data=rec.get("data", {}))


def build_content_nodes(content_records: list[dict]) -> list[Node]:
    """Return one Node per content record, deduped (identical first-wins) and
    sorted by id. A duplicate id with DIFFERENT content is an authoring bug -> raise."""
    seen: dict[str, Node] = {}
    for rec in content_records:
        node = _build_one(rec)
        prior = seen.get(node.id)
        if prior is not None:
            if prior != node:
                raise ValueError(
                    f"content_nodes: conflicting definitions for {node.id!r}: "
                    f"{prior!r} vs {node!r}")
            continue
        seen[node.id] = node
    return [seen[i] for i in sorted(seen)]
