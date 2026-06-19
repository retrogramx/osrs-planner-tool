# src/osrs_planner/cost/prices.py
"""Price providers for the cost overlay.

``PriceProvider`` is the single seam where snapshot -> daily-refresh -> live
all plug in (design spec §7). v1 ships ``SnapshotPriceProvider`` over the
committed ``data/ge_prices.json`` (deterministic, testable). A
``LivePriceProvider`` is a later drop-in on the same interface.

IDs in the cost layer are KG-style ``"item:<n>"`` strings. ``ge_prices.json``
keys by NUMERIC ``item_id``, so the provider strips the ``"item:"`` prefix
internally. A missing or untraded price returns ``None`` (never a fabricated
number) so the routing walk can mark the route ``gold_status="unavailable"``.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod


def _strip_item_prefix(item_id: str) -> int:
    """`"item:4587"` -> ``4587``. Raises on a malformed id (fail loud)."""
    if not item_id.startswith("item:"):
        raise ValueError(f"expected an 'item:<n>' id, got {item_id!r}")
    return int(item_id[len("item:") :])


class PriceProvider(ABC):
    """Abstract price source. ``None`` means 'no known price' (absence != 0)."""

    @abstractmethod
    def ge_price(self, item_id: str) -> int | None:
        """Grand Exchange price for an ``"item:<n>"`` id, or ``None``."""

    @abstractmethod
    def high_alch(self, item_id: str) -> int | None:
        """High-alchemy value for an ``"item:<n>"`` id, or ``None``."""


class SnapshotPriceProvider(PriceProvider):
    """``PriceProvider`` backed by a committed ``data/ge_prices.json`` snapshot.

    The envelope is ``{_provenance, records: [...], _excluded: [...]}`` where
    each record is
    ``{item_id, name, price: {high, low, capturedAt}, high_alch, ...}``.
    ``ge_price`` reads ``price.high`` (the instant-buy side); a null ``high``
    or an unmapped item -> ``None``.
    """

    def __init__(self, records: dict[int, dict]) -> None:
        self._records = records

    @classmethod
    def from_file(cls, path: str) -> "SnapshotPriceProvider":
        with open(path, encoding="utf-8") as f:
            envelope = json.load(f)
        records = {r["item_id"]: r for r in envelope["records"]}
        return cls(records)

    def ge_price(self, item_id: str) -> int | None:
        rec = self._records.get(_strip_item_prefix(item_id))
        if rec is None:
            return None
        return (rec.get("price") or {}).get("high")

    def high_alch(self, item_id: str) -> int | None:
        rec = self._records.get(_strip_item_prefix(item_id))
        if rec is None:
            return None
        return rec.get("high_alch")
