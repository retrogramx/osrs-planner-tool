# data/_rarity_grammar.py
"""Parse a dropsline `Rarity` string into a numeric per-roll probability.

NEVER fabricates: a qualitative word ("Common") or an unparseable string returns
None with a status, never a guessed number. Pure + deterministic (no I/O)."""
from __future__ import annotations

import re

_FRACTION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")
_TIMES = re.compile(r"^\s*(\d+)\s*[x×*]\s*(.+)$")
_QUALITATIVE = {"", "~", "always*", "common", "uncommon", "rare", "very rare",
                "varies", "random", "unknown"}

def parse_rarity(raw):
    """Return (rate_per_roll: float|None, rolls_in_string: int, status: str)."""
    if raw is None:
        return (None, 1, "null-qualitative")
    # M3: the API emits comma thousands-separators ("1/3,000", "1/16,384") for the
    # RAREST uniques -- strip them so the fraction regex matches (a comma never
    # appears except as a group separator in these strings). Without this every
    # denominator >=1000 silently becomes null-unparsed.
    s = str(raw).strip().replace(",", "")
    low = s.lower()
    if low in ("always", "1/1"):
        return (1.0, 1, "sourced")
    if low in _QUALITATIVE:
        return (None, 1, "null-qualitative")
    m = _TIMES.match(s)
    if m:
        mult = int(m.group(1))
        rate, _inner_rolls, status = parse_rarity(m.group(2))
        return (rate, mult, status)
    m = _FRACTION.match(s)
    if m:
        num, denom = float(m.group(1)), float(m.group(2))
        if denom <= 0 or num <= 0:
            return (None, 1, "null-unparsed")
        rate = num / denom
        if rate > 1.0:
            return (None, 1, "null-unparsed")
        return (rate, 1, "sourced")
    return (None, 1, "null-unparsed")
